"""
Report Agent - Generate Structured Audit Reports

Produces human-readable reports and persists decisions.
Constitution Principle IV: Rastreabilidade - All decisions are logged.
"""

import logging
from typing import Optional
from uuid import UUID

from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend
from src.models.decision import Decision, DecisionState
from src.models.audit_log import AuditLog
from src.utils.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class ReportAgentError(Exception):
    """Raised when report generation fails."""
    pass


class ReportAgent:
    """
    Agent responsible for:
    1. Generating structured reports for human review
    2. Persisting decisions to audit log
    
    Constitution Principle IV: Rastreabilidade - All decisions are logged.
    """
    
    AGENT_NAME = "ReportAgent"
    TIMEOUT_SECONDS = 15.0
    AGENT_VERSION = "1.0.0"
    
    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize report agent.
        
        Args:
            audit_logger: AuditLogger instance.
        """
        self._audit_logger = audit_logger or AuditLogger()
    
    async def generate_report(
        self,
        decision: Decision,
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
    ) -> dict:
        """
        Generate a structured report for human review.
        """
        logger.info(
            f"[{self.AGENT_NAME}] Generating report for decision {decision.decision_id}"
        )
        
        report = {
            "report_type": "decision_recommendation",
            "decision_id": str(decision.decision_id),
            "generated_at": decision.created_at.isoformat(),
            "summary": self._build_summary(decision, cluster),
            "cluster_details": self._build_cluster_section(cluster),
            "trend_analysis": self._build_trends_section(trends),
            "recommendation": self._build_recommendation_section(decision),
            "evidence": self._build_evidence_section(decision),
            "audit_trail": self._build_audit_section(decision),
            "actions": self._build_action_section(decision),
        }
        
        return report
    
    def persist_decision(
        self,
        decision: Decision,
        cluster: AlertCluster,
    ) -> AuditLog:
        """Persist a decision to the audit log."""
        alert_fingerprints = [a.fingerprint for a in cluster.alerts]
        
        audit_log = self._audit_logger.log_decision(
            decision=decision,
            cluster_id=cluster.cluster_id,
            alert_fingerprints=alert_fingerprints,
            agent_version=self.AGENT_VERSION,
        )
        
        return audit_log
    
    async def handle_confirmation(
        self,
        decision: Decision,
        cluster: AlertCluster,
        validator_id: str,
    ) -> None:
        """Handle human confirmation of a decision."""
        logger.info(
            f"[{self.AGENT_NAME}] Handling confirmation for {decision.decision_id} by {validator_id}"
        )
        decision.confirm(validator_id)
        self._audit_logger.log_validation(
            decision_id=decision.decision_id,
            validated_by=validator_id,
            approved=True,
        )
    
    async def handle_rejection(
        self,
        decision: Decision,
        validator_id: str,
    ) -> None:
        """Handle human rejection of a decision."""
        logger.info(
            f"[{self.AGENT_NAME}] Handling rejection for {decision.decision_id} by {validator_id}"
        )
        decision.reject(validator_id)
        self._audit_logger.log_validation(
            decision_id=decision.decision_id,
            validated_by=validator_id,
            approved=False,
        )
    
    def _build_summary(self, decision: Decision, cluster: AlertCluster) -> dict:
        return {
            "service": cluster.primary_service,
            "severity": cluster.primary_severity,
            "alert_count": cluster.alert_count,
            "recommendation": decision.decision_state.value,
            "confidence": f"{decision.confidence:.0%}",
            "requires_human_review": decision.decision_state == DecisionState.MANUAL_REVIEW,
        }
    
    def _build_cluster_section(self, cluster: AlertCluster) -> dict:
        return {
            "cluster_id": cluster.cluster_id,
            "primary_service": cluster.primary_service,
            "primary_severity": cluster.primary_severity,
            "correlation_score": cluster.correlation_score,
            "alerts": [
                {
                    "fingerprint": a.fingerprint,
                    "description": a.description,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in cluster.alerts[:10]
            ],
        }
    
    def _build_trends_section(self, trends: dict[str, MetricTrend]) -> dict:
        return {
            "metrics_analyzed": len(trends),
            "trends": [
                {
                    "metric": name,
                    "state": trend.trend_state.value,
                    "confidence": trend.confidence,
                    "data_points": len(trend.data_points),
                }
                for name, trend in trends.items()
            ],
        }
    
    def _build_recommendation_section(self, decision: Decision) -> dict:
        return {
            "action": decision.decision_state.value,
            "confidence": decision.confidence,
            "justification": decision.justification,
            "rules_applied": decision.rules_applied,
            "llm_used": decision.llm_contribution,
            "llm_reason": decision.llm_reason,
        }
    
    def _build_evidence_section(self, decision: Decision) -> dict:
        return {
            "historical_matches": len(decision.semantic_evidence),
            "evidence": [
                {
                    "decision_id": str(e.decision_id),
                    "similarity_score": e.similarity_score,
                    "summary": e.summary,
                }
                for e in decision.semantic_evidence
            ],
        }
    
    def _build_audit_section(self, decision: Decision) -> dict:
        return {
            "decision_id": str(decision.decision_id),
            "created_at": decision.created_at.isoformat(),
            "validation_status": decision.human_validation_status.value,
            "validated_by": decision.validated_by,
            "validated_at": (decision.validated_at.isoformat() if decision.validated_at else None),
        }
    
    def _build_action_section(self, decision: Decision) -> dict:
        if decision.is_confirmed:
            return {"status": "confirmed", "available_actions": []}
        return {
            "status": "pending",
            "available_actions": [
                {"action": "approve", "description": "Confirm the recommendation"},
                {"action": "reject", "description": "Reject the recommendation"},
            ],
        }

# Strands agent tool definition
REPORT_AGENT_TOOL = {
    "name": "generate_report",
    "description": "Generate structured report for a decision",
    "parameters": {
        "type": "object",
        "properties": {
            "decision_id": {
                "type": "string",
                "description": "ID of the decision to report on",
            },
        },
        "required": ["decision_id"],
    },
}
