# Rules Package
"""
Deterministic rule engines.

Rules are evaluated BEFORE any LLM invocation.
All rule contributions are logged in audit trail.

Constitution Principle II: Determinismo.
"""

from src.rules.correlation_rules import (
    CorrelationEngine,
    CorrelationConfig,
    correlate_alerts,
)
from src.rules.trend_rules import (
    TrendAnalyzer,
    TrendConfig,
    TrendRules,
    analyze_metric_trend,
)
from src.rules.decision_rules import (
    DecisionRules,
    RuleEngine,
    RuleResult,
    RULE_CRITICAL_DEGRADING,
    RULE_RECOVERY_DETECTED,
    RULE_STABLE_METRICS,
    RULE_HISTORICAL_CLOSE,
    RULE_INSUFFICIENT_DATA,
    RULE_DEFAULT_OBSERVE,
)

__all__ = [
    "CorrelationEngine",
    "CorrelationConfig",
    "correlate_alerts",
    "TrendAnalyzer",
    "TrendConfig",
    "TrendRules",
    "analyze_metric_trend",
    "DecisionRules",
    "RuleEngine",
    "RuleResult",
    "RULE_CRITICAL_DEGRADING",
    "RULE_RECOVERY_DETECTED",
    "RULE_STABLE_METRICS",
    "RULE_HISTORICAL_CLOSE",
    "RULE_INSUFFICIENT_DATA",
    "RULE_DEFAULT_OBSERVE",
]
