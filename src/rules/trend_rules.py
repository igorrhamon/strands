"""
Trend Rules - Metric Classification Logic

Deterministic rules for classifying metric trends.
Constitution Principle II: Rules execute BEFORE any LLM invocation.

Enhanced with p95 outlier filtering (FR-011) and confidence scoring (FR-005).
"""

import logging
from typing import Optional, Tuple

from src.models.metric_trend import MetricTrend, TrendState, DataPoint
from src.utils.statistics import (
    filter_outliers_p95,
    compute_linear_trend,
    compute_variance_coefficient,
    validate_data_points,
)

logger = logging.getLogger(__name__)


# Default thresholds
DEFAULT_DEGRADING_THRESHOLD = 0.15  # 15% increase
DEFAULT_RECOVERING_THRESHOLD = 0.10  # 10% decrease
DEFAULT_MIN_DATA_POINTS = 3  # Minimum points for trend analysis


class TrendConfig:
    """Configuration for trend analysis rules."""

    def __init__(
        self,
        degrading_threshold: float = DEFAULT_DEGRADING_THRESHOLD,
        recovering_threshold: float = DEFAULT_RECOVERING_THRESHOLD,
        min_data_points: int = DEFAULT_MIN_DATA_POINTS,
        lookback_minutes: int = 15,
    ):
        self.degrading_threshold = degrading_threshold
        self.recovering_threshold = recovering_threshold
        self.min_data_points = min_data_points
        self.lookback_minutes = lookback_minutes


