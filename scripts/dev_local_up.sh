#!/bin/bash
# Development local setup script
# Brings up Docker Compose and runs migrations/bootstrap

set -e

echo "=========================================="
echo "Starting Recommendation System (Local Dev)"
echo "=========================================="

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env created. Please review and update if needed."
fi

# Start Docker Compose
echo ""
echo "Starting Docker Compose services..."
docker-compose -f infra/docker-compose.yml up -d

# Wait for services to be healthy
echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check service health
echo ""
echo "Checking service health..."
docker-compose -f infra/docker-compose.yml ps

# Wait a bit more for databases to be ready
echo ""
echo "Waiting for databases to initialize..."
sleep 15

# Run database migrations (if any)
echo ""
echo "Running database migrations..."
# Add migration commands here if needed

# Bootstrap sample data
echo ""
echo "Bootstrapping sample data..."
python scripts/bootstrap_sample_data.py

echo ""
echo "=========================================="
echo "✓ Local development environment ready!"
echo "=========================================="
echo ""
echo "Services available at:"
echo "  - Ingestion API: http://localhost:8000"
echo "  - Serving API: http://localhost:8001"
echo "  - MLflow UI: http://localhost:5000"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3001 (admin/admin)"
echo ""
echo "Next steps:"
echo "  1. Start services: see README.md for instructions"
echo "  2. Run smoke test: ./scripts/run_smoke_test.sh"
echo ""

