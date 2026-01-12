"""Metrics and trend analysis models"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# Import the enhanced MetricTrend from metric_trend module
from src.models.metric_trend import MetricTrend as MetricTrendEnhanced, TrendState


class TrendClassification(str, Enum):
    """Metric trend classifications"""

    DEGRADING = "degrading"
    STABLE = "stable"
    RECOVERING = "recovering"
    INSUFFICIENT_DATA = "insufficient_data"


class MetricTrend(BaseModel):
    """Analyzed metric trend"""

    metric_name: str = Field(..., description="Prometheus metric name")
    query: str = Field(..., description="PromQL query used")
    classification: TrendClassification
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in classification")
    slope: Optional[float] = Field(None, description="Linear regression slope")
    p_value: Optional[float] = Field(None, description="Mann-Kendall test p-value")
    data_points: int = Field(..., description="Number of data points analyzed")
    time_range_seconds: int = Field(..., description="Time range of analysis")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    outliers_removed: int = Field(0, description="Number of outliers filtered (p95)")

    class Config:
        json_schema_extra = {
            "example": {
                "metric_name": "cpu_usage_percent",
                "query": "rate(cpu_usage[5m])",
                "classification": "degrading",
                "confidence": 0.85,
                "slope": 0.05,
                "p_value": 0.001,
                "data_points": 120,
                "time_range_seconds": 3600,
                "outliers_removed": 3,
            }
        }


class MetricsAnalysisResult(BaseModel):
    """Complete metrics analysis for an alert cluster (FR-008 enhanced)"""

    cluster_id: str
    service: str = Field("unknown", description="Primary service being analyzed")
    # Accept either dict or list of MetricTrendEnhanced for test flexibility.
    # Tests sometimes pass a list of MetricTrend objects; convert in post-init.
    trends: Dict | list = Field(default_factory=dict, description="Dict or list of analyzed trends")
    overall_health: TrendClassification = Field(..., description="Aggregate health status")
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    query_latency_ms: int = Field(..., description="Total query latency in milliseconds (FR-008)")
    metrics_available_count: int = Field(0, description="Number of metrics requested")
    metrics_queried_count: int = Field(0, description="Number of metrics successfully queried")
    prometheus_errors: List[str] = Field(
        default_factory=list, description="List of errors encountered (FR-008)"
    )
    retry_summary: Dict = Field(
        default_factory=dict, description="Retry statistics from Prometheus client (FR-008)"
    )
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: dict) -> None:  # type: ignore[override]
        # Allow tests to pass a list of trends; convert to dict keyed by metric_name
        # If tests provided a list, convert to dict by metric_name
        if isinstance(self.trends, list):
            d: Dict[str, object] = {}
            for t in self.trends:
                # t may be a dict or MetricTrendEnhanced model
                if hasattr(t, "metric_name"):
                    key = t.metric_name
                elif isinstance(t, dict) and "metric_name" in t:
                    key = t["metric_name"]
                else:
                    # Skip malformed entries
                    continue
                d[key] = t
            self.trends = d

    @property
    def has_degrading_metrics(self) -> bool:
        """Check if any metrics are degrading"""
        if isinstance(self.trends, dict):
            return any(t.trend_state == TrendState.DEGRADING for t in self.trends.values())
        return False

    @property
    def is_reliable(self) -> bool:
        """Check if analysis is reliable (confidence > 0.7)"""
        return self.overall_confidence >= 0.7
