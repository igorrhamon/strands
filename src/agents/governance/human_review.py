import logging
from uuid import UUID, uuid4
from datetime import datetime, timezone
from src.models.decision import DecisionCandidate, DecisionValidation, DecisionStatus
from src.graph.neo4j_repo import Neo4jRepository

logger = logging.getLogger(__name__)

class HumanReviewAgent:
    """
    Manages the Human-in-the-Loop workflow, capturing operator feedback
    and transitioning decision states.
    """
    
    def __init__(self, repo: Neo4jRepository):
        self.repo = repo

    def process_review(self, candidate: DecisionCandidate, validation: DecisionValidation) -> DecisionCandidate:
        """
        Applies human validation to a decision candidate and persists the outcome.
        """
        logger.info(f"Processing review for decision {candidate.decision_id}: Approved={validation.is_approved}")
        
        if str(candidate.decision_id) != str(validation.decision_id):
            raise ValueError(f"Validation ID mismatch: {candidate.decision_id} vs {validation.decision_id}")

        # Update status based on validation
        if validation.is_approved:
            candidate.status = DecisionStatus.APPROVED
            logger.info(f"Decision {candidate.decision_id} APPROVED.")
        else:
            candidate.status = DecisionStatus.REJECTED
            logger.info(f"Decision {candidate.decision_id} REJECTED. Feedback: {validation.feedback}")
            
        # Update persistence
        # We assume the candidate node already exists (Phase 5)
        # We need to update its property and/add a Review node? 
        # Spec says: "Update Graph with Decision Outcome"
        
        self.repo.record_decision_outcome(validation)
        return candidate

    def review_decision(self, decision_id: str, is_approved: bool, validated_by: str, feedback: str = None) -> bool:
        v = DecisionValidation(validation_id=f"val-{uuid4()}", decision_id=UUID(decision_id), validated_by=validated_by, is_approved=is_approved, feedback=feedback, validated_at=datetime.now(timezone.utc))
        try:
            self.repo.record_decision_outcome(v)
            return True
        except Exception:
            return False
