# Real-Time Recommendation System

A production-grade, fault-tolerant ML system that ingests streaming user events and serves low-latency personalized recommendations.

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   React     │─────▶│   Ingest     │─────▶│  Kafka/Redpanda │
│  Frontend   │      │   Service    │      │   Event Stream  │
└─────────────┘      └──────────────┘      └─────────────────┘
                                                      │
                                                      ▼
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Serve     │◀─────│   Feature    │◀─────│ Stream Processor│
│  Service    │      │    Store     │      │   (Spark/Python)│
│ (FastAPI)   │      │  (Redis/DB)  │      └─────────────────┘
└─────────────┘      └──────────────┘              │
       │                    │                      │
       │                    ▼                      ▼
       │            ┌──────────────┐      ┌─────────────────┐
       └───────────▶│  Vector DB   │      │   MongoDB       │
                    │(Pinecone/    │      │  Event Store    │
                    │   FAISS)     │      └─────────────────┘
                    └──────────────┘
                            ▲
                            │
                    ┌──────────────┐
                    │   Trainer    │
                    │  (MLflow)    │
                    └──────────────┘
                            ▲
                            │
                    ┌──────────────┐
                    │   Airflow    │
                    │ Orchestration│
                    └──────────────┘
```

### Key Components

1. **Ingestion Service**: FastAPI service that receives user events and publishes to Kafka/Redpanda
2. **Stream Processor**: Spark Structured Streaming job (with Python fallback) that computes features in real-time
3. **Feature Store**: Redis for low-latency feature caching, PostgreSQL for persistent metadata
4. **Vector Store**: Pinecone (production) or FAISS (local dev) for similarity search
5. **Training Pipeline**: PyTorch/LightGBM models tracked with MLflow, orchestrated by Airflow
6. **Serving Service**: FastAPI endpoint that serves recommendations with caching and fallbacks
7. **Frontend**: React demo application

## Quick Start (Local Development)

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Node.js 18+ (for frontend)
- Make (optional, for convenience scripts)

### Step 1: Clone and Setup

```bash
git clone https://github.com/AyushBhure/recommendation-system.git
cd recommendation-system
cp .env.example .env
# Edit .env if needed (defaults work for local dev)
```

### Step 2: Start Infrastructure

```bash
# Start all services with Docker Compose
docker-compose -f infra/docker-compose.yml up -d

# Wait for services to be healthy (about 30 seconds)
docker-compose -f infra/docker-compose.yml ps
```

### Step 3: Initialize Databases

```bash
# Run database migrations and seed sample data
python scripts/bootstrap_sample_data.py
```

### Step 4: Start Services

In separate terminals:

```bash
# Terminal 1: Ingestion Service
cd services/ingest
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Stream Processor
cd services/stream_processor
python main.py

# Terminal 3: Serving Service
cd services/serve
python -m uvicorn main:app --reload --port 8001

# Terminal 4: Frontend
cd frontend
npm install
npm start
```

### Step 5: Run Training (Optional)

```bash
cd services/trainer
python train.py --experiment-name recommendation-system
```

### Step 6: Test the System

```bash
# Run end-to-end smoke test
./scripts/run_smoke_test.sh
```

Or manually:

```bash
# Generate some events
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "event_type": "view", "item_id": "item1", "timestamp": "2024-01-01T00:00:00Z"}'

# Wait a few seconds for processing, then get recommendations
curl "http://localhost:8001/recommend?user_id=user1&k=10"
```

## Project Structure

```
.
├── infra/                    # Infrastructure as Code
│   ├── docker-compose.yml    # Local dev environment
│   ├── k8s/                  # Kubernetes manifests
│   └── terraform/            # Azure Terraform configs
├── services/
│   ├── ingest/               # Event ingestion service
│   ├── stream_processor/     # Spark/Python stream processor
│   ├── trainer/              # Model training + MLflow
│   └── serve/                # Recommendation serving API
├── frontend/                 # React demo application
├── ops/                      # Operations scripts
│   ├── prometheus/           # Prometheus config
│   ├── grafana/              # Grafana dashboards
│   └── otlp/                 # OpenTelemetry config
├── tests/
│   ├── unit/                 # Unit tests
│   └── e2e/                  # End-to-end tests
├── scripts/                  # Utility scripts
└── data/                     # Sample data (gitignored)
```

## Testing

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=services --cov-report=html
```

