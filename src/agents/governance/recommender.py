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
        
        # Enhanced heuristic logic
        hypothesis_lower = candidate.primary_hypothesis.lower()
        
        if "cpu" in hypothesis_lower:
            candidate.risk_assessment += ". Standard CPU saturation playbook applies."
            candidate.suggested_actions.append("Check CPU limits and requests via 'kubectl describe pod'.")
        
        elif "memory" in hypothesis_lower or "oom" in hypothesis_lower:
            candidate.risk_assessment += ". High risk of OOMKilled."
            candidate.suggested_actions.append("Check memory usage trends and consider increasing limits.")
            
        elif "crashloopbackoff" in hypothesis_lower or "restarting" in hypothesis_lower:
            candidate.risk_assessment += ". Service instability detected."
            candidate.suggested_actions.append("Check application logs for startup errors.")
            candidate.suggested_actions.append("Verify liveness/readiness probes configuration.")
            
        elif "timeout" in hypothesis_lower or "latency" in hypothesis_lower:
            candidate.risk_assessment += ". Performance degradation."
            candidate.suggested_actions.append("Check downstream dependencies (database, external APIs).")
            candidate.suggested_actions.append("Verify network policies and service endpoints.")

        # Incorporate insights from similar incidents if available in summary
        if "similar incident" in candidate.summary.lower():
             candidate.risk_assessment += ". Recurrent issue pattern detected."

        # Verify Automation Level constraints
        # E.g., if risk is High, force Manual
        if "High" in candidate.risk_assessment and candidate.automation_level != AutomationLevel.MANUAL:
            logger.warning(f"Downgrading automation level to MANUAL due to High Risk for {candidate.decision_id}")
            candidate.automation_level = AutomationLevel.MANUAL
            candidate.summary += " (Automation downgraded due to Risk)"

        return candidate
