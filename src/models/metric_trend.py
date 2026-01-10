"""
MetricTrend Model - Computed Trend State

Represents the analysis of a specific metric over time.
Used to determine if a metric is degrading, stable, or recovering.
"""

from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

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

    model_config = ConfigDict(frozen=True, extra="ignore")

    metric_name: str
    trend_state: TrendState
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of trend classification")
    data_points: list[DataPoint] = Field(default_factory=list, description="Time-series data used")

    # Analysis metadata
    lookback_minutes: int = 15
    threshold_value: float | None = None
    current_value: float | None = None

    # Enhancement fields (FR-011, FR-008)
    data_points_total: int = 0
    data_points_used: int = 0
    outliers_removed: int = 0
    reasoning: str = ""
    time_window_seconds: int = 900
    fusion_method: str | None = None

    @property
    def is_actionable(self) -> bool:
        """Returns True if trend provides actionable insight."""
        return self.trend_state != TrendState.UNKNOWN and self.confidence >= 0.6