### End-to-End Tests

```bash
# Ensure Docker Compose is running
./scripts/run_smoke_test.sh
```

## Production Deployment

### Kubernetes (AKS)

1. **Provision Azure Resources**:
   ```bash
   cd infra/terraform
   terraform init
   terraform plan
   terraform apply
   ```

2. **Deploy to AKS**:
   ```bash
   # Configure kubectl
   az aks get-credentials --resource-group recommendation-system-rg --name recommendation-aks

   # Apply manifests
   kubectl apply -f infra/k8s/
   ```

3. **Verify Deployment**:
   ```bash
   kubectl get pods -n recommendation-system
   kubectl get services -n recommendation-system
   ```

See `infra/k8s/README.md` for detailed deployment instructions.

## Configuration

All configuration is managed via environment variables. See `.env.example` for all available options.

Key configuration areas:
- **Databases**: PostgreSQL, MongoDB, Redis connection strings
- **Streaming**: Kafka/Redpanda brokers and topics
- **Vector Search**: Pinecone API key (or use FAISS locally)
- **MLflow**: Tracking URI and experiment name
- **Observability**: Prometheus, Grafana, OpenTelemetry endpoints

## Observability

### Metrics (Prometheus)

- Service: `http://localhost:9090`
- Metrics endpoint: `http://localhost:8001/metrics`

### Dashboards (Grafana)

- Service: `http://localhost:3001`
- Default credentials: `admin/admin`
- Pre-configured dashboards in `ops/grafana/dashboards/`

### Logs

Structured JSON logs are emitted by all services. View with:

```bash
docker-compose -f infra/docker-compose.yml logs -f [service-name]
```

## Mentoring & Best Practices

See [MENTORING.md](./MENTORING.md) for:
- System design interview talking points
- Best practices for junior engineers
- Testing strategies
- Deployment patterns
- Observability practices

## Development

### Code Quality

```bash
# Format code
black services/ tests/

# Lint
flake8 services/ tests/
pylint services/

# Type checking
mypy services/

# Pre-commit hooks (install with)
pre-commit install
```

### Adding New Features

1. Create feature branch
2. Write tests first (TDD)
3. Implement feature
4. Ensure all tests pass
5. Update documentation
6. Submit PR

## Security Notes

- **Never commit `.env` files** - use `.env.example` as template
- **Rotate secrets regularly** in production
- **Use Kubernetes secrets** for sensitive data
- **Enable TLS** for all database connections in production
- **Implement rate limiting** on public endpoints

## Design Decisions & Tradeoffs

### At-Least-Once vs Exactly-Once

- **Current**: At-least-once delivery (simpler, lower latency)
- **Rationale**: Idempotency keys in events handle duplicates
- **Tradeoff**: Slight risk of duplicate processing (acceptable for recommendations)

### Redis vs PostgreSQL for Feature Cache

- **Redis**: Hot features, low-latency reads (<1ms)
- **PostgreSQL**: Persistent metadata, user/item profiles
- **Rationale**: Hybrid approach balances speed and durability

### Pinecone vs FAISS

- **Pinecone**: Production scale, managed service
- **FAISS**: Local dev, no external dependencies
- **Rationale**: Fallback ensures system works without cloud dependencies

### Spark vs Lightweight Python Consumer

- **Spark**: Production scale, complex aggregations
- **Python Consumer**: Local dev, simpler debugging
- **Rationale**: Both provided for flexibility



Contributions welcome! Please read CONTRIBUTING.md first.

---

**Status**: ✅ Production-ready for local development. Azure deployment requires credentials setup.

