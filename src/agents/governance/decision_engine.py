import logging
from uuid import uuid4
from datetime import datetime, timezone

from src.models.swarm import SwarmResult
from src.models.decision import DecisionCandidate, DecisionStatus, AutomationLevel
from src.models.alert import NormalizedAlert

logger = logging.getLogger(__name__)

class DecisionEngine:
    """
    Consolidates analysis from Swarm Agents into a single Decision Candidate.
    """
    
    def __init__(self):
        # Intentionally empty: decision engine holds no runtime state.
        # Kept for DI and future extension.
        pass

    def consolidate(self, alert: NormalizedAlert, swarm_results: list[SwarmResult]) -> DecisionCandidate:
        """
        Aggregates multiple SwarmResults into a single DecisionCandidate using deterministic heuristics
        (and potentially LLM synthesis in future versions).
        """
        logger.info(f"Consolidating {len(swarm_results)} swarm results for alert {alert.fingerprint}")
        
        if not swarm_results:
            return self._create_empty_decision(alert)

        # 1. Identify Primary Hypothesis (Highest Confidence)
        # Sort by confidence descending
        sorted_results = sorted(swarm_results, key=lambda x: x.confidence, reverse=True)
        winner = sorted_results[0]
        
        # 2. Check for conflicts (High confidence disagreement)
        # Logic: if runner-up has > 0.7 confidence and distinct hypothesis, mark as conflicting
        conflicts = []
        # We need a similarity check, but for now strict string inequality
        # In a real system, we'd use semantic similarity
        for res in sorted_results[1:]:
            if res.confidence > 0.7:
                # Simple deduplication check
                if res.hypothesis != winner.hypothesis:
                    conflicts.append(f"[{res.agent_id}] {res.hypothesis}")

        status = DecisionStatus.PROPOSED
        summary = f"Analysis completed by {len(swarm_results)} agents. Primary insight from {winner.agent_id}."
        
        if conflicts:
            summary += f" Note: {len(conflicts)} conflicting high-confidence hypotheses detected."
        
        # 3. Assess Risk & Automation
        # Heuristic rules
        risk = "Medium"
        automation = AutomationLevel.ASSISTED
        
        if winner.confidence > 0.95 and not conflicts:
            risk = "Low"
            automation = AutomationLevel.FULL
        elif winner.confidence < 0.6:
            risk = "High - Low Confidence"
            automation = AutomationLevel.MANUAL
        elif conflicts:
            risk = "High - Conflicting Analysis"
            automation = AutomationLevel.MANUAL

        # 4. Gather Evidence
        # Combine evidence from the winner and maybe consistent supports
        # For now, just take winner's evidence + suggestions
        supporting_evidence = [f"[{e.type.value}] {e.description}" for e in winner.evidence]
        
        return DecisionCandidate(
            decision_id=uuid4(),
            alert_reference=str(alert.fingerprint),
            summary=summary,
            status=status,
            primary_hypothesis=winner.hypothesis,
            risk_assessment=risk,
            automation_level=automation,
            supporting_evidence=supporting_evidence,
            conflicting_hypotheses=conflicts,
            created_at=datetime.now(timezone.utc)
        )

    def _create_empty_decision(self, alert: NormalizedAlert) -> DecisionCandidate:
        return DecisionCandidate(
            decision_id=uuid4(),
            alert_reference=str(alert.fingerprint),
            summary="No analysis results available.",
            status=DecisionStatus.PROPOSED,
            primary_hypothesis="Insufficient data to form hypothesis.",
            risk_assessment="Unknown",
            automation_level=AutomationLevel.MANUAL,
            created_at=datetime.now(timezone.utc)
        )
