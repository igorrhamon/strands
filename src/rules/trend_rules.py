"""
Trend Rules - Metric Classification Logic

Deterministic rules for classifying metric trends.
Constitution Principle II: Rules execute BEFORE any LLM invocation.
"""

import logging
from typing import Optional

from src.models.metric_trend import MetricTrend, TrendState, DataPoint

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
        Analyze data points to determine trend.
        
        Args:
            metric_name: Name of the metric being analyzed.
            data_points: Time-series data points (should be sorted by timestamp).
            threshold_value: Optional threshold that triggered the alert.
        
        Returns:
            MetricTrend with classification and confidence.
        """
        # Check for minimum data points
        if len(data_points) < self._config.min_data_points:
            logger.warning(
                f"Insufficient data for {metric_name}: "
                f"{len(data_points)} < {self._config.min_data_points}"
            )
            return MetricTrend(
                metric_name=metric_name,
                trend_state=TrendState.UNKNOWN,
                confidence=0.0,
                data_points=data_points,
                lookback_minutes=self._config.lookback_minutes,
                threshold_value=threshold_value,
                current_value=data_points[-1].value if data_points else None,
            )
        
        # Sort by timestamp if not already
        sorted_points = sorted(data_points, key=lambda dp: dp.timestamp)
        
        # Calculate trend
        trend_state, confidence = self._calculate_trend(sorted_points)
        
        return MetricTrend(
            metric_name=metric_name,
            trend_state=trend_state,
            confidence=confidence,
            data_points=sorted_points,
            lookback_minutes=self._config.lookback_minutes,
            threshold_value=threshold_value,
            current_value=sorted_points[-1].value,
        )
    
    def _calculate_trend(
        self, data_points: list[DataPoint]
    ) -> tuple[TrendState, float]:
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
        return {
            name: self.analyze(name, points)
            for name, points in metrics.items()
        }


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
            1 for t in trends 
            if t.trend_state == TrendState.DEGRADING and t.confidence >= 0.7
        )
        
        return degrading_count >= 2 or any(
            t.trend_state == TrendState.DEGRADING and t.confidence >= 0.9
            for t in trends
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
