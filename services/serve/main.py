"""
Serving Service - FastAPI service that serves personalized recommendations.
Loads models from MLflow, uses vector search (Pinecone/FAISS), and caches features in Redis.
Implements fallback to popularity baseline for new users.
"""

import os
import sys
import json
import time
import pickle
from typing import List, Dict, Optional, Any
from datetime import datetime

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import psycopg2
from redis import Redis
import mlflow
from mlflow.tracking import MlflowClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import settings
from shared.logging_config import setup_logging
from shared.retry import exponential_backoff
from shared.circuit_breaker import CircuitBreaker

# Setup logging
logger = setup_logging("serve")

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

RECOMMENDATION_COUNT = Counter(
    'recommendations_served_total',
    'Total recommendations served',
    ['user_type']  # new_user, existing_user
)

CACHE_HIT_RATE = Gauge(
    'cache_hit_rate',
    'Feature cache hit rate'
)

# Circuit breakers
redis_breaker = CircuitBreaker(failure_threshold=5, name="redis")
postgres_breaker = CircuitBreaker(failure_threshold=5, name="postgres")
mlflow_breaker = CircuitBreaker(failure_threshold=5, name="mlflow")

# FastAPI app
app = FastAPI(
    title="Recommendation System - Serving Service",
    description="Service for serving personalized recommendations",
    version="1.0.0"
)

# Global state
model_cache: Optional[Any] = None
vector_db = None  # Will be initialized based on config


