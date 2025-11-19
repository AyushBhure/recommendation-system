# Makefile for Recommendation System
# Provides convenient commands for common tasks

.PHONY: help setup up down test lint format clean

help:
	@echo "Available commands:"
	@echo "  make setup     - Install Python dependencies"
	@echo "  make up         - Start Docker Compose services"
	@echo "  make down       - Stop Docker Compose services"
	@echo "  make bootstrap  - Bootstrap sample data"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters"
	@echo "  make format     - Format code"
	@echo "  make clean      - Clean temporary files"

setup:
	pip install -r requirements.txt
	pip install -r services/ingest/requirements.txt
	pip install -r services/serve/requirements.txt
	pip install -r services/stream_processor/requirements.txt
	pip install -r services/trainer/requirements.txt
	pip install -r shared/requirements.txt

up:
	docker-compose -f infra/docker-compose.yml up -d

down:
	docker-compose -f infra/docker-compose.yml down

bootstrap:
	python scripts/bootstrap_sample_data.py

test:
	pytest tests/ -v

lint:
	flake8 services/ tests/
	mypy services/ --ignore-missing-imports || true

format:
	black services/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov

