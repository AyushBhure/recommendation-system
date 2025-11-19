"""
Unit tests for ingestion service.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.ingest.main import app, get_kafka_producer


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer."""
    producer = Mock()
    future = Mock()
    future.get.return_value = Mock(
        topic='user-events',
        partition=0,
        offset=123
    )
    producer.send.return_value = future
    producer.list_topics.return_value = []
    
    with patch('services.ingest.main.get_kafka_producer', return_value=producer):
        yield producer


def test_health_check(client, mock_kafka_producer):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["service"] == "ingest"


def test_ingest_event(client, mock_kafka_producer):
    """Test event ingestion."""
    event = {
        "user_id": "user_001",
        "item_id": "item_001",
        "event_type": "view",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    response = client.post("/events", json=event)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "event_id" in data
    assert data["topic"] == "user-events"
    
    # Verify Kafka producer was called
    mock_kafka_producer.send.assert_called_once()


def test_ingest_event_invalid_type(client):
    """Test event ingestion with invalid event type."""
    event = {
        "user_id": "user_001",
        "item_id": "item_001",
        "event_type": "invalid_type"
    }
    
    response = client.post("/events", json=event)
    assert response.status_code == 422  # Validation error


def test_ingest_event_auto_timestamp(client, mock_kafka_producer):
    """Test event ingestion with auto-generated timestamp."""
    event = {
        "user_id": "user_001",
        "item_id": "item_001",
        "event_type": "view"
    }
    
    response = client.post("/events", json=event)
    assert response.status_code == 201
    data = response.json()
    assert "event_id" in data


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

