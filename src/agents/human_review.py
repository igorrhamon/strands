"""Human Review Agent - handles human-in-the-loop review"""
from typing import Optional
import logging
from datetime import datetime, timezone

from src.models.decision import Decision, DecisionValidation, DecisionState
from src.models.audit import AuditLog, AuditEventType


logger = logging.getLogger(__name__)


class HumanReviewAgent:
    """
    Agent responsible for human review workflow.
    
    Input: Decision
    Output: DecisionValidation (after human review)
    Side Effects: Blocks until human provides feedback, logs audit events
    """
    
    def __init__(self):
        self.agent_name = "HumanReviewAgent"
        self.pending_reviews = {}
    
    def request_review(self, decision: Decision) -> str:
        """Request human review for a decision
        
        Args:
            decision: Decision requiring review
            
        Returns:
            Review request ID
        """
        review_id = f"review_{decision.decision_id}_{int(datetime.now(timezone.utc).timestamp())}"
        
        self.pending_reviews[review_id] = {
            "decision": decision,
            "requested_at": datetime.now(timezone.utc),
            "status": "pending"
        }
        
        logger.info(f"Human review requested for decision {decision.decision_id}")
        
        # Audit log
        AuditLog.create(
            event_type=AuditEventType.HUMAN_REVIEW,
            agent_name=self.agent_name,
            entity_id=str(decision.decision_id),  # Convert UUID to string
            event_data={
                "review_id": review_id,
                "decision_state": decision.decision_state.value,
                "confidence": decision.confidence,
                "status": "requested"
            }
        )
        
        return review_id
    
    def submit_review(
        self,
        review_id: str,
        reviewer: str,
        is_approved: bool,
        feedback: str,
        corrected_decision: Optional[DecisionState] = None
    ) -> DecisionValidation:
        """Submit human review feedback
        
        Args:
            review_id: Review request ID
            reviewer: Human reviewer identifier
            is_approved: Whether decision is approved
            feedback: Human feedback/reasoning
            corrected_decision: Optional corrected decision state
            
        Returns:
            DecisionValidation object
        """
        if review_id not in self.pending_reviews:
            raise ValueError(f"Review ID {review_id} not found")
        
        review_data = self.pending_reviews[review_id]
        decision = review_data["decision"]
        
        validation = DecisionValidation(
            validation_id=f"val_{review_id}",
            decision_id=decision.decision_id,
            validated_by=reviewer,
            is_approved=is_approved,
            feedback=feedback,
            corrected_decision=corrected_decision,
            validated_at=datetime.now(timezone.utc)
        )
        
        # Update review status
        self.pending_reviews[review_id]["status"] = "completed"
        self.pending_reviews[review_id]["validation"] = validation
        
        logger.info(
            f"Review {review_id} completed by {reviewer}: "
            f"{'approved' if is_approved else 'rejected'}"
        )
        
        # Audit log
        AuditLog.create(
            event_type=AuditEventType.HUMAN_REVIEW,
            agent_name=self.agent_name,
            entity_id=str(decision.decision_id),  # Convert UUID to string
            event_data={
                "review_id": review_id,
                "reviewer": reviewer,
                "is_approved": is_approved,
                "corrected_decision": corrected_decision.value if corrected_decision else None,
                "status": "completed"
            }
        )
        
        return validation
    
    def get_pending_reviews(self) -> list:
        """Get all pending review requests
        
        Returns:
            List of pending review request dicts
        """
        return [
            {
                "review_id": rid,
                "decision_id": data["decision"].decision_id,
                "requested_at": data["requested_at"],
                "decision_state": data["decision"].decision_state.value,
                "confidence": data["decision"].confidence
            }
            for rid, data in self.pending_reviews.items()
            if data["status"] == "pending"
        ]
