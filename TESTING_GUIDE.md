# Strands Observability Testing Guide

This guide explains how to run the complete observability stack for testing and validation.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+
- At least 4GB of available RAM
- Ports available: 3000, 6333, 6334, 6831, 6832, 7474, 7687, 8001, 9090, 11434, 14250, 16686

## Quick Start

### 1. Start the Docker Compose Stack

```bash
cd /home/ubuntu/strands
docker-compose -f docker-compose-test.yml up -d
```

This will start:
- **Prometheus** (http://localhost:9090) - Metrics database
- **Grafana** (http://localhost:3000) - Dashboards (admin/admin)
- **Jaeger** (http://localhost:16686) - Distributed tracing
- **Ollama** (http://localhost:11434) - Local LLM
- **Error Simulator** (http://localhost:8001) - Test application
- **Neo4j** (http://localhost:7474) - Graph database
- **Qdrant** (http://localhost:6333) - Vector database

### 2. Verify Services are Running

```bash
docker-compose -f docker-compose-test.yml ps
```

### 3. Run End-to-End Tests

```bash
python3 test_e2e.py
```

This will:
- Test Error Simulator metrics generation
- Verify Prometheus is scraping metrics
- Check Grafana accessibility
- Validate Jaeger tracing
- Test Ollama integration
- Verify alert rules configuration
- Test the complete metrics flow

## Component Details

### Error Simulator

The Error Simulator generates random errors and metrics to simulate production incidents.

**Endpoints:**
- `GET /health` - Health check
- `GET /simulate/{error_type}` - Manually trigger an error
- `GET /errors` - Get current active errors
- `GET /metrics` - Prometheus metrics endpoint

**Error Types:**
- `database_timeout`
- `network_error`
- `memory_leak`
- `cpu_spike`
- `disk_full`
- `auth_failure`
- `service_unavailable`

**Example:**
```bash
curl http://localhost:8001/simulate/database_timeout
curl http://localhost:8001/errors
```

### Prometheus

Prometheus scrapes metrics from the Error Simulator every 5 seconds.

**Access:** http://localhost:9090

**Useful Queries:**
```promql
# Error rate
rate(simulator_errors_total[5m])

# Active errors
simulator_active_errors

# Request latency (p95)
histogram_quantile(0.95, rate(simulator_request_duration_seconds_bucket[5m]))

# Error rate by type
rate(simulator_errors_total{error_type="database_timeout"}[5m])
```

### Grafana

Grafana provides visualization of metrics from Prometheus.

**Access:** http://localhost:3000
**Default Credentials:** admin / admin

**Dashboards:**
- Strands Agent System - Main dashboard with all metrics
- Error Simulator - Focused on simulator metrics

### Jaeger

Jaeger collects and visualizes distributed traces.

**Access:** http://localhost:16686

**Features:**
- Trace search by service
- Latency analysis
- Error tracking
- Dependency graph

### Ollama

Ollama provides local LLM capabilities.

**Access:** http://localhost:11434

**Setup:**
```bash
# Pull a model (e.g., mistral)
curl http://localhost:11434/api/pull -d '{"name": "mistral"}'

# List models
curl http://localhost:11434/api/tags

# Generate text
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Why is incident response important?"
}'
```

## Testing Workflow

### 1. Generate Errors

```bash
# Trigger multiple errors
for i in {1..10}; do
  curl http://localhost:8001/simulate/database_timeout &
done
```

### 2. Monitor in Prometheus

1. Go to http://localhost:9090
2. Query: `rate(simulator_errors_total[5m])`
3. Watch the error rate increase

### 3. View in Grafana

1. Go to http://localhost:3000
2. Navigate to "Strands Agent System" dashboard
3. Observe metrics updating in real-time

### 4. Check Traces in Jaeger

1. Go to http://localhost:16686
2. Select "error-simulator" service
3. View traces for each request

### 5. Test Alerts

Prometheus should trigger alerts when:
- Error rate > 0.1 errors/sec (HighErrorRate)
- Active errors > 5 (ActiveErrorsDetected)
- Database timeout rate > 0.05 errors/sec (DatabaseTimeoutErrors)

View alerts at: http://localhost:9090/alerts

## Troubleshooting

### Services not starting

```bash
# Check logs
docker-compose -f docker-compose-test.yml logs -f

# Rebuild images
docker-compose -f docker-compose-test.yml build --no-cache
```

### Metrics not appearing in Prometheus

1. Check Error Simulator is running: `curl http://localhost:8001/health`
2. Check Prometheus config: http://localhost:9090/config
3. Check targets: http://localhost:9090/targets

### Grafana dashboards not loading

1. Verify Prometheus datasource: http://localhost:3000/datasources
2. Check dashboard JSON files in `monitoring/dashboards/`

### Ollama not responding

1. Check if model is pulled: `curl http://localhost:11434/api/tags`
2. Pull a model: `curl http://localhost:11434/api/pull -d '{"name": "mistral"}'`
3. Note: First generation may take time as model loads

## Cleanup

```bash
# Stop all services
docker-compose -f docker-compose-test.yml down

# Remove volumes (data)
docker-compose -f docker-compose-test.yml down -v

# Remove images
docker-compose -f docker-compose-test.yml down --rmi all
```

## Next Steps

1. **Integrate with Strands**: Modify Strands agents to use `@instrument_agent` decorator
2. **Configure Alerts**: Set up alerting rules in Prometheus
3. **Create Dashboards**: Customize Grafana dashboards for your use case
4. **Enable Tracing**: Set `ENABLE_TRACING=true` for distributed tracing
5. **Use Ollama**: Integrate LLM for incident analysis

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Ollama Documentation](https://github.com/ollama/ollama)