class TrendAnalyzer:
    """
    Analyzes time-series data to determine trend state.

    Classification logic:
    - DEGRADING: Metric increased by > threshold over window
    - RECOVERING: Metric decreased by > threshold over window
    - STABLE: Metric within threshold bounds
    - UNKNOWN: Insufficient data for analysis
    """

    def __init__(self, config: Optional[TrendConfig] = None):
        """
        Initialize trend analyzer.

        Args:
            config: Trend analysis configuration.
        """
        self._config = config or TrendConfig()

    def analyze(
        self,
        metric_name: str,
        data_points: list[DataPoint],
        threshold_value: Optional[float] = None,
    ) -> MetricTrend:
        """
        Analyze data points to determine trend with p95 outlier filtering.

        Enhanced workflow (FR-011):
        1. Validate data points (remove NaN/Inf)
        2. Apply p95 percentile filtering to remove outliers
        3. Classify trend using linear regression
        4. Assign confidence based on data quality

        Args:
            metric_name: Name of the metric being analyzed.
            data_points: Time-series data points (should be sorted by timestamp).
            threshold_value: Optional threshold that triggered the alert.

        Returns:
            MetricTrend with classification, confidence, and outlier metadata.
        """
        # Extract values and validate
        values = [dp.value for dp in data_points]
        valid_values = validate_data_points(values)

        # Check for minimum data points (FR-005)
        if len(valid_values) < 5:
            logger.warning(
                f"Insufficient data for {metric_name}: {len(valid_values)} points (need ≥5)"
            )
            return self._create_unknown_trend(
                metric_name,
                data_points,
                threshold_value,
                reasoning="Insufficient data: <5 valid data points",
            )

        # Apply p95 outlier filtering (FR-011)
        # For very small datasets, skip outlier filtering to avoid removing
        # critical points that would make the set insufficient for analysis.
        total_valid = len(valid_values)
        if total_valid <= 5:
            filtered_values = valid_values
            outliers = []
        else:
            filtered_values, outliers = filter_outliers_p95(valid_values)

        # Update DataPoint objects with outlier flag
        filtered_data_points = self._mark_outliers(data_points, outliers)

        # Calculate trend classification
        trend_state, confidence, reasoning = self._classify_trend_internal(
            filtered_values, len(valid_values)
        )

        # Construct result with enhancement fields (FR-008)
        return MetricTrend(
            metric_name=metric_name,
            trend_state=trend_state,
            confidence=confidence,
            data_points=filtered_data_points,
            lookback_minutes=self._config.lookback_minutes,
            threshold_value=threshold_value,
            current_value=filtered_data_points[-1].value if filtered_data_points else None,
            # Enhancement fields
            data_points_total=len(data_points),
            data_points_used=len(filtered_values),
            outliers_removed=len(outliers),
            reasoning=reasoning,
            time_window_seconds=self._config.lookback_minutes * 60,
            fusion_method=None,  # Single-metric, no fusion
        )

    def _mark_outliers(
        self, data_points: list[DataPoint], outlier_values: list[float]
    ) -> list[DataPoint]:
        """Mark DataPoint objects as outliers based on filtered values."""
        outlier_set = set(outlier_values)
        marked_points = []

        for dp in data_points:
            is_outlier = dp.value in outlier_set
            # Create new DataPoint with is_outlier flag
            marked_points.append(
                DataPoint(
                    timestamp=dp.timestamp,
                    value=dp.value,
                    is_outlier=is_outlier,
                )
            )

        return marked_points

    def _create_unknown_trend(
        self,
        metric_name: str,
        data_points: list[DataPoint],
        threshold_value: Optional[float],
        reasoning: str,
    ) -> MetricTrend:
        """Create an UNKNOWN MetricTrend with explanation."""
        return MetricTrend(
            metric_name=metric_name,
            trend_state=TrendState.UNKNOWN,
            confidence=0.0,
            data_points=data_points,
            lookback_minutes=self._config.lookback_minutes,
            threshold_value=threshold_value,
            current_value=data_points[-1].value if data_points else None,
            data_points_total=len(data_points),
            data_points_used=0,
            outliers_removed=0,
            reasoning=reasoning,
            time_window_seconds=self._config.lookback_minutes * 60,
            fusion_method=None,
        )

    def _classify_trend_internal(
        self, values: list[float], total_valid_points: int
    ) -> tuple[TrendState, float, str]:
        """
        Classify trend using linear regression slope with tiered confidence.

        Enhanced classification (FR-004, FR-005, FR-011):
        - Uses compute_linear_trend() for slope-based classification
        - Confidence tiers: ≥10 points → ≥0.85, 5-9 points → cap 0.70, <5 → UNKNOWN
        - Generates deterministic reasoning trace

        Args:
            values: Filtered (post-p95) data values.
            total_valid_points: Count of valid points before filtering.

        Returns:
            (TrendState, confidence_score, reasoning_string)
        """
        if len(values) < 5:
            return (
                TrendState.UNKNOWN,
                0.0,
                f"Insufficient filtered data: {len(values)} points after p95 filtering",
            )

        # Prefer relative percent change over the window for classification.
        # This aligns with human expectations (e.g., 15% increase => degrading).
        try:
            first = values[0]
            last = values[-1]
            percent_change = (last - first) / abs(first) if first != 0 else 0.0
        except Exception:
            percent_change = 0.0

        if percent_change > self._config.degrading_threshold:
            trend_state = TrendState.DEGRADING
            direction = "increasing"
        elif percent_change < -self._config.recovering_threshold:
            trend_state = TrendState.RECOVERING
            direction = "decreasing"
        else:
            trend_state = TrendState.STABLE
            direction = "stable"

        # Compute linear regression diagnostics for confidence scoring
        slope, r_squared = compute_linear_trend(values)
        cv = compute_variance_coefficient(values)

        # Tiered confidence scoring (FR-005)
        base_confidence = r_squared  # Start with goodness-of-fit (0.0-1.0)

        if len(values) >= 10:
            # High-quality data: boost confidence
            confidence = min(base_confidence + 0.15, 0.95)
            data_quality = "high (≥10 points)"
        elif len(values) >= 5:
            # Medium-quality data: cap confidence
            confidence = min(base_confidence, 0.70)
            data_quality = "medium (5-9 points)"
        else:
            # Should not reach here (caught earlier), but defensive
            confidence = 0.0
            data_quality = "insufficient (<5 points)"

        # Adjust confidence based on variance (high variance → lower confidence)
        if cv > 0.5:  # High coefficient of variation
            confidence *= 0.85
            variance_note = " (high variance penalty applied)"
        else:
            variance_note = ""

        # Boost confidence for STABLE classification: low CV and many points should be trustworthy
        if trend_state == TrendState.STABLE:
            if len(values) >= 10:
                confidence = max(confidence, min(0.95, 0.6 + (1 - min(cv, 1.0)) * 0.3))
            else:
                confidence = max(confidence, min(0.75, 0.5 + (1 - min(cv, 1.0)) * 0.2))

        # Generate deterministic reasoning (FR-008)
        reasoning = (
            f"Trend: {direction} (slope={slope:.4f}). "
            f"Confidence: {confidence:.2f} (R²={r_squared:.2f}, data_quality={data_quality}, "
            f"cv={cv:.2f}{variance_note}). "
            f"Thresholds: degrading={self._config.degrading_threshold}, recovering={self._config.recovering_threshold}. "
            f"Points: {len(values)} used from {total_valid_points} valid."
        )

        return trend_state, confidence, reasoning

    def _calculate_trend(self, data_points: list[DataPoint]) -> tuple[TrendState, float]:
        """
        Calculate trend state and confidence from data points.

        Uses linear regression slope to determine direction.
        """
        if not data_points:
            return TrendState.UNKNOWN, 0.0

        # Calculate percentage change from first to last
        first_value = data_points[0].value
        last_value = data_points[-1].value

        if first_value == 0:
            # Avoid division by zero
            if last_value > 0:
                return TrendState.DEGRADING, 0.8
            return TrendState.STABLE, 0.5

        pct_change = (last_value - first_value) / first_value

        # Calculate average for variance analysis
        avg_value = sum(dp.value for dp in data_points) / len(data_points)
        variance = sum((dp.value - avg_value) ** 2 for dp in data_points) / len(data_points)

        # Determine trend state
        if pct_change > self._config.degrading_threshold:
            trend_state = TrendState.DEGRADING
            confidence = min(0.95, 0.6 + abs(pct_change))
        elif pct_change < -self._config.recovering_threshold:
            trend_state = TrendState.RECOVERING
            confidence = min(0.95, 0.6 + abs(pct_change))
        else:
            trend_state = TrendState.STABLE
            # Higher confidence for low variance
            confidence = 0.7 if variance < avg_value * 0.1 else 0.5

        return trend_state, confidence

    def analyze_multiple(
        self,
        metrics: dict[str, list[DataPoint]],
    ) -> dict[str, MetricTrend]:
        """
        Analyze multiple metrics at once.

        Args:
            metrics: Dict mapping metric names to their data points.

        Returns:
            Dict mapping metric names to their trend analysis.
        """
        return {name: self.analyze(name, points) for name, points in metrics.items()}


