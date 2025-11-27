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

## Configuration

All configuration is managed via environment variables. See `.env.example` for all available options.

Key configuration areas:
- **Databases**: PostgreSQL, MongoDB, Redis connection strings
- **Streaming**: Kafka/Redpanda brokers and topics
- **Vector Search**: Pinecone API key (or use FAISS locally)
- **MLflow**: Tracking URI and experiment name
- **Observability**: Prometheus, Grafana, OpenTelemetry endpoints

## Observability

### Logs

Structured JSON logs are emitted by all services. View with:

```bash
docker-compose -f infra/docker-compose.yml logs -f [service-name]
```
