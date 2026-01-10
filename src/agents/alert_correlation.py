"""
Alert Correlation Agent - Strands Agent Wrapper

Orchestrates alert collection, normalization, and clustering.
Part of the multi-agent pipeline for alert decision support.
"""

import logging
from typing import Optional

from src.models.alert import Alert, NormalizedAlert
from src.models.cluster import AlertCluster
from src.models.cluster import AlertCluster
from src.tools.grafana_mcp import GrafanaMCPClient, GrafanaClientError
from src.utils.alert_normalizer import AlertNormalizer
from src.rules.correlation_rules import CorrelationEngine, CorrelationConfig

logger = logging.getLogger(__name__)


class AlertCorrelationAgent:
    """
    Agent responsible for:
    1. Collecting alerts from Grafana
    2. Normalizing to canonical format
    3. Clustering related alerts
    
    This agent has NO LLM dependency - purely deterministic.
    """
    
    AGENT_NAME = "AlertCorrelationAgent"
    TIMEOUT_SECONDS = 30.0
    
    def __init__(
        self,
        grafana_client: Optional[GrafanaMCPClient] = None,
        normalizer: Optional[AlertNormalizer] = None,
        correlation_engine: Optional[CorrelationEngine] = None,
        time_window_minutes: int = 5,
    ):
        """
        Initialize alert correlation agent.
        
        Args:
            grafana_client: Client for fetching alerts.
            normalizer: Alert normalizer.
            correlation_engine: Clustering engine.
            time_window_minutes: Time window for correlation.
        """
        self._grafana = grafana_client or GrafanaMCPClient()
        self._normalizer = normalizer or AlertNormalizer()
        self._correlation = correlation_engine or CorrelationEngine(
            CorrelationConfig(time_window_minutes=time_window_minutes)
        )
    
    async def collect_and_correlate(
        self,
        lookback_minutes: int = 60,
    ) -> list[AlertCluster]:
        """
        Full pipeline: collect → normalize → correlate.
        
        Args:
            lookback_minutes: Time window for alert collection.
        
        Returns:
            List of correlated AlertCluster objects.
        """
        logger.info(f"[{self.AGENT_NAME}] Starting collection for last {lookback_minutes} minutes")
        
        # Step 1: Collect raw alerts
        try:
            raw_alerts = self._grafana.fetch_alerts()
            logger.info(f"[{self.AGENT_NAME}] Collected {len(raw_alerts)} raw alerts")
        except GrafanaClientError as e:
            logger.error(f"[{self.AGENT_NAME}] Failed to collect alerts: {e}")
            return []
        
        if not raw_alerts:
            logger.info(f"[{self.AGENT_NAME}] No alerts found")
            return []
        
        # Step 2: Normalize alerts
        normalized = self._normalizer.normalize_batch(raw_alerts)
        valid_count = sum(1 for a in normalized if a.validation_status.value == "VALID")
        logger.info(f"[{self.AGENT_NAME}] Normalized {len(normalized)} alerts ({valid_count} valid)")
        
        # Step 3: Correlate into clusters
        clusters = self._correlation.correlate(normalized)
        logger.info(f"[{self.AGENT_NAME}] Created {len(clusters)} clusters")
        
        return clusters
    
    def correlate_existing(self, alerts: list[Alert]) -> list[AlertCluster]:
        """
        Correlate a list of existing alerts (no Grafana fetch).
        
        Args:
            alerts: Pre-fetched Alert objects.
        
        Returns:
            List of AlertCluster objects.
        """
        normalized = self._normalizer.normalize_batch(alerts)
        return self._correlation.correlate(normalized)
    
    def correlate(self, alerts: list[NormalizedAlert]) -> list[AlertCluster]:
        """
        Correlate a list of normalized alerts using instance time window.
        
        Args:
            alerts: List of NormalizedAlert objects to correlate.
        
        Returns:
            List of AlertCluster objects.
        """
        return self._correlation.correlate(alerts)
    
    def normalize_only(self, alerts: list[Alert]) -> list[NormalizedAlert]:
        """
        Normalize alerts without clustering.
        
        Args:
            alerts: Raw Alert objects.
        
        Returns:
            List of NormalizedAlert objects.
        """
        return self._normalizer.normalize_batch(alerts)


# Strands agent tool definition
ALERT_CORRELATION_TOOL = {
    "name": "alert_correlation",
    "description": "Collect and correlate Grafana alerts into related clusters",
    "parameters": {
        "type": "object",
        "properties": {
            "lookback_minutes": {
                "type": "integer",
                "description": "Time window for alert collection (default: 60)",
                "default": 60,
            },
            "severity_filter": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by severity levels (e.g., ['critical', 'warning'])",
            },
        },
    },
}


async def execute_correlation_tool(
    lookback_minutes: int = 60,
    severity_filter: Optional[list[str]] = None,
) -> dict:
    """
    Tool execution function for Strands integration.
    
    Returns dict format expected by Strands agent framework.
    """
    agent = AlertCorrelationAgent()
    clusters = await agent.collect_and_correlate(
        lookback_minutes=lookback_minutes,
        severity_filter=severity_filter,
    )
    
    return {
        "cluster_count": len(clusters),
        "clusters": [
            {
                "cluster_id": str(c.cluster_id),
                "alert_count": c.alert_count,
                "primary_service": c.primary_service,
                "primary_severity": c.primary_severity,
                "correlation_score": c.correlation_score,
            }
            for c in clusters
        ],
    }
