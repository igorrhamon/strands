"""
Metrics Analysis Agent

Analyzes time-series data related to the alert.
Wraps: src/tools/prometheus_client.py
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType
from src.tools.prometheus_client import PrometheusClient

logger = logging.getLogger(__name__)

class MetricsAnalysisAgent:
    agent_id = "metrics_analysis"
    
    def __init__(self):
        # Fallback URL if config logic isn't fully wired or env var missing
        self.prometheus = PrometheusClient(base_url="http://localhost:9090")

    async def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        logger.info(f"[{self.agent_id}] Analyzing metrics for {alert.service}...")
        
        hypothesis = "No significant metric anomalies detected."
        confidence = 0.5
        evidence = []
        
        # 1. Define query based on alert metadata if possible
        # Defaulting to a generic CPU query for demonstration
        # In prod this would map `alert.service` to specific job/pod labels
        query = "up"  # Simple 'up' check for demo to ensure we get data
        
        try:
            now = datetime.now(timezone.utc)
            start = now - timedelta(minutes=10)
            
            # Using synchronous client method (wrapper might need refactor to async later)
            result = self.prometheus.query_range(
                query=query, 
                start_time=start, 
                end_time=now, 
                step="30s"
            )
            
            series_list = result.get("result", [])
            if series_list:
                # Basic logic: if we have data, we assume something is happening (demo logic)
                hypothesis = f"Successfully queried metrics. Found {len(series_list)} time series for '{query}'."
                confidence = 0.7
                
                # Check for flapping or down
                # Example: checking values
                for s in series_list:
                     values = s.get("values", [])
                     if values and values[-1][1] == "1":
                         hypothesis += " Service appears UP."
                         confidence = 0.8
                     else:
                         hypothesis = "Service appears DOWN."
                         confidence = 0.95
                         
                evidence.append(EvidenceItem(
                    type=EvidenceType.METRIC,
                    description=f"Prometheus Query '{query}' returned {len(series_list)} series.",
                    source_url=f"http://localhost:9090/graph?g0.expr={query}",
                    timestamp=now
                ))
            else:
                 hypothesis = "No metrics found for query."
                 confidence = 0.3
                 
        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            hypothesis = f"Failed to query metrics: {str(e)}"
            confidence = 0.0

        return SwarmResult(
            agent_id=self.agent_id,
            hypothesis=hypothesis,
            confidence=confidence,
            evidence=evidence,
            suggested_actions=["Check Prometheus targets"]
        )
            
        evidence = [
            EvidenceItem(
                type=EvidenceType.METRIC,
                description=f"95th percentile {alert.labels.get('metric', 'cpu')} > threshold",
                source_url="http://grafana/d/123",
                timestamp=datetime.now(timezone.utc)
            )
        ]

        return SwarmResult(
            agent_id=self.agent_id,
            hypothesis=hypothesis,
            confidence=confidence,
            evidence=evidence,
            suggested_actions=["Check container resource limits", "Profile heap usage"]
        )
