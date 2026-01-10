"""Deterministic policy engine for decision rules"""
from typing import Dict, List
import logging

from src.models.cluster import AlertCluster
from src.models.metrics import MetricsAnalysisResult, TrendClassification
from src.models.decision import DecisionState


logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Deterministic rule-based policy engine.
    
    No side effects - pure function evaluation.
    """
    
    def __init__(self):
        self.rules = [
            self._rule_critical_degrading,
            self._rule_stable_metrics,
            self._rule_insufficient_data,
            self._rule_recurrent_pattern,
            self._rule_single_alert_low_severity,
        ]
    
    def evaluate(
        self,
        cluster: AlertCluster,
        metrics_result: MetricsAnalysisResult,
        context: Dict
    ) -> Dict:
        """Evaluate all rules and return decision
        
        Args:
            cluster: Alert cluster
            metrics_result: Metrics analysis
            context: Additional context
            
        Returns:
            Dict with decision_state, confidence, rules_applied, justification
        """
        rules_applied = []
        justifications = []
        
        # Evaluate each rule in order
        for rule_func in self.rules:
            result = rule_func(cluster, metrics_result, context)
            
            if result["applies"]:
                rules_applied.append(result["rule_name"])
                justifications.append(result["justification"])
                
                # If rule has high confidence, use it immediately
                if result["confidence"] >= 0.8:
                    return {
                        "decision_state": result["decision_state"],
                        "confidence": result["confidence"],
                        "rules_applied": rules_applied,
                        "justification": "; ".join(justifications)
                    }
        
        # If no high-confidence rule fired, aggregate results
        if rules_applied:
            # Use first applicable rule as default
            return {
                "decision_state": DecisionState.MANUAL_REVIEW,
                "confidence": 0.6,
                "rules_applied": rules_applied,
                "justification": "; ".join(justifications)
            }
        
        # No rules applied - default to investigation
        return {
            "decision_state": DecisionState.MANUAL_REVIEW,
            "confidence": 0.5,
            "rules_applied": ["DEFAULT_INVESTIGATE"],
            "justification": "No specific policy rule matched - default to investigation"
        }
    
    def _rule_critical_degrading(
        self,
        cluster: AlertCluster,
        metrics_result: MetricsAnalysisResult,
        context: Dict
    ) -> Dict:
        """Rule: Critical alerts with degrading metrics = ESCALATE"""
        has_critical = any(
            a.severity == "critical" 
            for a in cluster.alerts
        )
        
        is_degrading = metrics_result.overall_health == TrendClassification.DEGRADING
        
        if has_critical and is_degrading and metrics_result.is_reliable:
            return {
                "applies": True,
                "rule_name": "CRITICAL_DEGRADING_METRICS",
                "decision_state": DecisionState.ESCALATE,
                "confidence": 0.9,
                "justification": "Critical severity with degrading metric trends detected"
            }
        
        return {"applies": False}
    
    def _rule_stable_metrics(
        self,
        cluster: AlertCluster,
        metrics_result: MetricsAnalysisResult,
        context: Dict
    ) -> Dict:
        """Rule: Stable or recovering metrics = CLOSE (formerly AUTO_RESOLVE)"""
        is_stable_or_recovering = metrics_result.overall_health in [
            TrendClassification.STABLE,
            TrendClassification.RECOVERING
        ]
        
        if is_stable_or_recovering and metrics_result.is_reliable:
            return {
                "applies": True,
                "rule_name": "STABLE_METRICS",
                "decision_state": DecisionState.CLOSE,
                "confidence": 0.85,
                "justification": f"Metrics show {metrics_result.overall_health.value} trend"
            }
        
        return {"applies": False}
    
    def _rule_insufficient_data(
        self,
        cluster: AlertCluster,
        metrics_result: MetricsAnalysisResult,
        context: Dict
    ) -> Dict:
        """Rule: Insufficient metric data = HUMAN_REVIEW_REQUIRED"""
        if metrics_result.overall_health == TrendClassification.INSUFFICIENT_DATA:
            return {
                "applies": True,
                "rule_name": "INSUFFICIENT_DATA",
                "decision_state": DecisionState.MANUAL_REVIEW,
                "confidence": 0.7,
                "justification": "Insufficient metric data for automated decision"
            }
        
        return {"applies": False}
    
    def _rule_recurrent_pattern(
        self,
        cluster: AlertCluster,
        metrics_result: MetricsAnalysisResult,
        context: Dict
    ) -> Dict:
        """Rule: Recurrent pattern detected = INVESTIGATE"""
        historical_outcomes = context.get("historical_outcomes", [])
        
        # Check if cluster fingerprint has recurred
        recurrences = [
            o for o in historical_outcomes 
            if o.get("cluster_id") == str(cluster.cluster_id)
        ]
        
        if len(recurrences) >= 2:
            return {
                "applies": True,
                "rule_name": "RECURRENT_PATTERN",
                "decision_state": DecisionState.ESCALATE,
                "confidence": 0.8,
                "justification": f"Pattern recurred {len(recurrences)} times in history"
            }
        
        return {"applies": False}
    
    def _rule_single_alert_low_severity(
        self,
        cluster: AlertCluster,
        metrics_result: MetricsAnalysisResult,
        context: Dict
    ) -> Dict:
        """Rule: Single low/medium severity alert = IGNORE"""
        if cluster.alert_count == 1:
            alert = cluster.alerts[0]
            if alert.severity in ["low", "medium", "info"]:
                return {
                    "applies": True,
                    "rule_name": "SINGLE_LOW_SEVERITY",
                    "decision_state": DecisionState.OBSERVE,
                    "confidence": 0.75,
                    "justification": f"Single {alert.severity} severity alert without correlation"
                }
        
        return {"applies": False}