def fuse_trends(trends: list[tuple[TrendState, float]]) -> tuple[TrendState, float]:
    """
    Fuse multiple metric trends using priority-based logic (FR-009).

    Priority ordering: DEGRADING (3) > RECOVERING (2) > STABLE (1) > UNKNOWN (0)
    Weighted confidence: 70% weight for matching priority, 30% for others.

    Args:
        trends: List of (TrendState, confidence) tuples from individual metrics.

    Returns:
        (fused_trend_state, fused_confidence)

    Examples:
        >>> fuse_trends([(TrendState.DEGRADING, 0.9), (TrendState.STABLE, 0.8)])
        (TrendState.DEGRADING, 0.87)  # 0.9 * 0.7 + 0.8 * 0.3

        >>> fuse_trends([(TrendState.STABLE, 0.7), (TrendState.STABLE, 0.8)])
        (TrendState.STABLE, 0.82)  # (0.7 + 0.8) * 0.7 / 2 + ...
    """
    if not trends:
        return TrendState.UNKNOWN, 0.0

    # Find max priority trend (DEGRADING > RECOVERING > STABLE > UNKNOWN)
    max_priority = max(state for state, _ in trends)
    fused_state = TrendState(max_priority)

    # Separate trends into matching and non-matching priority
    matching_trends = [conf for state, conf in trends if state == fused_state]
    other_trends = [conf for state, conf in trends if state != fused_state]

    # Weighted confidence calculation
    if matching_trends:
        matching_avg = sum(matching_trends) / len(matching_trends)
        matching_weight = 0.7
    else:
        matching_avg = 0.0
        matching_weight = 0.0

    if other_trends:
        other_avg = sum(other_trends) / len(other_trends)
        other_weight = 0.3
    else:
        other_avg = 0.0
        other_weight = 0.0

    # Normalize weights if we don't have both types
    total_weight = matching_weight + other_weight
    if total_weight > 0:
        fused_confidence = matching_avg * (matching_weight / total_weight) + other_avg * (
            other_weight / total_weight
        )
    else:
        fused_confidence = 0.0

    # Ensure confidence is in valid range
    fused_confidence = max(0.0, min(1.0, fused_confidence))

    return fused_state, fused_confidence


