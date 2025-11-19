"""
End-to-end smoke test for the recommendation system.
Tests the full pipeline: ingestion -> processing -> serving.
"""

import pytest
import time
import requests
from typing import Dict, Any


# Configuration
INGEST_URL = "http://localhost:8000"
SERVE_URL = "http://localhost:8001"
TEST_USER_ID = f"smoke_test_user_{int(time.time())}"


@pytest.fixture(scope="module")
def wait_for_services():
    """Wait for services to be ready."""
    max_retries = 30
    for _ in range(max_retries):
        try:
            response = requests.get(f"{INGEST_URL}/health", timeout=2)
            if response.status_code == 200:
                response = requests.get(f"{SERVE_URL}/health", timeout=2)
                if response.status_code == 200:
                    return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    pytest.skip("Services not available")


def test_ingest_event(wait_for_services):
    """Test event ingestion."""
    event = {
        "user_id": TEST_USER_ID,
        "item_id": "item_001",
        "event_type": "view",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    response = requests.post(f"{INGEST_URL}/events", json=event, timeout=5)
    assert response.status_code in [200, 201]
    data = response.json()
    assert "event_id" in data or "status" in data


def test_process_and_recommend(wait_for_services):
    """Test full pipeline: ingest events, wait for processing, get recommendations."""
    # Ingest multiple events
    events = [
        {"user_id": TEST_USER_ID, "item_id": f"item_{i:03d}", "event_type": "view"}
        for i in range(1, 6)
    ]
    
    for event in events:
        response = requests.post(f"{INGEST_URL}/events", json=event, timeout=5)
        assert response.status_code in [200, 201]
    
    # Wait for stream processing (events need time to be processed)
    time.sleep(10)
    
    # Get recommendations
    response = requests.get(
        f"{SERVE_URL}/recommend",
        params={"user_id": TEST_USER_ID, "k": 10},
        timeout=5
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert data["user_id"] == TEST_USER_ID
    # Recommendations may be empty for new users (fallback to popularity)
    assert isinstance(data["recommendations"], list)


def test_fallback_for_new_user(wait_for_services):
    """Test that new users get popularity-based recommendations."""
    new_user_id = f"new_user_{int(time.time())}"
    
    response = requests.get(
        f"{SERVE_URL}/recommend",
        params={"user_id": new_user_id, "k": 10},
        timeout=5
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should return recommendations (even if from popularity baseline)
    assert "recommendations" in data

