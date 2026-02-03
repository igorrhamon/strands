import logging
from src.models.decision import DecisionCandidate, AutomationLevel

logger = logging.getLogger(__name__)

class RecommenderAgent:
    """
    Analyzes Decision Candidates to propose specific technical actions,
    refine risk assessments, and validate automation levels.
    """
    
    agent_id = "recommender"

    def refine_recommendation(self, candidate: DecisionCandidate) -> DecisionCandidate:
        """
        Refines the DecisionCandidate with specific action plans.
        """
        logger.info(f"[{self.agent_id}] Refining recommendation for {candidate.decision_id}")
        
        # Logic to augment the candidate with actionable steps
        # This simulates an LLM call: "Given hypothesis X, what are the steps to fix?"
        
        if "CPU" in candidate.primary_hypothesis:
            candidate.risk_assessment += ". Standard CPU saturation playbook applies."
            # In future: candidate.suggested_commands = ["kubectl get pods", "top"]
        
        elif "Memory" in candidate.primary_hypothesis:
            candidate.risk_assessment += ". Potential OOM Killer risk."
        
        # Verify Automation Level constraints
        # E.g., if risk is High, force Manual
        if "High" in candidate.risk_assessment and candidate.automation_level != AutomationLevel.MANUAL:
            logger.warning(f"Downgrading automation level to MANUAL due to High Risk for {candidate.decision_id}")
            candidate.automation_level = AutomationLevel.MANUAL
            candidate.summary += " (Automation downgraded due to Risk)"

        return candidate
