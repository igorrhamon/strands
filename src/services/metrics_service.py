"""
Metrics Service - Prometheus Observability for Strands
Exposes operational metrics for monitoring and governance.
"""

import logging
import os
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from typing import Optional

logger = logging.getLogger(__name__)

class MetricsService:
    """
    Handles Prometheus metrics for the Strands platform.
    """
    
    # Singleton instance
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MetricsService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, port: Optional[int] = None):
        if self._initialized:
            return
            
        # Port configurable via ENV or parameter, default to 9090
        self.port = port or int(os.getenv("STRANDS_METRICS_PORT", 9090))
        
        # 1. Execution Metrics
        self.swarm_execution_time = Histogram(
            'strands_swarm_execution_seconds',
            'Time spent executing a swarm run',
            ['domain', 'risk_level']
        )
        
        # 2. Decision Metrics
        # Custom buckets for granular confidence analysis
        self.decision_confidence = Histogram(
            'strands_decision_confidence_score',
            'Confidence scores of generated decisions',
            ['decision_state'],
            buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        self.human_override_rate = Counter(
            'strands_human_override_total',
            'Total number of human overrides (confirm/reject)',
            ['status'] # confirmed, rejected
        )
        
        # 3. Deduplication Metrics
        self.deduplication_events = Counter(
            'strands_deduplication_total',
            'Total events processed by deduplicator',
            ['action'] # new_execution, update_existing, skip
        )
        
        # 4. RAG Metrics
        self.rag_similarity_score = Histogram(
            'strands_rag_similarity_score',
            'Similarity scores for RAG retrieval',
            ['source'] # runbooks, past_decisions
        )
        
        self._initialized = True
        logger.info(f"[METRICS] Initialized Prometheus metrics (Port: {self.port}, Custom Buckets: Enabled)")

    def start_server(self):
        """Starts the Prometheus metrics server."""
        try:
            start_http_server(self.port)
            logger.info(f"[METRICS] Prometheus server started on port {self.port}")
        except Exception as e:
            logger.error(f"[METRICS] Failed to start Prometheus server on port {self.port}: {e}")

    def record_execution(self, duration: float, domain: str, risk: str):
        self.swarm_execution_time.labels(domain=domain, risk_level=risk).observe(duration)

    def record_decision(self, score: float, state: str):
        self.decision_confidence.labels(decision_state=state).observe(score)

    def record_override(self, status: str):
        self.human_override_rate.labels(status=status).inc()

    def record_dedup(self, action: str):
        self.deduplication_events.labels(action=action).inc()

    def record_rag(self, score: float, source: str):
        self.rag_similarity_score.labels(source=source).observe(score)
