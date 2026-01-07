"""Metrics and trend analysis models"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


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
                "outliers_removed": 3
            }
        }


class MetricsAnalysisResult(BaseModel):
    """Complete metrics analysis for an alert cluster"""
    cluster_id: str
    trends: List[MetricTrend] = Field(..., description="Analyzed metric trends")
    overall_health: TrendClassification = Field(..., description="Aggregate health status")
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    query_latency_ms: int = Field(..., description="Time taken for Prometheus queries")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = Field(default_factory=list, description="Any errors during analysis")
    
    @property
    def has_degrading_metrics(self) -> bool:
        """Check if any metrics are degrading"""
        return any(t.classification == TrendClassification.DEGRADING for t in self.trends)
    
    @property
    def is_reliable(self) -> bool:
        """Check if analysis is reliable (confidence > 0.7)"""
        return self.overall_confidence >= 0.7
