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

    def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        logger.info(f"[{self.agent_id}] Analyzing metrics for {alert.service}...")
        
        hypothesis = "No significant metric anomalies detected."
        confidence = 0.5
        evidence = []
        
        # 1. Define dynamic queries based on alert service
        # Maps alert.service to Prometheus label selectors
        service_label = f'app="{alert.service}"'
        
        # Define a set of standard queries to run
        queries = {
            "availability": f'up{{{service_label}}}',
            "error_rate": f'rate(http_requests_total{{status=~"5..", {service_label}}}[5m])',
            "latency": f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{{service_label}}}[5m])) by (le))'
        }
        
        anomalies = []
        evidence = []
        
        try:
            now = datetime.now(timezone.utc)
            start = now - timedelta(minutes=10)
            
            for metric_name, query in queries.items():
                try:
                    result = self.prometheus.query_range(
                        query=query, 
                        start_time=start, 
                        end_time=now, 
                        step="30s"
                    )
                    
                    series_list = result.get("result", [])
                    if not series_list:
                        continue
                        
                    for s in series_list:
                        values = s.get("values", [])
                        if not values:
                            continue
                            
                        current_val = float(values[-1][1])
                        
                        # Basic anomaly detection logic
                        if metric_name == "availability" and current_val == 0:
                            anomalies.append(f"Service {alert.service} is DOWN (availability=0).")
                        elif metric_name == "error_rate" and current_val > 0.05: # > 5% error rate
                            anomalies.append(f"High error rate detected: {current_val:.2f} errors/sec.")
                        elif metric_name == "latency" and current_val > 2.0: # > 2s latency
                            anomalies.append(f"High P95 latency detected: {current_val:.2f}s.")
                            
                    evidence.append(EvidenceItem(
                        type=EvidenceType.METRIC,
                        description=f"Metric '{metric_name}' analyzed via query '{query}'.",
                        source_url=f"http://localhost:9090/graph?g0.expr={query}",
                        timestamp=now
                    ))
                    
                except Exception as q_err:
                    logger.warning(f"Failed to query {metric_name}: {q_err}")
                    continue

            if anomalies:
                hypothesis = f"Metrics anomalies detected for {alert.service}: " + "; ".join(anomalies)
                confidence = 0.9
            else:
                hypothesis = f"No significant anomalies found in standard metrics (Availability, Error Rate, Latency) for {alert.service}."
                confidence = 0.6
                 
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
