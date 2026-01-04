"""
Report Agent - Generate Structured Audit Reports

Produces human-readable reports and persists decisions.
Coordinates with EmbeddingAgent for post-confirmation persistence.
"""

import logging
from typing import Optional
from uuid import UUID

from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend
from src.models.decision import Decision, DecisionState
from src.models.audit_log import AuditLog
from src.utils.audit_logger import AuditLogger
from src.agents.embedding_agent import EmbeddingAgent

logger = logging.getLogger(__name__)


class ReportAgentError(Exception):
    """Raised when report generation fails."""
    pass


class ReportAgent:
    """
    Agent responsible for:
    1. Generating structured reports for human review
    2. Persisting decisions to audit log
    3. Triggering embedding persistence on confirmation
    
    Constitution Principle IV: Rastreabilidade - All decisions are logged.
    Constitution Principle III: Embeddings only after human confirmation.
    """
    
    AGENT_NAME = "ReportAgent"
    TIMEOUT_SECONDS = 15.0
    AGENT_VERSION = "1.0.0"
    
    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        embedding_agent: Optional[EmbeddingAgent] = None,
    ):
        """
        Initialize report agent.
        
        Args:
            audit_logger: AuditLogger instance.
            embedding_agent: EmbeddingAgent for post-confirmation persistence.
        """
        self._audit_logger = audit_logger or AuditLogger()
        self._embedding_agent = embedding_agent or EmbeddingAgent()
    
    async def generate_report(
        self,
        decision: Decision,
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
    ) -> dict:
        """
        Generate a structured report for human review.
        
        Args:
            decision: The decision to report on.
            cluster: Alert cluster being analyzed.
            trends: Metric trends for the cluster.
        
        Returns:
            Dict containing the formatted report.
        """
        logger.info(
            f"[{self.AGENT_NAME}] Generating report for decision {decision.decision_id}"
        )
        
        # Build report sections
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
        
        logger.info(
            f"[{self.AGENT_NAME}] Report generated: {len(report)} sections"
        )
        
        return report
    
    def persist_decision(
        self,
        decision: Decision,
        cluster: AlertCluster,
    ) -> AuditLog:
        """
        Persist a decision to the audit log.
        
        Args:
            decision: Decision to persist.
            cluster: Alert cluster for context.
        
        Returns:
            The created AuditLog entry.
        """
        alert_fingerprints = [a.fingerprint for a in cluster.alerts]
        
        audit_log = self._audit_logger.log_decision(
            decision=decision,
            cluster_id=cluster.cluster_id,
            alert_fingerprints=alert_fingerprints,
            agent_version=self.AGENT_VERSION,
        )
        
        logger.info(
            f"[{self.AGENT_NAME}] Decision persisted: {audit_log.log_id}"
        )
        
        return audit_log
    
    async def handle_confirmation(
        self,
        decision: Decision,
        cluster: AlertCluster,
        validator_id: str,
    ) -> None:
        """
        Handle human confirmation of a decision.
        
        Constitution Principle III: Embedding persistence only after confirmation.
        
        Args:
            decision: Decision being confirmed.
            cluster: Alert cluster for embedding context.
            validator_id: ID of the human validator.
        """
        logger.info(
            f"[{self.AGENT_NAME}] Handling confirmation for {decision.decision_id} "
            f"by {validator_id}"
        )
        
        # Mark decision as confirmed
        decision.confirm(validator_id)
        
        # Log validation event
        self._audit_logger.log_validation(
            decision_id=decision.decision_id,
            validated_by=validator_id,
            approved=True,
        )
        
        # Persist embedding (Constitution Principle III)
        try:
            point_id = await self._embedding_agent.persist_confirmed_decision(
                decision=decision,
                cluster=cluster,
            )
            
            # Log embedding creation
            self._audit_logger.log_embedding_created(
                decision_id=decision.decision_id,
                point_id=point_id,
            )
            
            logger.info(
                f"[{self.AGENT_NAME}] Embedding persisted: {point_id}"
            )
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Failed to persist embedding: {e}")
            raise ReportAgentError(f"Embedding persistence failed: {e}") from e
    
    async def handle_rejection(
        self,
        decision: Decision,
        validator_id: str,
    ) -> None:
        """
        Handle human rejection of a decision.
        
        Constitution Principle III: NO embedding for rejected decisions.
        
        Args:
            decision: Decision being rejected.
            validator_id: ID of the human validator.
        """
        logger.info(
            f"[{self.AGENT_NAME}] Handling rejection for {decision.decision_id} "
            f"by {validator_id}"
        )
        
        # Mark decision as rejected
        decision.reject(validator_id)
        
        # Log validation event
        self._audit_logger.log_validation(
            decision_id=decision.decision_id,
            validated_by=validator_id,
            approved=False,
        )
        
        # NO embedding persistence for rejected decisions
        logger.info(
            f"[{self.AGENT_NAME}] Rejection logged, no embedding created"
        )
    
    def _build_summary(
        self,
        decision: Decision,
        cluster: AlertCluster,
    ) -> dict:
        """Build report summary section."""
        return {
            "service": cluster.primary_service,
            "severity": cluster.primary_severity,
            "alert_count": cluster.alert_count,
            "recommendation": decision.decision_state.value,
            "confidence": f"{decision.confidence:.0%}",
            "requires_human_review": decision.decision_state == DecisionState.MANUAL_REVIEW,
        }
    
    def _build_cluster_section(self, cluster: AlertCluster) -> dict:
        """Build cluster details section."""
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
                for a in cluster.alerts[:10]  # Limit to first 10
            ],
        }
    
    def _build_trends_section(
        self,
        trends: dict[str, MetricTrend],
    ) -> dict:
        """Build trend analysis section."""
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
        """Build recommendation section."""
        return {
            "action": decision.decision_state.value,
            "confidence": decision.confidence,
            "justification": decision.justification,
            "rules_applied": decision.rules_applied,
            "llm_used": decision.llm_contribution,
            "llm_reason": decision.llm_reason,
        }
    
    def _build_evidence_section(self, decision: Decision) -> dict:
        """Build evidence section (semantic context)."""
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
        """Build audit trail section."""
        return {
            "decision_id": str(decision.decision_id),
            "created_at": decision.created_at.isoformat(),
            "validation_status": decision.human_validation_status.value,
            "validated_by": decision.validated_by,
            "validated_at": (
                decision.validated_at.isoformat()
                if decision.validated_at else None
            ),
        }
    
    def _build_action_section(self, decision: Decision) -> dict:
        """Build available actions section."""
        if decision.is_confirmed:
            return {
                "status": "confirmed",
                "available_actions": [],
            }
        
        return {
            "status": "pending",
            "available_actions": [
                {
                    "action": "approve",
                    "description": "Confirm the recommendation and persist to semantic memory",
                },
                {
                    "action": "reject",
                    "description": "Reject the recommendation (no semantic persistence)",
                },
                {
                    "action": "modify",
                    "description": "Modify the recommendation before confirming",
                },
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
