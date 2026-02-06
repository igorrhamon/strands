# Strands Observability & SLOs

This document defines the observability strategy, Service Level Objectives (SLOs), and Service Level Indicators (SLIs) for the Strands agent system.

## 1. Observability Strategy

Strands uses a three-pillar approach to observability:

### Metrics (Prometheus)
- **Application Metrics**: Custom metrics for agent performance, confidence scores, and orchestration health.
- **System Metrics**: CPU, memory, network usage from Kubernetes.
- **Business Metrics**: Incident resolution rate, human review frequency.

### Tracing (OpenTelemetry)
- **Distributed Tracing**: End-to-end tracing of incident analysis workflows.
- **Span Context**: Propagation of trace IDs across async tasks and agent executions.
- **Performance Profiling**: Identification of bottlenecks in agent logic.

### Logs (Structured Logging)
- **JSON Format**: All logs are structured for easy parsing by ELK/Loki.
- **Correlation IDs**: Trace IDs included in logs to link with traces.
- **Audit Trail**: Decision logs for compliance and post-incident review.

## 2. Service Level Objectives (SLOs)

### API Availability
- **SLO**: 99.9% availability (monthly)
- **SLI**: `(total_requests - 5xx_errors) / total_requests`
- **Error Budget**: 43 minutes/month

### Incident Analysis Latency
- **SLO**: 95% of analyses completed within 30 seconds
- **SLI**: `histogram_quantile(0.95, strands_orchestrator_task_duration_seconds)`
- **Threshold**: < 30s

### Decision Confidence
- **SLO**: 90% of automated decisions have confidence > 0.8
- **SLI**: `count(decision_confidence > 0.8) / total_decisions`
- **Action**: If breached, retrain models or adjust heuristics.

### Agent Success Rate
- **SLO**: 99% success rate for individual agent executions
- **SLI**: `rate(strands_agent_executions_total{status="success"}) / rate(strands_agent_executions_total)`

## 3. Alerting Rules

| Alert Name | Condition | Severity | Response |
|------------|-----------|----------|----------|
| `HighErrorRate` | Error rate > 1% for 5m | Critical | Page on-call |
| `HighLatency` | p95 latency > 30s for 5m | Warning | Investigate |
| `LowConfidence` | Avg confidence < 0.7 for 1h | Warning | Review models |
| `QueueBacklog` | Queue depth > 100 for 5m | Critical | Scale workers |
| `AgentFailure` | Agent failure rate > 5% | High | Check dependencies |

## 4. Dashboards

### Main Dashboard (Grafana)
- **System Health**: Global status, active incidents, worker pool utilization.
- **Key Metrics**: Request rate, error rate, latency (RED method).
- **Business KPIs**: Incidents resolved, average resolution time.

### Agent Performance Dashboard
- **Per-Agent Metrics**: Execution time, success rate, confidence distribution.
- **Resource Usage**: CPU/Memory per agent type.
- **Dependency Health**: Neo4j/Qdrant query latency.

### Debugging Dashboard
- **Trace Lookup**: Search traces by incident ID.
- **Log Stream**: Live logs filtered by error severity.
- **Queue Metrics**: Enqueue/dequeue rates, processing time.

## 5. Implementation Details

### Instrumentation
Agents are instrumented using the `@instrument_agent` decorator:

```python
from src.instrumentation import instrument_agent

@instrument_agent("log_inspector")
async def analyze_logs(pod_name: str):
    # ... logic ...
```

### Tracing
OpenTelemetry is configured in `src/tracing.py` and enabled via `ENABLE_TRACING=true`.

### Metrics Endpoint
Prometheus metrics are exposed at `/metrics` on port 8000.