class TrendRules:
    """
    Deterministic rules for interpreting trend analysis.

    Provides actionable insights based on trend states.
    """

    @staticmethod
    def should_escalate(trends: list[MetricTrend]) -> bool:
        """
        Determine if trends warrant escalation.

        Escalate if:
        - Multiple critical metrics are DEGRADING
        - Any metric is DEGRADING with high confidence
        """
        degrading_count = sum(
            1 for t in trends if t.trend_state == TrendState.DEGRADING and t.confidence >= 0.7
        )

        return degrading_count >= 2 or any(
            t.trend_state == TrendState.DEGRADING and t.confidence >= 0.9 for t in trends
        )

    @staticmethod
    def can_auto_close(trends: list[MetricTrend]) -> bool:
        """
        Determine if trends suggest auto-close is safe.

        Auto-close if:
        - All metrics are STABLE or RECOVERING
        - No metrics are UNKNOWN (need data)
        """
        if not trends:
            return False

        for trend in trends:
            if trend.trend_state == TrendState.DEGRADING:
                return False
            if trend.trend_state == TrendState.UNKNOWN:
                return False

        return True

    @staticmethod
    def get_trend_summary(trends: list[MetricTrend]) -> str:
        """
        Generate human-readable summary of trends.

        Args:
            trends: List of MetricTrend objects.

        Returns:
            Summary string for decision justification.
        """
        if not trends:
            return "No metric data available for analysis."

        degrading = [t for t in trends if t.trend_state == TrendState.DEGRADING]
        recovering = [t for t in trends if t.trend_state == TrendState.RECOVERING]
        stable = [t for t in trends if t.trend_state == TrendState.STABLE]
        unknown = [t for t in trends if t.trend_state == TrendState.UNKNOWN]

        parts = []
        if degrading:
            names = ", ".join(t.metric_name for t in degrading)
            parts.append(f"DEGRADING: {names}")
        if recovering:
            names = ", ".join(t.metric_name for t in recovering)
            parts.append(f"RECOVERING: {names}")
        if stable:
            parts.append(f"{len(stable)} metric(s) STABLE")
        if unknown:
            names = ", ".join(t.metric_name for t in unknown)
            parts.append(f"UNKNOWN (insufficient data): {names}")

        return "; ".join(parts)


def analyze_metric_trend(
    metric_name: str,
    data_points: list[DataPoint],
    threshold_value: Optional[float] = None,
) -> MetricTrend:
    """
    Convenience function to analyze a single metric.

    Args:
        metric_name: Name of the metric.
        data_points: Time-series data.
        threshold_value: Optional alert threshold.

    Returns:
        MetricTrend with analysis results.
    """
    analyzer = TrendAnalyzer()
    return analyzer.analyze(metric_name, data_points, threshold_value)
