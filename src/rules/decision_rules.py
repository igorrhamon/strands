"""
Decision Rules - Deterministic Logic

Implements deterministic rules for decision-making.
Constitution Principle II: Rules execute BEFORE any LLM invocation.

Rule evaluation order:
1. Critical severity checks
2. Trend-based analysis
3. Historical pattern matching
4. Default fallback
"""

import logging
from typing import Optional

from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend, TrendState
from src.models.decision import DecisionState, SemanticEvidence

logger = logging.getLogger(__name__)


# Rule identifiers for audit trail
RULE_CRITICAL_DEGRADING = "rule_critical_degrading"
RULE_RECOVERY_DETECTED = "rule_recovery_detected"
RULE_STABLE_METRICS = "rule_stable_metrics"
RULE_HISTORICAL_CLOSE = "rule_historical_close"
RULE_HISTORICAL_ESCALATE = "rule_historical_escalate"
RULE_INSUFFICIENT_DATA = "rule_insufficient_data"
RULE_DEFAULT_OBSERVE = "rule_default_observe"


class RuleResult:
    """Result of a rule evaluation."""
    
    def __init__(
        self,
        decision_state: Optional[DecisionState],
        confidence: float,
        rule_id: str,
        justification: str,
        fires: bool = True,
    ):
        self.decision_state = decision_state
        self.confidence = confidence
        self.rule_id = rule_id
        self.justification = justification
        self.fires = fires
    
    def __repr__(self) -> str:
        return f"RuleResult({self.rule_id}, fires={self.fires}, confidence={self.confidence})"


