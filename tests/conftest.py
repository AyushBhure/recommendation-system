"""
Pytest configuration and shared fixtures.
"""

import pytest
import os

# Set test environment variables
os.environ.setdefault('POSTGRES_HOST', 'localhost')
os.environ.setdefault('POSTGRES_PORT', '5432')
os.environ.setdefault('POSTGRES_DB', 'recommendation_db')
os.environ.setdefault('POSTGRES_USER', 'recommendation_user')
os.environ.setdefault('POSTGRES_PASSWORD', 'recommendation_pass')
os.environ.setdefault('REDIS_HOST', 'localhost')
os.environ.setdefault('REDIS_PORT', '6379')
os.environ.setdefault('KAFKA_BROKERS', 'localhost:9092')
os.environ.setdefault('MLFLOW_TRACKING_URI', 'http://localhost:5000')

