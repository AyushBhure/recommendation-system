# Mentoring Guide: Real-Time Recommendation System

This document provides talking points, best practices, and learning resources for engineers working on or learning from this recommendation system.

## 🎯 System Design Interview Talking Points

### High-Level Architecture

**Question**: "How would you design a real-time recommendation system?"

**Key Points to Cover**:

1. **Data Flow**:
   - User events → Ingestion → Stream Processing → Feature Store → Serving
   - Batch training pipeline runs periodically to update models

2. **Scalability**:
   - Horizontal scaling: Stateless services, partitioned Kafka topics
   - Caching: Redis for hot features, CDN for static content
   - Database: Read replicas, sharding by user_id

3. **Latency**:
   - Pre-compute features where possible
   - Cache frequently accessed data
   - Use async processing for non-critical paths

4. **Fault Tolerance**:
   - At-least-once delivery with idempotency
   - Circuit breakers for external services
   - Graceful degradation (fallback to popularity)

5. **Consistency**:
   - Eventual consistency for recommendations (acceptable)
   - Strong consistency for user profiles (when needed)

### Tradeoffs Discussed

1. **At-Least-Once vs Exactly-Once**:
   - **At-least-once**: Simpler, lower latency, requires idempotency
   - **Exactly-once**: More complex, higher latency, stronger guarantees
   - **Our choice**: At-least-once with idempotency keys

2. **Redis vs PostgreSQL for Features**:
   - **Redis**: Fast, in-memory, volatile
   - **PostgreSQL**: Persistent, queryable, slower
   - **Our choice**: Hybrid - Redis for hot cache, PostgreSQL for persistence

3. **Spark vs Lightweight Consumer**:
   - **Spark**: Scales to millions of events, complex aggregations
   - **Python Consumer**: Simpler, easier to debug, sufficient for moderate scale
   - **Our choice**: Both - Spark for production, Python for dev

## 🧪 Testing Best Practices

### Unit Testing

**Why**: Catch bugs early, enable refactoring, document behavior

**Principles**:
- Test one thing at a time
- Use descriptive test names
- Arrange-Act-Assert pattern
- Mock external dependencies

**Example**:
```python
def test_recommendation_with_cached_features():
    # Arrange
    user_id = "user1"
    mock_redis = Mock()
    mock_redis.get.return_value = json.dumps({"features": [1, 2, 3]})
    
    # Act
    result = get_recommendations(user_id, redis_client=mock_redis)
    
    # Assert
    assert len(result) > 0
    mock_redis.get.assert_called_once_with(f"features:{user_id}")
```

### Integration Testing

**Why**: Verify components work together correctly

**Approach**:
- Test against real databases (use test containers)
- Test API endpoints end-to-end
- Verify data flows correctly

### End-to-End Testing

**Why**: Validate entire system works as expected

**Approach**:
- Use Docker Compose for full stack
- Generate realistic test data
- Verify outcomes match expectations

## 🚀 Deployment Best Practices

### Containerization

**Why**: Consistent environments, easy scaling, isolation

**Best Practices**:
- Use multi-stage builds to reduce image size
- Don't run as root
- Health checks in Dockerfiles
- .dockerignore to exclude unnecessary files

### Kubernetes

**Why**: Orchestration, auto-scaling, self-healing

**Key Concepts**:
- **Deployments**: Manage pod replicas
- **Services**: Load balancing, service discovery
- **ConfigMaps**: Non-sensitive configuration
- **Secrets**: Sensitive data (encrypted at rest)
- **Readiness/Liveness Probes**: Health monitoring

**Example Pattern**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Infrastructure as Code

**Why**: Reproducible, version-controlled infrastructure

**Tools**:
- **Terraform**: Provision cloud resources
- **Helm**: Package Kubernetes applications
- **Ansible**: Configuration management

## 📊 Observability Best Practices

### Logging

**Structured Logging**:
- Use JSON format for machine parsing
- Include correlation IDs for tracing
- Log levels: DEBUG, INFO, WARN, ERROR
- Never log sensitive data (passwords, tokens)

**Example**:
```python
logger.info("event_processed", extra={
    "user_id": user_id,
    "event_type": event_type,
    "duration_ms": duration,
    "correlation_id": request_id
})
```

