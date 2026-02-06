"""
Prometheus metrics definitions for Strands.

This module defines all custom metrics used across the application.
"""

from prometheus_client import Counter, Histogram, Gauge, Summary

# Agent Metrics
AGENT_EXECUTION_TIME = Histogram(
    'strands_agent_execution_seconds',
    'Time spent executing agent logic',
    ['agent_name', 'status']
)

AGENT_SUCCESS_RATE = Counter(
    'strands_agent_executions_total',
    'Total number of agent executions',
    ['agent_name', 'status']
)

AGENT_CONFIDENCE_SCORE = Histogram(
    'strands_agent_confidence_score',
    'Confidence scores returned by agents',
    ['agent_name'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Orchestrator Metrics
ORCHESTRATOR_ACTIVE_TASKS = Gauge(
    'strands_orchestrator_active_tasks',
    'Number of currently running tasks'
)

ORCHESTRATOR_QUEUE_DEPTH = Gauge(
    'strands_orchestrator_queue_depth',
    'Number of tasks waiting in queue'
)

ORCHESTRATOR_TASK_DURATION = Histogram(
    'strands_orchestrator_task_duration_seconds',
    'Total time to process a task from submission to completion',
    ['task_type']
)

# Decision Quality Metrics
DECISION_CONFIDENCE = Histogram(
    'strands_decision_confidence',
    'Final confidence score of aggregated decisions',
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
)

HUMAN_REVIEW_REQUIRED = Counter(
    'strands_human_review_required_total',
    'Total number of decisions requiring human review'
)

# System Resource Metrics (Application Level)
DB_CONNECTION_POOL_SIZE = Gauge(
    'strands_db_pool_size',
    'Current size of database connection pool',
    ['database']  # neo4j, qdrant
)

DB_QUERY_DURATION = Histogram(
    'strands_db_query_duration_seconds',
    'Time spent executing database queries',
    ['database', 'operation']
)

def init_metrics(app):
    """Initialize metrics endpoint for FastAPI app."""
    from prometheus_client import make_asgi_app
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