class VectorDB:
    """Vector database interface (Pinecone or FAISS)."""
    
    def __init__(self):
        """Initialize vector database."""
        if settings.vector_db.use_pinecone and settings.vector_db.pinecone_api_key:
            self._init_pinecone()
        else:
            self._init_faiss()
    
    def _init_pinecone(self):
        """Initialize Pinecone (production)."""
        try:
            import pinecone
            pinecone.init(
                api_key=settings.vector_db.pinecone_api_key,
                environment=settings.vector_db.pinecone_environment
            )
            self.index = pinecone.Index(settings.vector_db.pinecone_index_name)
            self.db_type = "pinecone"
            logger.info("Initialized Pinecone vector database")
        except Exception as e:
            logger.warning(f"Failed to initialize Pinecone, falling back to FAISS: {e}")
            self._init_faiss()
    
    def _init_faiss(self):
        """Initialize FAISS (local fallback)."""
        try:
            import faiss
            index_path = settings.vector_db.faiss_index_path
            if os.path.exists(index_path):
                self.index = faiss.read_index(index_path)
            else:
                # Create empty index
                dimension = settings.vector_db.faiss_dimension
                self.index = faiss.IndexFlatL2(dimension)
                os.makedirs(os.path.dirname(index_path), exist_ok=True)
                faiss.write_index(self.index, index_path)
            self.db_type = "faiss"
            logger.info("Initialized FAISS vector database (local)")
        except ImportError:
            logger.warning("FAISS not available, using in-memory fallback")
            self.db_type = "memory"
            self.index = {}
    
    def search(self, query_vector: np.ndarray, k: int = 10) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query vector
            k: Number of results
        
        Returns:
            List of similar items with scores
        """
        if self.db_type == "pinecone":
            results = self.index.query(
                vector=query_vector.tolist(),
                top_k=k,
                include_metadata=True
            )
            return [
                {
                    'item_id': match.id,
                    'score': match.score,
                    'metadata': match.metadata
                }
                for match in results.matches
            ]
        elif self.db_type == "faiss":
            query_vector = query_vector.reshape(1, -1).astype('float32')
            distances, indices = self.index.search(query_vector, k)
            return [
                {
                    'item_id': f"item_{idx}",
                    'score': float(1.0 / (1.0 + dist)),
                    'metadata': {}
                }
                for dist, idx in zip(distances[0], indices[0]) if idx >= 0
            ]
        else:
            # Memory fallback - return empty
            return []


class RecommendationEngine:
    """Generates recommendations for users."""
    
    def __init__(self):
        """Initialize recommendation engine."""
        self.redis = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password,
            decode_responses=True
        )
        
        self.postgres = psycopg2.connect(
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.db,
            user=settings.database.user,
            password=settings.database.password
        )
        self.postgres.autocommit = True
        
        self.vector_db = VectorDB()
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load latest model from MLflow."""
        try:
            client = MlflowClient(settings.mlflow.tracking_uri)
            latest_version = client.get_latest_versions("recommendation-model", stages=["Production", "Staging"])
            
            if latest_version:
                model_version = latest_version[0]
                model_uri = f"models:/recommendation-model/{model_version.version}"
                self.model = mlflow.sklearn.load_model(model_uri)
                logger.info(f"Loaded model version {model_version.version}")
            else:
                logger.warning("No model found in MLflow, using popularity baseline")
        except Exception as e:
            logger.warning(f"Failed to load model from MLflow: {e}, using popularity baseline")
    
    @redis_breaker.call
    @exponential_backoff(max_retries=3)
    def get_user_features(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user features from cache or database."""
        # Try cache first
        cache_key = f"features:user:{user_id}"
        cached = self.redis.get(cache_key)
        if cached:
            CACHE_HIT_RATE.set(1.0)
            return json.loads(cached)
        
        CACHE_HIT_RATE.set(0.0)
        
        # Fallback to database
        cur = self.postgres.cursor()
        try:
            cur.execute(
                "SELECT features FROM user_features WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                return json.loads(row[0])
        finally:
            cur.close()
        
        return None
    
    @postgres_breaker.call
    @exponential_backoff(max_retries=3)
    def get_popular_items(self, k: int = 10) -> List[Dict[str, Any]]:
        """Get popular items as fallback."""
        cur = self.postgres.cursor()
        try:
            cur.execute(
                """
                SELECT item_id, SUM(count) as total_interactions
                FROM interactions
                WHERE last_interaction_at > NOW() - INTERVAL '30 days'
                GROUP BY item_id
                ORDER BY total_interactions DESC
                LIMIT %s
                """,
                (k,)
            )
            return [
                {'item_id': row[0], 'score': float(row[1]), 'metadata': {}}
                for row in cur.fetchall()
            ]
        finally:
            cur.close()
    
    def get_recommendations(self, user_id: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Get recommendations for a user.
        
        Args:
            user_id: User identifier
            k: Number of recommendations
        
        Returns:
            List of recommended items with scores
        """
        start_time = time.time()
        
        # Get user features
        user_features = self.get_user_features(user_id)
        
        if user_features and 'feature_vector' in user_features:
            # Use vector search
            query_vector = np.array(user_features['feature_vector'])
            recommendations = self.vector_db.search(query_vector, k=k)
            user_type = "existing_user"
        else:
            # Fallback to popularity
            recommendations = self.get_popular_items(k=k)
            user_type = "new_user"
            logger.info(f"Using popularity baseline for user {user_id}")
        
        RECOMMENDATION_COUNT.labels(user_type=user_type).inc()
        
        duration = time.time() - start_time
        logger.info(
            f"Generated {len(recommendations)} recommendations",
            extra={
                'user_id': user_id,
                'k': k,
                'user_type': user_type,
                'duration_ms': duration * 1000
            }
        )
        
        return recommendations


# Global recommendation engine
recommendation_engine: Optional[RecommendationEngine] = None


# Middleware for metrics
class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect metrics."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response


app.add_middleware(MetricsMiddleware)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global recommendation_engine
    logger.info("Starting serving service")
    try:
        recommendation_engine = RecommendationEngine()
        logger.info("Serving service started successfully")
    except Exception as e:
        logger.error(f"Failed to start serving service: {e}", exc_info=True)
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "serve",
        "model_loaded": recommendation_engine.model is not None if recommendation_engine else False
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    if recommendation_engine is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    return {"status": "ready"}


@app.get("/recommend")
async def get_recommendations(
    user_id: str = Query(..., description="User identifier"),
    k: int = Query(10, ge=1, le=100, description="Number of recommendations")
):
    """
    Get personalized recommendations for a user.
    
    Returns:
        List of recommended items with scores
    """
    if recommendation_engine is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        recommendations = recommendation_engine.get_recommendations(user_id, k=k)
        
        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "count": len(recommendations),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(REGISTRY), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