### Metrics

**What to Measure**:
- Request latency (p50, p95, p99)
- Error rates
- Throughput (requests/second)
- Resource usage (CPU, memory)

**Prometheus Metrics**:
```python
from prometheus_client import Counter, Histogram

request_count = Counter('http_requests_total', 'Total requests')
request_latency = Histogram('http_request_duration_seconds', 'Request latency')
```

### Tracing

**Why**: Understand request flow across services

**OpenTelemetry**:
- Automatic instrumentation for common libraries
- Manual spans for custom operations
- Export to Jaeger, Zipkin, or cloud providers

## 🔒 Security Best Practices

### Secrets Management

**Never**:
- Commit secrets to git
- Hardcode credentials
- Log sensitive data

**Always**:
- Use environment variables or secret managers
- Rotate secrets regularly
- Use least-privilege access

### API Security

- Rate limiting to prevent abuse
- Authentication/authorization
- Input validation
- HTTPS in production

### Database Security

- Use parameterized queries (prevent SQL injection)
- Encrypt connections (TLS)
- Limit database user permissions
- Regular backups

## 🏗️ Code Organization

### Service Structure

```
service/
├── main.py              # Entry point, FastAPI app
├── models.py            # Pydantic models
├── handlers.py          # Business logic
├── clients.py           # External service clients
├── config.py            # Configuration (Pydantic Settings)
└── tests/               # Service tests
```

### Dependency Injection

**Why**: Testability, flexibility, clear dependencies

**Pattern**:
```python
def get_recommendations(
    user_id: str,
    redis_client: Redis = Depends(get_redis),
    vector_db: VectorDB = Depends(get_vector_db)
):
    # Use injected dependencies
    pass
```

## 🐛 Debugging Strategies

### Local Development

1. **Use Debugger**: `pdb` or IDE debugger
2. **Add Logging**: Temporary debug logs
3. **Test in Isolation**: Unit tests for specific functions
4. **Check Logs**: Structured logs are searchable

### Production Debugging

1. **Correlation IDs**: Trace requests across services
2. **Distributed Tracing**: See full request path
3. **Metrics Dashboards**: Identify anomalies
4. **Log Aggregation**: Centralized log search

## 📈 Performance Optimization

### Database Queries

- Use indexes on frequently queried columns
- Avoid N+1 queries (use joins or batch loading)
- Connection pooling
- Query result caching

### Caching Strategy

- **Cache-Aside**: Application manages cache
- **Write-Through**: Write to cache and DB
- **TTL**: Expire stale data
- **Invalidation**: Clear cache on updates

### Async Processing

- Use async/await for I/O-bound operations
- Background tasks for non-critical work
- Message queues for decoupling

## 🎓 Learning Resources

### Books

- "Designing Data-Intensive Applications" by Martin Kleppmann
- "Site Reliability Engineering" by Google
- "Building Microservices" by Sam Newman

### Online Courses

- Kubernetes: https://kubernetes.io/docs/tutorials/
- FastAPI: https://fastapi.tiangolo.com/tutorial/
- Apache Kafka: https://kafka.apache.org/documentation/

### Practice

- Build small projects to practice concepts
- Contribute to open source
- Read production codebases

## 💡 Common Pitfalls to Avoid

1. **Premature Optimization**: Measure first, optimize later
2. **Over-Engineering**: Start simple, add complexity when needed
3. **Ignoring Errors**: Always handle exceptions gracefully
4. **No Monitoring**: Can't fix what you can't see
5. **Tight Coupling**: Services should be independently deployable

## 🤝 Code Review Best Practices

### As a Reviewer

- Be constructive and kind
- Explain why, not just what
- Suggest alternatives
- Approve when ready

### As an Author

- Keep PRs small and focused
- Write clear commit messages
- Respond to feedback
- Test your changes

## 📝 Documentation

### Code Comments

- Explain **why**, not **what** (code should be self-documenting)
- Document complex algorithms
- Include examples for public APIs

### README Files

- Quick start guide
- Architecture overview
- Configuration options
- Troubleshooting section

---

**Remember**: The best code is code that others can understand and maintain. Write for your future self and your teammates.

