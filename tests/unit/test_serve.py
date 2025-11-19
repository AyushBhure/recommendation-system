"""
Unit tests for serving service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.serve.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_recommendation_engine():
    """Mock recommendation engine."""
    engine = Mock()
    engine.get_recommendations.return_value = [
        {"item_id": "item_001", "score": 0.95, "metadata": {}},
        {"item_id": "item_002", "score": 0.87, "metadata": {}},
    ]
    engine.model = Mock()  # Mock model
    
    with patch('services.serve.main.recommendation_engine', engine):
        yield engine


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "serve"


def test_get_recommendations(client, mock_recommendation_engine):
    """Test getting recommendations."""
    response = client.get("/recommend?user_id=user_001&k=10")
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert data["user_id"] == "user_001"
    assert len(data["recommendations"]) == 2
    
    # Verify engine was called
    mock_recommendation_engine.get_recommendations.assert_called_once_with("user_001", 10)


def test_get_recommendations_missing_user_id(client):
    """Test getting recommendations without user_id."""
    response = client.get("/recommend")
    assert response.status_code == 422  # Validation error


def test_get_recommendations_invalid_k(client):
    """Test getting recommendations with invalid k."""
    response = client.get("/recommend?user_id=user_001&k=200")  # k > 100
    assert response.status_code == 422  # Validation error


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

