"""
Metrics Analysis Agent - Strands Agent Wrapper

Orchestrates metric retrieval and trend analysis for alert clusters.
Part of the multi-agent pipeline for alert decision support.
"""

import logging
import time
from typing import Optional

from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend, DataPoint, TrendState
from src.models.metrics import MetricsAnalysisResult
from src.tools.prometheus_queries import (
    PrometheusClient,
    PromQLBuilder,
    build_service_cpu_query,
    build_service_memory_query,
    build_request_rate_query,
    query_multiple_metrics,
)
from src.rules.trend_rules import (
    TrendAnalyzer,
    TrendConfig,
    TrendRules,
    fuse_trends,
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
    ) -> MetricsAnalysisResult:
        """
        Synchronous wrapper for cluster analysis (for multi-agent tools).
        
        Args:
            cluster: AlertCluster to analyze.
            metrics: List of metric types to analyze.
        
        Returns:
            MetricsAnalysisResult with trends and metadata.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, return empty result
                logger.warning("[MetricsAnalysisAgent] Cannot run async in event loop")
                from src.models.metrics import TrendClassification
                return MetricsAnalysisResult(
                    cluster_id=str(cluster.cluster_id),
                    service=cluster.primary_service,
                    trends={},
                    overall_health=TrendClassification.INSUFFICIENT_DATA,
                    overall_confidence=0.0,
                    query_latency_ms=0,
                    metrics_available_count=0,
                    metrics_queried_count=0,
                    prometheus_errors=["Cannot run async in running event loop"],
                    retry_summary={},
                )
        except RuntimeError:
            pass
        
        return asyncio.run(self.analyze_cluster(cluster, metrics))
    
    async def analyze_cluster(
        self,
        cluster: AlertCluster,
        metrics: Optional[list[str]] = None,
        enable_fusion: bool = True,
    ) -> MetricsAnalysisResult:
        """
        Analyze metrics for an alert cluster with optional multi-metric fusion.
        
        Enhanced to use parallel queries and multi-metric fusion (FR-009).
        
        Args:
            cluster: AlertCluster to analyze.
            metrics: List of metric types to analyze (default: cpu, memory, request_rate).
            enable_fusion: If True and len(metrics)>1, fuse trends using priority-based logic.
        
        Returns:
            MetricsAnalysisResult with trends and query metadata.
        """
        if metrics is None:
            metrics = self.DEFAULT_METRICS
        
        logger.info(
            f"[{self.AGENT_NAME}] Analyzing {len(metrics)} metrics for "
            f"cluster {cluster.cluster_id} (service: {cluster.primary_service})"
        )
        
        # Track query performance
        start_time = time.time()
        prometheus_errors = []
        metrics_available_count = len(metrics)
        
        # Build metric names for query_multiple_metrics
        metric_types_list = list(metrics)
        
        # Execute queries in parallel using query_multiple_metrics (FR-012)
        try:
            results_dict = await query_multiple_metrics(
                client=self._prometheus,
                service_id=cluster.primary_service,
                metric_names=metric_types_list,
                lookback_minutes=self._lookback,
            )
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Parallel query failed: {e}")
            prometheus_errors.append(f"Parallel query failed: {str(e)}")
            results_dict = {}
        
        # Analyze individual metric trends
        trends = {}
        for metric_type in metric_types_list:
            if metric_type in results_dict and results_dict[metric_type]:
                data_points = results_dict[metric_type]
                metric_name = f"{cluster.primary_service}_{metric_type}"
                try:
                    trend = self._analyzer.analyze(metric_name, data_points)
                    trends[metric_type] = trend
                    logger.debug(
                        f"[{self.AGENT_NAME}] {metric_type}: {trend.trend_state.name} "
                        f"(confidence: {trend.confidence:.2f})"
                    )
                except Exception as e:
                    error_msg = f"Failed to analyze {metric_type}: {str(e)}"
                    logger.warning(f"[{self.AGENT_NAME}] {error_msg}")
                    prometheus_errors.append(error_msg)
            else:
                error_msg = f"No data returned for {metric_type}"
                logger.warning(f"[{self.AGENT_NAME}] {error_msg}")
                prometheus_errors.append(error_msg)
        
        metrics_queried_count = len(trends)
        
        # Apply multi-metric fusion if enabled and multiple metrics (FR-009)
        fused_state = TrendState.UNKNOWN
        fused_confidence = 0.0
        if enable_fusion and len(trends) > 1:
            fused_trend = self._fuse_metric_trends(trends, cluster)
            trends["_fused"] = fused_trend  # Add fused trend to results
            fused_state = fused_trend.trend_state
            fused_confidence = fused_trend.confidence
        elif len(trends) == 1:
            # Single metric - use its state
            single_trend = list(trends.values())[0]
            fused_state = single_trend.trend_state
            fused_confidence = single_trend.confidence
        
        query_latency_ms = int((time.time() - start_time) * 1000)
        
        # Map TrendState to TrendClassification for overall_health
        from src.models.metrics import TrendClassification
        health_mapping = {
            TrendState.DEGRADING: TrendClassification.DEGRADING,
            TrendState.STABLE: TrendClassification.STABLE,
            TrendState.RECOVERING: TrendClassification.RECOVERING,
            TrendState.UNKNOWN: TrendClassification.INSUFFICIENT_DATA,
        }
        overall_health = health_mapping.get(fused_state, TrendClassification.INSUFFICIENT_DATA)
        
        # Build MetricsAnalysisResult (FR-008)
        return MetricsAnalysisResult(
            cluster_id=str(cluster.cluster_id),
            service=cluster.primary_service,
            trends=trends,
            overall_health=overall_health,
            overall_confidence=fused_confidence,
            query_latency_ms=query_latency_ms,
            metrics_available_count=metrics_available_count,
            metrics_queried_count=metrics_queried_count,
            prometheus_errors=prometheus_errors,
            retry_summary=self._get_retry_summary(),
        )
    
    def _build_query(self, service: str, metric_type: str) -> tuple[str, str]:
        """
        Build PromQL query and metric name for a given metric type.
        
        Args:
            service: Service name.
            metric_type: Type of metric (cpu, memory, request_rate).
        
        Returns:
            (query_expression, metric_name)
        """
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
        
        return expr, metric_name
    
    def _fuse_metric_trends(
        self, trends: dict[str, MetricTrend], cluster: AlertCluster
    ) -> MetricTrend:
        """
        Fuse multiple metric trends using priority-based logic (FR-009).
        
        Args:
            trends: Dict of individual metric trends.
            cluster: AlertCluster being analyzed.
        
        Returns:
            Fused MetricTrend with combined state and confidence.
        """
        # Extract trend states and confidences
        trend_tuples = [(t.trend_state, t.confidence) for t in trends.values()]
        
        # Apply fusion logic
        fused_state, fused_confidence = fuse_trends(trend_tuples)
        
        # Build reasoning string
        individual_summaries = [
            f"{name}: {t.trend_state.name} (conf={t.confidence:.2f})"
            for name, t in trends.items()
        ]
        reasoning = (
            f"Fused from {len(trends)} metrics using priority_weighted logic. "
            f"Individual trends: {', '.join(individual_summaries)}. "
            f"Result: {fused_state.name} (conf={fused_confidence:.2f})"
        )
        
        # Create fused MetricTrend
        return MetricTrend(
            metric_name=f"{cluster.primary_service}_fused",
            trend_state=fused_state,
            confidence=fused_confidence,
            data_points=[],  # No raw data points for fused trend
            lookback_minutes=self._lookback,
            threshold_value=None,
            current_value=None,
            data_points_total=sum(t.data_points_total for t in trends.values()),
            data_points_used=sum(t.data_points_used for t in trends.values()),
            outliers_removed=sum(t.outliers_removed for t in trends.values()),
            reasoning=reasoning,
            time_window_seconds=self._lookback * 60,
            fusion_method="priority_weighted",
        )
    
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
        
        # Fetch data (use async version)
        data_points = await self._prometheus.query_range_async(expr=expr)
        
        # Analyze trend
        return self._analyzer.analyze(metric_name, data_points)
    
    def _get_retry_summary(self) -> dict:
        """
        Get retry summary from Prometheus client.
        
        Returns:
            Dict with retry statistics (if available).
        """
        # Check if prometheus client has retry stats
        if hasattr(self._prometheus, '_retry_count'):
            return {
                "total_retries": getattr(self._prometheus, '_retry_count', 0),
                "failed_after_retry": getattr(self._prometheus, '_failed_count', 0),
            }
        return {"total_retries": 0, "failed_after_retry": 0}
    
    def get_enrichment_summary(
        self,
        result: MetricsAnalysisResult,
    ) -> dict:
        """
        Generate enrichment data for decision engine.
        
        Args:
            result: MetricsAnalysisResult with trends and metadata.
        
        Returns:
            Dict with summary suitable for decision context.
        """
        trend_list = list(result.trends.values()) if isinstance(result.trends, dict) else result.trends
        
        return {
            "trend_count": len(trend_list),
            "should_escalate": TrendRules.should_escalate(trend_list),
            "can_auto_close": TrendRules.can_auto_close(trend_list),
            "summary": TrendRules.get_trend_summary(trend_list),
            "degrading_metrics": [
                t.metric_name for t in trend_list 
                if t.trend_state == TrendState.DEGRADING
            ],
            "recovering_metrics": [
                t.metric_name for t in trend_list 
                if t.trend_state == TrendState.RECOVERING
            ],
            # Add metrics metadata
            "query_latency_ms": result.query_latency_ms,
            "metrics_success_rate": (
                result.metrics_queried_count / result.metrics_available_count
                if result.metrics_available_count > 0 else 0
            ),
            "has_errors": len(result.prometheus_errors) > 0,
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
            Dict mapping metric names to their trend analysis (for backward compatibility).
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
        
        result = asyncio.run(self.agent.analyze_cluster(cluster, metrics))
        # Return only trends dict for backward compatibility
        return result.trends



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
