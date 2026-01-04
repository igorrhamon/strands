"""
Unit Tests for Trend Analyzer

Tests:
- TrendAnalyzer classification logic
- Threshold detection
- TrendRules decision helpers
"""

import pytest
from datetime import datetime, timedelta

from src.models.metric_trend import MetricTrend, TrendState, DataPoint
from src.rules.trend_rules import (
    TrendAnalyzer,
    TrendConfig,
    TrendRules,
    analyze_metric_trend,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def base_time():
    """Base timestamp for creating test data."""
    return datetime.utcnow()


@pytest.fixture
def degrading_data(base_time):
    """Data showing degrading trend (increasing values)."""
    return [
        DataPoint(timestamp=base_time + timedelta(minutes=i), value=100 + i * 10)
        for i in range(10)  # 100 -> 190 (90% increase)
    ]


@pytest.fixture
def recovering_data(base_time):
    """Data showing recovering trend (decreasing values)."""
    return [
        DataPoint(timestamp=base_time + timedelta(minutes=i), value=200 - i * 15)
        for i in range(10)  # 200 -> 65 (67.5% decrease)
    ]


@pytest.fixture
def stable_data(base_time):
    """Data showing stable trend (minor fluctuation)."""
    import random
    random.seed(42)  # Reproducible
    return [
        DataPoint(
            timestamp=base_time + timedelta(minutes=i), 
            value=100 + random.uniform(-5, 5)
        )
        for i in range(10)
    ]


@pytest.fixture
def insufficient_data(base_time):
    """Insufficient data points."""
    return [
        DataPoint(timestamp=base_time, value=100),
        DataPoint(timestamp=base_time + timedelta(minutes=1), value=110),
    ]


# ============================================================================
# TrendAnalyzer Tests
# ============================================================================

class TestTrendAnalyzer:
    """Tests for TrendAnalyzer."""
    
    def test_detect_degrading_trend(self, degrading_data):
        """Test that increasing metrics are classified as DEGRADING."""
        analyzer = TrendAnalyzer()
        result = analyzer.analyze("cpu_usage", degrading_data)
        
        assert result.trend_state == TrendState.DEGRADING
        assert result.confidence >= 0.6
        assert result.metric_name == "cpu_usage"
    
    def test_detect_recovering_trend(self, recovering_data):
        """Test that decreasing metrics are classified as RECOVERING."""
        analyzer = TrendAnalyzer()
        result = analyzer.analyze("memory_usage", recovering_data)
        
        assert result.trend_state == TrendState.RECOVERING
        assert result.confidence >= 0.6
    
    def test_detect_stable_trend(self, stable_data):
        """Test that flat metrics are classified as STABLE."""
        analyzer = TrendAnalyzer()
        result = analyzer.analyze("request_rate", stable_data)
        
        assert result.trend_state == TrendState.STABLE
        assert result.confidence >= 0.5
    
    def test_insufficient_data_unknown(self, insufficient_data):
        """Test that insufficient data results in UNKNOWN."""
        analyzer = TrendAnalyzer()
        result = analyzer.analyze("test_metric", insufficient_data)
        
        assert result.trend_state == TrendState.UNKNOWN
        assert result.confidence == 0.0
    
    def test_empty_data_unknown(self):
        """Test that empty data results in UNKNOWN."""
        analyzer = TrendAnalyzer()
        result = analyzer.analyze("test_metric", [])
        
        assert result.trend_state == TrendState.UNKNOWN
    
    def test_custom_config(self, base_time):
        """Test that custom config thresholds are respected."""
        # Data with 20% increase
        data = [
            DataPoint(timestamp=base_time, value=100),
            DataPoint(timestamp=base_time + timedelta(minutes=1), value=105),
            DataPoint(timestamp=base_time + timedelta(minutes=2), value=110),
            DataPoint(timestamp=base_time + timedelta(minutes=3), value=115),
            DataPoint(timestamp=base_time + timedelta(minutes=4), value=120),
        ]
        
        # Default threshold (15%) should detect DEGRADING
        default_analyzer = TrendAnalyzer()
        result1 = default_analyzer.analyze("test", data)
        assert result1.trend_state == TrendState.DEGRADING
        
        # Higher threshold (25%) should detect STABLE
        strict_config = TrendConfig(degrading_threshold=0.25)
        strict_analyzer = TrendAnalyzer(strict_config)
        result2 = strict_analyzer.analyze("test", data)
        assert result2.trend_state == TrendState.STABLE
    
    def test_current_value_populated(self, degrading_data):
        """Test that current_value is set to last data point."""
        analyzer = TrendAnalyzer()
        result = analyzer.analyze("test", degrading_data)
        
        assert result.current_value == degrading_data[-1].value
    
    def test_threshold_value_preserved(self, degrading_data):
        """Test that threshold_value is preserved in result."""
        analyzer = TrendAnalyzer()
        result = analyzer.analyze("test", degrading_data, threshold_value=150.0)
        
        assert result.threshold_value == 150.0
    
    def test_analyze_multiple(self, degrading_data, recovering_data, stable_data):
        """Test batch analysis of multiple metrics."""
        analyzer = TrendAnalyzer()
        results = analyzer.analyze_multiple({
            "cpu": degrading_data,
            "memory": recovering_data,
            "requests": stable_data,
        })
        
        assert len(results) == 3
        assert results["cpu"].trend_state == TrendState.DEGRADING
        assert results["memory"].trend_state == TrendState.RECOVERING
        assert results["requests"].trend_state == TrendState.STABLE


# ============================================================================
# TrendRules Tests
# ============================================================================

class TestTrendRules:
    """Tests for TrendRules decision helpers."""
    
    def test_should_escalate_multiple_degrading(self, base_time):
        """Test escalation when multiple metrics are degrading."""
        trends = [
            MetricTrend(
                metric_name="cpu",
                trend_state=TrendState.DEGRADING,
                confidence=0.8,
                data_points=[],
            ),
            MetricTrend(
                metric_name="memory",
                trend_state=TrendState.DEGRADING,
                confidence=0.75,
                data_points=[],
            ),
        ]
        
        assert TrendRules.should_escalate(trends) is True
    
    def test_should_escalate_single_high_confidence(self, base_time):
        """Test escalation when single metric is degrading with high confidence."""
        trends = [
            MetricTrend(
                metric_name="cpu",
                trend_state=TrendState.DEGRADING,
                confidence=0.95,  # Very high confidence
                data_points=[],
            ),
            MetricTrend(
                metric_name="memory",
                trend_state=TrendState.STABLE,
                confidence=0.7,
                data_points=[],
            ),
        ]
        
        assert TrendRules.should_escalate(trends) is True
    
    def test_no_escalation_stable(self):
        """Test no escalation when metrics are stable."""
        trends = [
            MetricTrend(
                metric_name="cpu",
                trend_state=TrendState.STABLE,
                confidence=0.8,
                data_points=[],
            ),
            MetricTrend(
                metric_name="memory",
                trend_state=TrendState.RECOVERING,
                confidence=0.7,
                data_points=[],
            ),
        ]
        
        assert TrendRules.should_escalate(trends) is False
    
    def test_can_auto_close_all_stable(self):
        """Test auto-close allowed when all metrics stable/recovering."""
        trends = [
            MetricTrend(
                metric_name="cpu",
                trend_state=TrendState.STABLE,
                confidence=0.8,
                data_points=[],
            ),
            MetricTrend(
                metric_name="memory",
                trend_state=TrendState.RECOVERING,
                confidence=0.7,
                data_points=[],
            ),
        ]
        
        assert TrendRules.can_auto_close(trends) is True
    
    def test_cannot_auto_close_degrading(self):
        """Test auto-close blocked when any metric is degrading."""
        trends = [
            MetricTrend(
                metric_name="cpu",
                trend_state=TrendState.DEGRADING,
                confidence=0.6,
                data_points=[],
            ),
            MetricTrend(
                metric_name="memory",
                trend_state=TrendState.STABLE,
                confidence=0.8,
                data_points=[],
            ),
        ]
        
        assert TrendRules.can_auto_close(trends) is False
    
    def test_cannot_auto_close_unknown(self):
        """Test auto-close blocked when any metric is unknown."""
        trends = [
            MetricTrend(
                metric_name="cpu",
                trend_state=TrendState.STABLE,
                confidence=0.8,
                data_points=[],
            ),
            MetricTrend(
                metric_name="memory",
                trend_state=TrendState.UNKNOWN,
                confidence=0.0,
                data_points=[],
            ),
        ]
        
        assert TrendRules.can_auto_close(trends) is False
    
    def test_get_trend_summary(self):
        """Test human-readable summary generation."""
        trends = [
            MetricTrend(
                metric_name="cpu",
                trend_state=TrendState.DEGRADING,
                confidence=0.8,
                data_points=[],
            ),
            MetricTrend(
                metric_name="memory",
                trend_state=TrendState.STABLE,
                confidence=0.7,
                data_points=[],
            ),
        ]
        
        summary = TrendRules.get_trend_summary(trends)
        
        assert "DEGRADING: cpu" in summary
        assert "STABLE" in summary
    
    def test_get_trend_summary_empty(self):
        """Test summary for empty trends."""
        summary = TrendRules.get_trend_summary([])
        assert "No metric data" in summary


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestAnalyzeMetricTrend:
    """Tests for analyze_metric_trend convenience function."""
    
    def test_convenience_function(self, degrading_data):
        """Test the convenience function."""
        result = analyze_metric_trend("test_metric", degrading_data)
        
        assert isinstance(result, MetricTrend)
        assert result.metric_name == "test_metric"
        assert result.trend_state == TrendState.DEGRADING


# ============================================================================
# MetricTrend Model Tests
# ============================================================================

class TestMetricTrendModel:
    """Tests for MetricTrend model properties."""
    
    def test_is_actionable_true(self):
        """Test is_actionable returns True for valid trends."""
        trend = MetricTrend(
            metric_name="cpu",
            trend_state=TrendState.DEGRADING,
            confidence=0.7,
            data_points=[],
        )
        
        assert trend.is_actionable is True
    
    def test_is_actionable_false_unknown(self):
        """Test is_actionable returns False for UNKNOWN."""
        trend = MetricTrend(
            metric_name="cpu",
            trend_state=TrendState.UNKNOWN,
            confidence=0.7,
            data_points=[],
        )
        
        assert trend.is_actionable is False
    
    def test_is_actionable_false_low_confidence(self):
        """Test is_actionable returns False for low confidence."""
        trend = MetricTrend(
            metric_name="cpu",
            trend_state=TrendState.DEGRADING,
            confidence=0.5,  # Below 0.6 threshold
            data_points=[],
        )
        
        assert trend.is_actionable is False
