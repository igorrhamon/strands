# Strands Production Deployment Guide

This document provides comprehensive instructions for deploying the Strands agent system to production environments.

## Overview

The Strands production deployment includes:
- Kubernetes manifests for all components
- Helm charts for simplified deployment
- Prometheus monitoring and Grafana dashboards
- Security hardening and compliance measures
- Disaster recovery and backup procedures
- OpenAPI specification for API documentation
- Enhanced CI/CD pipeline with security scanning

## Quick Start

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured and authenticated
- Helm 3.0+
- Docker registry access

### Deployment Steps

#### 1. Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace strands

# Create secrets (update with your values)
kubectl create secret generic strands-secrets \
  --from-literal=neo4j_password=your-secure-password \
  --from-literal=api_key=your-api-key \
  --from-literal=jwt_secret=your-jwt-secret \
  -n strands
```

#### 2. Deploy with Helm

```bash
# Add Helm repository (if using remote chart)
helm repo add strands https://charts.example.com
helm repo update

# Install Strands
helm install strands ./helm/strands/ \
  --namespace strands \
  --values helm/strands/values.yaml

# Verify deployment
kubectl get pods -n strands
kubectl get svc -n strands
```

#### 3. Apply Kubernetes Manifests

```bash
# Apply ConfigMaps and Secrets
kubectl apply -f k8s/configmap-secrets.yaml

# Apply monitoring
kubectl apply -f k8s/prometheus-monitoring.yaml
kubectl apply -f k8s/grafana-dashboard.yaml
```

#### 4. Verify Deployment

```bash
# Check pod status
kubectl get pods -n strands

# Check logs
kubectl logs -n strands -l app=strands

# Test API
kubectl port-forward -n strands svc/strands-api 8000:80
curl http://localhost:8000/health
```

## Configuration

### Environment Variables

Key environment variables for production:

```bash
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<secure-password>
QDRANT_URL=http://qdrant:6333
PROMETHEUS_URL=http://prometheus:9090
API_KEY=<secure-api-key>
JWT_SECRET=<secure-jwt-secret>
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### Database Configuration

**Neo4j:**
- URI: bolt://neo4j:7687
- Default user: neo4j
- Change default password immediately

**Qdrant:**
- URL: http://qdrant:6333
- Ensure sufficient storage for embeddings

## Security

### Security Hardening

Review `SECURITY_HARDENING.md` for comprehensive security guidelines including:
- Input validation and sanitization
- Rate limiting
- Authentication and authorization
- HTTPS/TLS configuration
- Secrets management
- Dependency scanning

### Key Security Measures

1. **Network Policies:** Restrict traffic between pods
2. **RBAC:** Implement least privilege access
3. **Pod Security:** Use security contexts
4. **Secrets:** Use Kubernetes Secrets for sensitive data
5. **Monitoring:** Enable security event logging

## Monitoring

### Prometheus Metrics

Metrics are exposed on port 8001 at `/metrics` endpoint.

Key metrics:
- `agent_execution_duration_seconds`: Agent execution time
- `agent_errors_total`: Total agent errors
- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: HTTP request latency

### Grafana Dashboards

Access Grafana dashboards for visualization:
1. Port-forward to Grafana: `kubectl port-forward -n strands svc/grafana 3000:80`
2. Access: http://localhost:3000
3. Default credentials: admin/admin (change immediately)

### Alerting

PrometheusRules are configured for:
- High agent latency
- High error rates
- Database connection failures
- API availability
- Resource utilization

## Disaster Recovery

### Backup Strategy

Automated daily backups at 2:00 AM UTC:

```bash
# Manual backup
./scripts/backup.sh /backups/strands 30

# Automated backup (CronJob)
kubectl apply -f k8s/backup-cronjob.yaml
```

### Recovery Procedures

```bash
# Restore from backup
./scripts/restore.sh /backups/strands/strands_backup_20240120_100000 strands

# Verify restore
kubectl exec -n strands neo4j-0 -- cypher-shell -u neo4j "RETURN 1"
```

See `DISASTER_RECOVERY.md` for detailed recovery procedures.

## API Documentation

OpenAPI specification is available at `openapi_spec.yaml`.

To view interactive API documentation:

```bash
# Using Swagger UI
docker run -p 8080:8080 \
  -e SWAGGER_JSON=/openapi_spec.yaml \
  -v $(pwd)/openapi_spec.yaml:/openapi_spec.yaml \
  swaggerapi/swagger-ui

# Access at http://localhost:8080
```

## CI/CD Pipeline

The enhanced CI/CD pipeline includes:
- Security scanning (Bandit, Safety)
- Code quality checks (Flake8, Pylint)
- Unit and integration tests
- Docker image building
- Kubernetes manifest validation
- Automated deployment

### Triggering Deployments

**Development:**
```bash
git push origin develop
# Automatically deploys to development environment
```

**Production:**
```bash
git push origin main
# Requires approval, then deploys to production
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod -n strands <pod-name>

# Check logs
kubectl logs -n strands <pod-name>

# Check events
kubectl get events -n strands --sort-by='.lastTimestamp'
```

### Database Connection Issues

```bash
# Test Neo4j connectivity
kubectl exec -n strands neo4j-0 -- \
  cypher-shell -u neo4j "RETURN 1"

# Test Qdrant connectivity
kubectl exec -n strands qdrant-0 -- \
  curl -f http://localhost:6333/health
```

### High Memory Usage

```bash
# Check resource usage
kubectl top pods -n strands

# Adjust resource limits in values.yaml
helm upgrade strands ./helm/strands/ \
  --namespace strands \
  --set resources.limits.memory=4Gi
```

## Maintenance

### Regular Tasks

- **Daily:** Monitor logs and metrics
- **Weekly:** Review security alerts
- **Monthly:** Update dependencies
- **Quarterly:** Disaster recovery drill

### Updating Strands

```bash
# Update image
kubectl set image deployment/strands-api \
  strands-api=ghcr.io/igorrhamon/strands:v1.1.0 \
  -n strands

# Monitor rollout
kubectl rollout status deployment/strands-api -n strands
```

## Support

For issues and support:
- GitHub Issues: https://github.com/igorrhamon/strands/issues
- Documentation: https://github.com/igorrhamon/strands/wiki
- Email: support@strands.example.com

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Neo4j Operations Manual](https://neo4j.com/docs/operations-manual/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
