"""
Ingestion Service - FastAPI service that receives user events and publishes to Kafka/Redpanda.
This is the entry point for all user interaction events (views, clicks, purchases, etc.).
"""

import uuid
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from kafka import KafkaProducer
from kafka.errors import KafkaError
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from shared.config import settings
from shared.logging_config import setup_logging
from shared.retry import exponential_backoff

# Setup logging
logger = setup_logging("ingest")

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

EVENT_COUNT = Counter(
    'events_ingested_total',
    'Total events ingested',
    ['event_type']
)

# FastAPI app
app = FastAPI(
    title="Recommendation System - Ingestion Service",
    description="Service for ingesting user events and publishing to Kafka",
    version="1.0.0"
)

# Kafka producer (lazy initialization)
producer: Optional[KafkaProducer] = None


class Event(BaseModel):
    """User event model."""
    user_id: str = Field(..., description="User identifier")
    item_id: str = Field(..., description="Item/product identifier")
    event_type: str = Field(..., description="Event type: view, click, purchase, add_to_cart")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp (optional, defaults to now)")
    properties: Optional[dict] = Field(None, description="Additional event properties")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for deduplication")
    
    @validator('event_type')
    def validate_event_type(cls, v):
        """Validate event type."""
        allowed = ['view', 'click', 'purchase', 'add_to_cart', 'remove_from_cart']
        if v not in allowed:
            raise ValueError(f"event_type must be one of {allowed}")
        return v
    
    @validator('timestamp', always=True)
    def set_timestamp(cls, v):
        """Set timestamp if not provided."""
        if v is None:
            return datetime.utcnow().isoformat() + 'Z'
        return v


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    kafka_connected: bool


# Middleware for metrics and logging
class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect metrics and add correlation IDs."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # Start timer
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        # Log request
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                'correlation_id': correlation_id,
                'method': request.method,
                'path': request.url.path,
                'status_code': response.status_code,
                'duration_ms': duration * 1000
            }
        )
        
        # Add correlation ID to response header
        response.headers['X-Correlation-ID'] = correlation_id
        
        return response


app.add_middleware(MetricsMiddleware)


def get_kafka_producer() -> KafkaProducer:
    """Get or create Kafka producer with retry logic."""
    global producer
    
    if producer is None:
        @exponential_backoff(max_retries=3, initial_delay=1.0)
        def create_producer():
            return KafkaProducer(
                bootstrap_servers=settings.kafka.brokers.split(','),
                value_serializer=lambda v: v.encode('utf-8') if isinstance(v, str) else v,
                key_serializer=lambda k: k.encode('utf-8') if k and isinstance(k, str) else None,
                acks='all',  # Wait for all replicas
                retries=3,
                max_in_flight_requests_per_connection=1,  # Ensure ordering
            )
        
        producer = create_producer()
        logger.info("Kafka producer created", extra={'brokers': settings.kafka.brokers})
    
    return producer


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting ingestion service")
    try:
        get_kafka_producer()
        logger.info("Ingestion service started successfully")
    except Exception as e:
        logger.error(f"Failed to start ingestion service: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global producer
    if producer:
        producer.close()
        logger.info("Kafka producer closed")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    kafka_connected = False
    try:
        producer = get_kafka_producer()
        # Simple check - try to get metadata
        producer.list_topics(timeout=5)
        kafka_connected = True
    except Exception as e:
        logger.warning(f"Kafka health check failed: {e}")
    
    return HealthResponse(
        status="healthy" if kafka_connected else "degraded",
        service="ingest",
        kafka_connected=kafka_connected
    )


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        producer = get_kafka_producer()
        producer.list_topics(timeout=5)
        return JSONResponse({"status": "ready"})
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@app.post("/events", status_code=201)
async def ingest_event(event: Event, request: Request):
    """
    Ingest a user event and publish to Kafka.
    
    This endpoint receives user events (views, clicks, purchases, etc.)
    and publishes them to Kafka for downstream processing.
    """
    # Get correlation ID from request state (set by middleware)
    correlation_id = getattr(request.state, 'correlation_id', str(uuid.uuid4()))
    
    try:
        # Generate idempotency key if not provided
        idempotency_key = event.idempotency_key or str(uuid.uuid4())
        
        # Create event message
        event_message = {
            'event_id': str(uuid.uuid4()),
            'user_id': event.user_id,
            'item_id': event.item_id,
            'event_type': event.event_type,
            'timestamp': event.timestamp,
            'properties': event.properties or {},
            'idempotency_key': idempotency_key,
            'correlation_id': correlation_id,
        }
        
        # Serialize to JSON
        import json
        message_value = json.dumps(event_message)
        
        # Publish to Kafka
        producer = get_kafka_producer()
        future = producer.send(
            settings.kafka.topic_events,
            key=event.user_id,  # Partition by user_id for ordering
            value=message_value
        )
        
        # Wait for confirmation (with timeout)
        record_metadata = future.get(timeout=10)
        
        # Record metrics
        EVENT_COUNT.labels(event_type=event.event_type).inc()
        
        logger.info(
            "Event ingested successfully",
            extra={
                'correlation_id': correlation_id,
                'user_id': event.user_id,
                'item_id': event.item_id,
                'event_type': event.event_type,
                'topic': record_metadata.topic,
                'partition': record_metadata.partition,
                'offset': record_metadata.offset
            }
        )
        
        return {
            "status": "success",
            "event_id": event_message['event_id'],
            "topic": record_metadata.topic,
            "partition": record_metadata.partition,
            "offset": record_metadata.offset
        }
    
    except KafkaError as e:
        logger.error(
            "Failed to publish event to Kafka",
            extra={
                'correlation_id': correlation_id,
                'error': str(e),
                'user_id': event.user_id
            },
            exc_info=True
        )
        raise HTTPException(status_code=503, detail=f"Failed to publish event: {str(e)}")
    
    except Exception as e:
        logger.error(
            "Unexpected error ingesting event",
            extra={
                'correlation_id': correlation_id,
                'error': str(e)
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(REGISTRY), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