class DecisionRules:
    """
    Deterministic rules for alert decisions.
    
    All rules return RuleResult with:
    - decision_state: Recommended action (or None if rule doesn't fire)
    - confidence: Confidence in the decision (0.0-1.0)
    - rule_id: Identifier for audit trail
    - justification: Human-readable explanation
    - fires: Whether this rule applies
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.70
    LOW_CONFIDENCE = 0.50
    
    @staticmethod
    def check_critical_degrading(
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
    ) -> RuleResult:
        """
        Rule: Critical alerts with degrading metrics → ESCALATE
        
        Fires when:
        - Primary severity is 'critical'
        - At least one metric is DEGRADING with high confidence
        """
        if cluster.primary_severity != "critical":
            return RuleResult(
                decision_state=None,
                confidence=0.0,
                rule_id=RULE_CRITICAL_DEGRADING,
                justification="Not a critical alert",
                fires=False,
            )
        
        degrading_metrics = [
            name for name, trend in trends.items()
            if trend.trend_state == TrendState.DEGRADING and trend.confidence >= 0.7
        ]
        
        if degrading_metrics:
            return RuleResult(
                decision_state=DecisionState.ESCALATE,
                confidence=DecisionRules.HIGH_CONFIDENCE,
                rule_id=RULE_CRITICAL_DEGRADING,
                justification=f"Critical alert with degrading metrics: {', '.join(degrading_metrics)}",
            )
        
        return RuleResult(
            decision_state=None,
            confidence=0.0,
            rule_id=RULE_CRITICAL_DEGRADING,
            justification="Critical alert but metrics not degrading",
            fires=False,
        )
    
    @staticmethod
    def check_recovery_detected(
        trends: dict[str, MetricTrend],
    ) -> RuleResult:
        """
        Rule: All metrics RECOVERING → CLOSE
        
        Fires when:
        - All analyzed metrics show RECOVERING trend
        - Confidence in recovery is high
        """
        if not trends:
            return RuleResult(
                decision_state=None,
                confidence=0.0,
                rule_id=RULE_RECOVERY_DETECTED,
                justification="No metrics to analyze",
                fires=False,
            )
        
        recovering = [
            t for t in trends.values()
            if t.trend_state == TrendState.RECOVERING and t.confidence >= 0.6
        ]
        
        if len(recovering) == len(trends):
            avg_confidence = sum(t.confidence for t in recovering) / len(recovering)
            return RuleResult(
                decision_state=DecisionState.CLOSE,
                confidence=min(DecisionRules.HIGH_CONFIDENCE, avg_confidence + 0.1),
                rule_id=RULE_RECOVERY_DETECTED,
                justification=f"All {len(recovering)} metric(s) showing recovery",
            )
        
        return RuleResult(
            decision_state=None,
            confidence=0.0,
            rule_id=RULE_RECOVERY_DETECTED,
            justification="Not all metrics recovering",
            fires=False,
        )
    
    @staticmethod
    def check_stable_metrics(
        trends: dict[str, MetricTrend],
        min_stable_count: int = 2,
    ) -> RuleResult:
        """
        Rule: Stable metrics → OBSERVE
        
        Fires when:
        - At least min_stable_count metrics are STABLE
        - No metrics are DEGRADING
        """
        if not trends:
            return RuleResult(
                decision_state=None,
                confidence=0.0,
                rule_id=RULE_STABLE_METRICS,
                justification="No metrics to analyze",
                fires=False,
            )
        
        stable = [t for t in trends.values() if t.trend_state == TrendState.STABLE]
        degrading = [t for t in trends.values() if t.trend_state == TrendState.DEGRADING]
        
        if degrading:
            return RuleResult(
                decision_state=None,
                confidence=0.0,
                rule_id=RULE_STABLE_METRICS,
                justification="Some metrics are degrading",
                fires=False,
            )
        
        if len(stable) >= min_stable_count:
            return RuleResult(
                decision_state=DecisionState.OBSERVE,
                confidence=DecisionRules.MEDIUM_CONFIDENCE,
                rule_id=RULE_STABLE_METRICS,
                justification=f"{len(stable)} metric(s) stable, continuing observation",
            )
        
        return RuleResult(
            decision_state=None,
            confidence=0.0,
            rule_id=RULE_STABLE_METRICS,
            justification=f"Only {len(stable)} stable metric(s)",
            fires=False,
        )
    
    @staticmethod
    def check_historical_patterns(
        semantic_evidence: list[SemanticEvidence],
        min_score: float = 0.85,
    ) -> RuleResult:
        """
        Rule: Strong historical match → Follow historical pattern
        
        Fires when:
        - At least one semantic match with score >= min_score
        - Historical decision provides clear guidance
        """
        if not semantic_evidence:
            return RuleResult(
                decision_state=None,
                confidence=0.0,
                rule_id=RULE_HISTORICAL_CLOSE,
                justification="No historical evidence",
                fires=False,
            )
        
        # Find strongest match
        best_match = max(semantic_evidence, key=lambda e: e.similarity_score)
        
        if best_match.similarity_score < min_score:
            return RuleResult(
                decision_state=None,
                confidence=0.0,
                rule_id=RULE_HISTORICAL_CLOSE,
                justification=f"Best match score {best_match.similarity_score:.2f} below threshold {min_score}",
                fires=False,
            )
        
        # Analyze historical pattern from summary
        summary_lower = best_match.summary.lower()
        
        if any(word in summary_lower for word in ["closed", "resolved", "recovered"]):
            return RuleResult(
                decision_state=DecisionState.CLOSE,
                confidence=best_match.similarity_score,
                rule_id=RULE_HISTORICAL_CLOSE,
                justification=f"Historical match ({best_match.similarity_score:.2f}): similar alert was closed",
            )
        
        if any(word in summary_lower for word in ["escalated", "critical", "urgent"]):
            return RuleResult(
                decision_state=DecisionState.ESCALATE,
                confidence=best_match.similarity_score,
                rule_id=RULE_HISTORICAL_ESCALATE,
                justification=f"Historical match ({best_match.similarity_score:.2f}): similar alert was escalated",
            )
        
        return RuleResult(
            decision_state=DecisionState.OBSERVE,
            confidence=best_match.similarity_score * 0.8,  # Reduce confidence for unclear pattern
            rule_id=RULE_HISTORICAL_CLOSE,
            justification=f"Historical match ({best_match.similarity_score:.2f}): pattern unclear, recommending observation",
        )
    
    @staticmethod
    def check_insufficient_data(
        trends: dict[str, MetricTrend],
    ) -> RuleResult:
        """
        Rule: Insufficient metric data → MANUAL_REVIEW
        
        Fires when:
        - Too many metrics are UNKNOWN
        - Cannot make confident decision
        """
        if not trends:
            return RuleResult(
                decision_state=DecisionState.MANUAL_REVIEW,
                confidence=DecisionRules.MEDIUM_CONFIDENCE,
                rule_id=RULE_INSUFFICIENT_DATA,
                justification="No metric data available for analysis",
            )
        
        unknown = [t for t in trends.values() if t.trend_state == TrendState.UNKNOWN]
        
        if len(unknown) >= len(trends) / 2:
            return RuleResult(
                decision_state=DecisionState.MANUAL_REVIEW,
                confidence=DecisionRules.MEDIUM_CONFIDENCE,
                rule_id=RULE_INSUFFICIENT_DATA,
                justification=f"{len(unknown)}/{len(trends)} metrics have insufficient data",
            )
        
        return RuleResult(
            decision_state=None,
            confidence=0.0,
            rule_id=RULE_INSUFFICIENT_DATA,
            justification="Sufficient metric data available",
            fires=False,
        )
    
    @staticmethod
    def default_observe() -> RuleResult:
        """
        Default rule: No other rule fired → OBSERVE
        
        Fallback when no deterministic rule produces a decision.
        """
        return RuleResult(
            decision_state=DecisionState.OBSERVE,
            confidence=DecisionRules.LOW_CONFIDENCE,
            rule_id=RULE_DEFAULT_OBSERVE,
            justification="No deterministic rule matched, defaulting to observation",
        )


class RuleEngine:
    """
    Engine for evaluating decision rules in order.
    
    Constitution Principle II: All rules are evaluated before any LLM call.
    """
    
    def __init__(
        self,
        confidence_threshold: float = 0.60,
    ):
        """
        Initialize rule engine.
        
        Args:
            confidence_threshold: Minimum confidence to accept a rule decision.
        """
        self._confidence_threshold = confidence_threshold
    
    def evaluate(
        self,
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
        semantic_evidence: list[SemanticEvidence],
    ) -> tuple[RuleResult, list[str]]:
        """
        Evaluate all rules and return the best decision.
        
        Args:
            cluster: Alert cluster being analyzed.
            trends: Metric trends for the cluster.
            semantic_evidence: Historical context from RAG.
        
        Returns:
            Tuple of (best RuleResult, list of all fired rule IDs)
        """
        fired_rules = []
        best_result: Optional[RuleResult] = None
        
        # Rule evaluation order (priority)
        rules = [
            lambda: DecisionRules.check_critical_degrading(cluster, trends),
            lambda: DecisionRules.check_recovery_detected(trends),
            lambda: DecisionRules.check_insufficient_data(trends),
            lambda: DecisionRules.check_historical_patterns(semantic_evidence),
            lambda: DecisionRules.check_stable_metrics(trends),
        ]
        
        for rule_fn in rules:
            result = rule_fn()
            
            if result.fires:
                fired_rules.append(result.rule_id)
                
                if result.decision_state is not None:
                    if best_result is None or result.confidence > best_result.confidence:
                        best_result = result
                    
                    # If confidence is high enough, stop evaluating
                    if result.confidence >= self._confidence_threshold:
                        break
        
        # If no rule produced a decision, use default
        if best_result is None or best_result.decision_state is None:
            best_result = DecisionRules.default_observe()
            fired_rules.append(best_result.rule_id)
        
        logger.info(
            f"Rule engine: {len(fired_rules)} rules fired, "
            f"decision={best_result.decision_state.value}, "
            f"confidence={best_result.confidence:.2f}"
        )
        
        return best_result, fired_rules
