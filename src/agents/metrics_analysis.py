"""
Metrics Analysis Agent - Strands Agent Wrapper

Orchestrates metric retrieval and trend analysis for alert clusters.
Part of the multi-agent pipeline for alert decision support.
"""

import logging
from typing import Optional

from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend, DataPoint
from src.tools.prometheus_queries import (
    PrometheusClient,
    PromQLBuilder,
    build_service_cpu_query,
    build_service_memory_query,
    build_request_rate_query,
)
from src.rules.trend_rules import (
    TrendAnalyzer,
    TrendConfig,
    TrendRules,
)

logger = logging.getLogger(__name__)


class MetricsAnalysisAgent:
    """
    Agent responsible for:
    1. Fetching metric data for alert clusters
    2. Analyzing trends (DEGRADING/STABLE/RECOVERING)
    3. Providing enrichment data for decision engine
    
    This agent has NO LLM dependency - purely deterministic.
    """
    
    AGENT_NAME = "MetricsAnalysisAgent"
    TIMEOUT_SECONDS = 30.0
    
    # Default metrics to analyze per service
    DEFAULT_METRICS = ["cpu", "memory", "request_rate"]
    
    def __init__(
        self,
        prometheus_client: Optional[PrometheusClient] = None,
        trend_analyzer: Optional[TrendAnalyzer] = None,
        lookback_minutes: int = 15,
    ):
        """
        Initialize metrics analysis agent.
        
        Args:
            prometheus_client: Client for fetching metrics.
            trend_analyzer: Analyzer for trend classification.
            lookback_minutes: Time window for metric analysis.
        """
        self._prometheus = prometheus_client or PrometheusClient()
        self._analyzer = trend_analyzer or TrendAnalyzer(
            TrendConfig(lookback_minutes=lookback_minutes)
        )
        self._lookback = lookback_minutes
    
    def analyze_cluster_sync(
        self,
        cluster: AlertCluster,
        metrics: Optional[list[str]] = None,
    ) -> dict[str, MetricTrend]:
        """
        Synchronous wrapper for cluster analysis (for multi-agent tools).
        
        Args:
            cluster: AlertCluster to analyze.
            metrics: List of metric types to analyze.
        
        Returns:
            Dict mapping metric names to their trend analysis.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, return empty results
                logger.warning("[MetricsAnalysisAgent] Cannot run async in event loop")
                return {}
        except RuntimeError:
            pass
        
        return asyncio.run(self.analyze_cluster(cluster, metrics))
    
    async def analyze_cluster(
        self,
        cluster: AlertCluster,
        metrics: Optional[list[str]] = None,
    ) -> dict[str, MetricTrend]:
        """
        Analyze metrics for an alert cluster.
        
        Args:
            cluster: AlertCluster to analyze.
            metrics: List of metric types to analyze (default: cpu, memory, request_rate).
        
        Returns:
            Dict mapping metric names to their trend analysis.
        """
        if metrics is None:
            metrics = self.DEFAULT_METRICS
        
        logger.info(
            f"[{self.AGENT_NAME}] Analyzing {len(metrics)} metrics for "
            f"cluster {cluster.cluster_id} (service: {cluster.primary_service})"
        )
        
        results = {}
        
        for metric_type in metrics:
            try:
                trend = await self._analyze_metric(
                    service=cluster.primary_service,
                    metric_type=metric_type,
                )
                results[metric_type] = trend
                logger.debug(
                    f"[{self.AGENT_NAME}] {metric_type}: {trend.trend_state.value} "
                    f"(confidence: {trend.confidence:.2f})"
                )
            except Exception as e:
                logger.warning(
                    f"[{self.AGENT_NAME}] Failed to analyze {metric_type}: {e}"
                )
        
        return results
    
    async def _analyze_metric(
        self,
        service: str,
        metric_type: str,
    ) -> MetricTrend:
        """
        Analyze a specific metric for a service.
        
        Args:
            service: Service name.
            metric_type: Type of metric (cpu, memory, request_rate).
        
        Returns:
            MetricTrend with analysis results.
        """
        # Build query based on metric type
        if metric_type == "cpu":
            expr = build_service_cpu_query(service)
            metric_name = f"{service}_cpu_usage"
        elif metric_type == "memory":
            expr = build_service_memory_query(service)
            metric_name = f"{service}_memory_usage"
        elif metric_type == "request_rate":
            expr = build_request_rate_query(service)
            metric_name = f"{service}_request_rate"
        else:
            # Custom metric
            expr = PromQLBuilder(metric_type).with_label("service", service).build()
            metric_name = f"{service}_{metric_type}"
        
        # Fetch data
        data_points = await self._prometheus.query_range(expr=expr)
        
        # Analyze trend
        return self._analyzer.analyze(metric_name, data_points)
    
    def get_enrichment_summary(
        self,
        trends: dict[str, MetricTrend],
    ) -> dict:
        """
        Generate enrichment data for decision engine.
        
        Args:
            trends: Dict of metric trends.
        
        Returns:
            Dict with summary suitable for decision context.
        """
        trend_list = list(trends.values())
        
        return {
            "trend_count": len(trend_list),
            "should_escalate": TrendRules.should_escalate(trend_list),
            "can_auto_close": TrendRules.can_auto_close(trend_list),
            "summary": TrendRules.get_trend_summary(trend_list),
            "degrading_metrics": [
                t.metric_name for t in trend_list 
                if t.trend_state.value == "DEGRADING"
            ],
            "recovering_metrics": [
                t.metric_name for t in trend_list 
                if t.trend_state.value == "RECOVERING"
            ],
        }


# Strands agent tool definition
METRICS_ANALYSIS_TOOL = {
    "name": "metrics_analysis",
    "description": "Analyze metric trends for an alert cluster",
    "parameters": {
        "type": "object",
        "properties": {
            "cluster_id": {
                "type": "string",
                "description": "ID of the cluster to analyze",
            },
            "service": {
                "type": "string",
                "description": "Service name for metric queries",
            },
            "metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Metric types to analyze (default: cpu, memory, request_rate)",
            },
        },
        "required": ["service"],
    },
}


class MetricsAnalysisAgentSync:
    """Synchronous wrapper methods for MetricsAnalysisAgent."""
    
    def __init__(self, agent: MetricsAnalysisAgent):
        self.agent = agent
    
    def analyze_cluster_sync(
        self,
        cluster: AlertCluster,
        metrics: Optional[list[str]] = None,
    ) -> dict[str, MetricTrend]:
        """
        Synchronous wrapper for cluster analysis (for multi-agent tools).
        
        Args:
            cluster: AlertCluster to analyze.
            metrics: List of metric types to analyze.
        
        Returns:
            Dict mapping metric names to their trend analysis.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, return empty results
                logger.warning("[MetricsAnalysisAgent] Cannot run async in event loop")
                return {}
        except RuntimeError:
            pass
        
        return asyncio.run(self.agent.analyze_cluster(cluster, metrics))



async def execute_metrics_tool(
    service: str,
    metrics: Optional[list[str]] = None,
) -> dict:
    """
    Tool execution function for Strands integration.
    
    Returns dict format expected by Strands agent framework.
    """
    agent = MetricsAnalysisAgent()
    
    # Create a minimal cluster for analysis
    from src.models.alert import Alert, NormalizedAlert, ValidationStatus
    from datetime import datetime, timezone
    
    # Mock cluster for service-based analysis
    mock_alert = NormalizedAlert(
        timestamp=datetime.now(timezone.utc),
        fingerprint="mock",
        service=service,
        severity="warning",
        description="Mock alert for metrics analysis",
        labels={},
        validation_status=ValidationStatus.VALID,
        validation_errors=None,
    )
    
    from src.models.cluster import AlertCluster
    cluster = AlertCluster.from_alerts([mock_alert], correlation_score=1.0)
    
    trends = await agent.analyze_cluster(cluster, metrics)
    return agent.get_enrichment_summary(trends)
