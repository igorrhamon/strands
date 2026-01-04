"""
MetricTrend Model - Computed Trend State

Represents the analysis of a specific metric over time.
Used to determine if a metric is degrading, stable, or recovering.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TrendState(str, Enum):
    """Possible trend states for a metric."""
    DEGRADING = "DEGRADING"
    STABLE = "STABLE"
    RECOVERING = "RECOVERING"
    UNKNOWN = "UNKNOWN"  # When insufficient data


class DataPoint(BaseModel):
    """Single point in a time series."""
    timestamp: datetime
    value: float
    
    class Config:
        frozen = True


class MetricTrend(BaseModel):
    """
    Analysis of a specific metric over time.
    
    Created by TrendAnalyzer from Prometheus data.
    """
    
    metric_name: str = Field(..., description="Name of the metric (e.g., 'cpu_usage')")
    trend_state: TrendState = Field(..., description="DEGRADING, STABLE, RECOVERING, or UNKNOWN")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of trend classification")
    data_points: list[DataPoint] = Field(default_factory=list, description="Time-series data used")
    
    # Analysis metadata
    lookback_minutes: int = Field(15, description="Time window analyzed")
    threshold_value: float | None = Field(None, description="Threshold that triggered alert")
    current_value: float | None = Field(None, description="Most recent metric value")
    
    class Config:
        frozen = True
    
    @property
    def is_actionable(self) -> bool:
        """Returns True if trend provides actionable insight."""
        return self.trend_state != TrendState.UNKNOWN and self.confidence >= 0.6
