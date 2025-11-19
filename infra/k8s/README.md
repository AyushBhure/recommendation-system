# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying the recommendation system to AKS (Azure Kubernetes Service).

## Prerequisites

1. Azure CLI installed and configured
2. kubectl installed
3. AKS cluster created (see Terraform)
4. Docker images pushed to registry

## Setup

### 1. Create Namespace

```bash
kubectl apply -f namespace.yaml
```

### 2. Create Secrets

Create a secret with database credentials and other sensitive configuration:

```bash
kubectl create secret generic recommendation-secrets \
  --from-literal=postgres-host=your-postgres-host \
  --from-literal=postgres-user=your-postgres-user \
  --from-literal=postgres-password=your-postgres-password \
  --from-literal=redis-host=your-redis-host \
  --from-literal=kafka-brokers=your-kafka-brokers \
  --from-literal=mlflow-tracking-uri=your-mlflow-uri \
  --namespace=recommendation-system
```

### 3. Apply ConfigMap

```bash
kubectl apply -f configmap.yaml
```

### 4. Deploy Services

```bash
kubectl apply -f ingest-deployment.yaml
kubectl apply -f serve-deployment.yaml
kubectl apply -f stream-processor-deployment.yaml
```

### 5. Verify Deployment

```bash
kubectl get pods -n recommendation-system
kubectl get services -n recommendation-system
```

## Updating Deployments

```bash
# Update image
kubectl set image deployment/ingest-service ingest=ghcr.io/ayushbhure/recommendation-system/ingest:v1.1.0 -n recommendation-system

# Rollout status
kubectl rollout status deployment/ingest-service -n recommendation-system
```

## Troubleshooting

```bash
# View logs
kubectl logs -f deployment/ingest-service -n recommendation-system

# Describe pod
kubectl describe pod <pod-name> -n recommendation-system

# Exec into pod
kubectl exec -it <pod-name> -n recommendation-system -- /bin/bash
```

