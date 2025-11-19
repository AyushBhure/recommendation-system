"""
Stream Processor - Consumes events from Kafka and computes real-time features.
Provides both Spark Structured Streaming (production) and lightweight Python consumer (dev).
This service updates user/item features in Redis and PostgreSQL.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from kafka import KafkaConsumer
from kafka.errors import KafkaError
import psycopg2
from psycopg2.extras import execute_values
from redis import Redis
from prometheus_client import Counter, Histogram, Gauge, start_http_server

from shared.config import settings
from shared.logging_config import setup_logging
from shared.retry import exponential_backoff
from shared.circuit_breaker import CircuitBreaker

# Setup logging
logger = setup_logging("stream_processor")

# Prometheus metrics
EVENTS_PROCESSED = Counter(
    'events_processed_total',
    'Total events processed',
    ['event_type', 'status']
)

PROCESSING_LATENCY = Histogram(
    'event_processing_duration_seconds',
    'Event processing latency',
    ['event_type']
)

FEATURES_UPDATED = Counter(
    'features_updated_total',
    'Total feature updates',
    ['feature_type']
)

KAFKA_LAG = Gauge(
    'kafka_consumer_lag',
    'Kafka consumer lag',
    ['topic', 'partition']
)

# Circuit breakers for external services
redis_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="redis"
)

postgres_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="postgres"
)


class FeatureStore:
    """Manages feature storage in Redis and PostgreSQL."""
    
    def __init__(self):
        """Initialize feature store connections."""
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
    
    @redis_breaker.call
    @exponential_backoff(max_retries=3)
    def update_user_features(self, user_id: str, features: Dict[str, Any]) -> None:
        """
        Update user features in Redis cache and PostgreSQL.
        
        Args:
            user_id: User identifier
            features: Feature dictionary to store
        """
        # Update Redis cache
        cache_key = f"features:user:{user_id}"
        self.redis.setex(
            cache_key,
            settings.redis.ttl_seconds,
            json.dumps(features)
        )
        
        # Update PostgreSQL (persistent store)
        cur = self.postgres.cursor()
        try:
            cur.execute(
                """
                INSERT INTO user_features (user_id, features, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET features = %s, updated_at = %s
                """,
                (user_id, json.dumps(features), datetime.utcnow(), json.dumps(features), datetime.utcnow())
            )
        finally:
            cur.close()
        
        FEATURES_UPDATED.labels(feature_type='user').inc()
        logger.debug(f"Updated features for user {user_id}")
    
    @redis_breaker.call
    @exponential_backoff(max_retries=3)
    def update_item_features(self, item_id: str, features: Dict[str, Any]) -> None:
        """Update item features in Redis and PostgreSQL."""
        cache_key = f"features:item:{item_id}"
        self.redis.setex(
            cache_key,
            settings.redis.ttl_seconds,
            json.dumps(features)
        )
        
        cur = self.postgres.cursor()
        try:
            cur.execute(
                """
                INSERT INTO item_features (item_id, features, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (item_id)
                DO UPDATE SET features = %s, updated_at = %s
                """,
                (item_id, json.dumps(features), datetime.utcnow(), json.dumps(features), datetime.utcnow())
            )
        finally:
            cur.close()
        
        FEATURES_UPDATED.labels(feature_type='item').inc()
        logger.debug(f"Updated features for item {item_id}")
    
    @redis_breaker.call
    def get_user_features(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user features from cache."""
        cache_key = f"features:user:{user_id}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        return None
    
    def close(self):
        """Close connections."""
        self.redis.close()
        self.postgres.close()


class EventProcessor:
    """Processes events and computes features."""
    
    def __init__(self, feature_store: FeatureStore):
        """Initialize event processor."""
        self.feature_store = feature_store
        self.processed_ids = set()  # Simple in-memory deduplication (use Redis in production)
    
    def process_event(self, event: Dict[str, Any]) -> None:
        """
        Process a single event and update features.
        
        Args:
            event: Event dictionary from Kafka
        """
        start_time = time.time()
        event_type = event.get('event_type', 'unknown')
        user_id = event.get('user_id')
        item_id = event.get('item_id')
        idempotency_key = event.get('idempotency_key')
        
        # Idempotency check
        if idempotency_key and idempotency_key in self.processed_ids:
            logger.debug(f"Skipping duplicate event: {idempotency_key}")
            EVENTS_PROCESSED.labels(event_type=event_type, status='duplicate').inc()
            return
        
        try:
            # Update user features
            if user_id:
                user_features = self.feature_store.get_user_features(user_id) or {}
                
                # Compute simple features (in production, use more sophisticated algorithms)
                user_features['total_events'] = user_features.get('total_events', 0) + 1
                user_features[f'{event_type}_count'] = user_features.get(f'{event_type}_count', 0) + 1
                user_features['last_event_at'] = event.get('timestamp')
                user_features['last_event_type'] = event_type
                
                # Update recent items
                if 'recent_items' not in user_features:
                    user_features['recent_items'] = []
                recent_items = user_features['recent_items']
                if item_id not in recent_items:
                    recent_items.insert(0, item_id)
                    recent_items = recent_items[:10]  # Keep last 10
                user_features['recent_items'] = recent_items
                
                self.feature_store.update_user_features(user_id, user_features)
            
            # Update item features
            if item_id:
                item_features = {
                    'total_events': 1,  # Simplified - in production, aggregate from DB
                    f'{event_type}_count': 1,
                    'last_event_at': event.get('timestamp'),
                }
                self.feature_store.update_item_features(item_id, item_features)
            
            # Update interactions table
            self._update_interactions(user_id, item_id, event_type, event.get('timestamp'))
            
            # Mark as processed
            if idempotency_key:
                self.processed_ids.add(idempotency_key)
                # Limit size (simple approach - use Redis TTL in production)
                if len(self.processed_ids) > 10000:
                    self.processed_ids.clear()
            
            duration = time.time() - start_time
            PROCESSING_LATENCY.labels(event_type=event_type).observe(duration)
            EVENTS_PROCESSED.labels(event_type=event_type, status='success').inc()
            
            logger.info(
                f"Processed event: {event_type}",
                extra={
                    'user_id': user_id,
                    'item_id': item_id,
                    'event_type': event_type,
                    'duration_ms': duration * 1000
                }
            )
        
        except Exception as e:
            EVENTS_PROCESSED.labels(event_type=event_type, status='error').inc()
            logger.error(
                f"Failed to process event: {e}",
                extra={
                    'user_id': user_id,
                    'item_id': item_id,
                    'event_type': event_type,
                    'error': str(e)
                },
                exc_info=True
            )
            raise
    
    @postgres_breaker.call
    @exponential_backoff(max_retries=3)
    def _update_interactions(self, user_id: str, item_id: str, event_type: str, timestamp: str) -> None:
        """Update interactions table in PostgreSQL."""
        if not user_id or not item_id:
            return
        
        conn = psycopg2.connect(
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.db,
            user=settings.database.user,
            password=settings.database.password
        )
        conn.autocommit = True
        
        try:
            cur = conn.cursor()
            event_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            cur.execute(
                """
                INSERT INTO interactions (user_id, item_id, interaction_type, count, last_interaction_at)
                VALUES (%s, %s, %s, 1, %s)
                ON CONFLICT (user_id, item_id, interaction_type)
                DO UPDATE SET
                    count = interactions.count + 1,
                    last_interaction_at = %s
                """,
                (user_id, item_id, event_type, event_timestamp, event_timestamp)
            )
        finally:
            cur.close()
            conn.close()


def create_kafka_consumer() -> KafkaConsumer:
    """Create Kafka consumer with retry logic."""
    @exponential_backoff(max_retries=3, initial_delay=2.0)
    def _create():
        return KafkaConsumer(
            settings.kafka.topic_events,
            bootstrap_servers=settings.kafka.brokers.split(','),
            group_id=settings.kafka.consumer_group,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',  # Start from beginning if no offset
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            consumer_timeout_ms=10000,  # Timeout for polling
        )
    
    return _create()


def main():
    """Main processing loop."""
    logger.info("Starting stream processor")
    
    # Start Prometheus metrics server
    start_http_server(8002)
    logger.info("Metrics server started on port 8002")
    
    # Initialize components
    feature_store = FeatureStore()
    processor = EventProcessor(feature_store)
    
    # Create consumer
    try:
        consumer = create_kafka_consumer()
        logger.info(f"Connected to Kafka: {settings.kafka.brokers}")
    except Exception as e:
        logger.error(f"Failed to create Kafka consumer: {e}", exc_info=True)
        sys.exit(1)
    
    # Processing loop
    logger.info("Starting event processing loop...")
    try:
        while True:
            try:
                # Poll for messages
                message_batch = consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    continue
                
                # Process each message
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        try:
                            event = message.value
                            processor.process_event(event)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}", exc_info=True)
                            # Continue processing other messages
                
                # Update lag metrics
                for topic_partition in message_batch.keys():
                    # Simple lag estimation (in production, use consumer metrics)
                    pass
                
            except KafkaError as e:
                logger.error(f"Kafka error: {e}", exc_info=True)
                time.sleep(5)  # Back off before retrying
            
            except KeyboardInterrupt:
                logger.info("Shutting down stream processor...")
                break
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                time.sleep(5)
    
    finally:
        consumer.close()
        feature_store.close()
        logger.info("Stream processor stopped")


if __name__ == "__main__":
    main()

