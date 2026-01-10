"""
MetricTrend Model - Computed Trend State

Represents the analysis of a specific metric over time.
Used to determine if a metric is degrading, stable, or recovering.
"""

from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from enum import Enum as _StrEnum
else:
    _StrEnum = str


class TrendState(IntEnum):
    """
    Possible trend states for a metric (FR-009).

    IntEnum with priority ordering for multi-metric fusion:
    UNKNOWN=0, STABLE=1, RECOVERING=2, DEGRADING=3
    """

    UNKNOWN = 0  # When insufficient data
    STABLE = 1
    RECOVERING = 2
    DEGRADING = 3

    @property
    def name_str(self) -> str:
        """Return string name for Pydantic serialization."""
        return self.name


class DataPoint(BaseModel):
    """Single point in a time series."""

    timestamp: datetime
    value: float
    is_outlier: bool = Field(False, description="True if filtered by p95 logic (FR-011)")

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

    # Enhancement fields (FR-011, FR-008)
    data_points_total: int = Field(0, description="Total raw data points retrieved")
    data_points_used: int = Field(0, description="Data points after p95 filtering")
    outliers_removed: int = Field(0, description="Count of outliers filtered (FR-011)")
    reasoning: str = Field("", description="Human-readable explanation of classification")
    time_window_seconds: int = Field(
        900, description="Actual analysis window duration (default 15min)"
    )
    fusion_method: str | None = Field(None, description="Multi-metric fusion method if applicable")

    class Config:
        frozen = True

    @property
    def is_actionable(self) -> bool:
        """Returns True if trend provides actionable insight."""
        return self.trend_state != TrendState.UNKNOWN and self.confidence >= 0.6
