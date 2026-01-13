
import asyncio
import logging
import random
from typing import Dict, Any, List

from swarm_intelligence.core.models import (
    SwarmResult,
    EvidenceType,
    Alert,
    SwarmPlan,
    SwarmStep,
    Decision,
    HumanAction,
    HumanDecision,
    OperationalOutcome,
)
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator
from swarm_intelligence.controller import SwarmController
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter

# --- 1. Mock Agent Implementations ---

class MetricsAgent(Agent):
    """A deterministic agent that usually succeeds with high confidence."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        await asyncio.sleep(0.1) # Simulate I/O
        return SwarmResult(
            agent_id=self.agent_id,
            output={"cpu_usage": 0.95, "status": "critical"},
            confidence=0.98,
            actionable=True,
            evidence_type=EvidenceType.METRICS,
        )

# Global state to simulate transient failure
semantic_agent_attempts = 0

class SemanticAnalysisAgent(Agent):
    """An agent that might fail on the first try but succeeds on retry."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        global semantic_agent_attempts
        semantic_agent_attempts += 1

        await asyncio.sleep(0.2) # Simulate I/O

        if semantic_agent_attempts <= 1:
            return SwarmResult(
                agent_id=self.agent_id,
                output=None,
                confidence=0.2,
                actionable=False,
                evidence_type=EvidenceType.SEMANTIC,
                error="Failed to connect to embedding model."
            )

        return SwarmResult(
            agent_id=self.agent_id,
            output={"threat_level": "high", "entities": ["login_service"]},
            confidence=0.85,
            actionable=True,
            evidence_type=EvidenceType.SEMANTIC,
        )

class RuleValidationAgent(Agent):
    """An agent that consistently fails, forcing an escalation."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        await asyncio.sleep(0.1) # Simulate I/O
        return SwarmResult(
            agent_id=self.agent_id,
            output={"reason": "Rule 'critical_cpu_and_high_threat' is misconfigured."},
            confidence=0.4,
            actionable=False,
            evidence_type=EvidenceType.RULES,
            error="Rule evaluation failed."
        )

class LLMAgent(Agent):
    """A mock LLM agent that provides a hypothesis when deterministic methods fail."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        await asyncio.sleep(0.5) # Simulate a slower LLM call

        objective = params.get("objective")
        failed_steps = params.get("failed_steps")

        return SwarmResult(
            agent_id=self.agent_id,
            output={
                "summary": f"Based on the failure of {len(failed_steps)} agents, the likely root cause is a cascading failure originating from the login service.",
                "action": "isolate_login_service_and_reboot"
            },
            confidence=0.75, # LLMs provide hypotheses, so confidence is not 1.0
            actionable=True,
            evidence_type=EvidenceType.HYPOTHESIS,
        )

# --- 2. Human-in-the-Loop Hook Implementations ---

def human_review_decision(decision: Decision) -> HumanDecision:
    """
    Simulates a human expert reviewing the swarm's decision.
    In this scenario, the human disagrees and provides an override.
    """
    logging.info("--- HUMAN REVIEW REQUIRED ---")
    logging.info(f"Swarm's Proposed Action: {decision.action_proposed}")

    # Simulate a human deciding the swarm's action is too risky
    if "isolate" in decision.action_proposed:
        logging.warning("Human disagrees with the proposed action. Providing an override.")
        return HumanDecision(
            action=HumanAction.OVERRIDE,
            author="senior_engineer_jane",
            override_reason="Isolating the service is too disruptive during peak hours. A rolling restart is safer.",
            overridden_action_proposed="rolling_restart_login_service",
            domain_expertise="SRE"
        )

    logging.info("Human agrees with the proposed action.")
    return HumanDecision(action=HumanAction.ACCEPT, author="operator_john")


# --- 3. End-to-End Execution Flow ---

async def main():
    """Main function to run the end-to-end example."""
    logging.info("--- Starting Governed Cognitive Swarm Example ---")

    # --- Setup ---
    agents = [
        MetricsAgent("metrics_agent"),
        SemanticAnalysisAgent("semantic_agent"),
        RuleValidationAgent("rules_agent"),
        LLMAgent("llm_agent"),
    ]
    orchestrator = SwarmOrchestrator(agents)
    controller = SwarmController(orchestrator, max_retries=1, llm_agent_id="llm_agent")

    # Register the human governance hooks
    controller.register_human_hooks(human_review_decision)

    # --- Data ---
    alert = Alert(alert_id="alert-12345", data={"source_ip": "192.168.1.100"})

    # Note: The 'rules_agent' is mandatory and will fail, triggering LLM escalation.
    # The 'semantic_agent' will fail once and then succeed on retry.
    plan = SwarmPlan(
        objective="Investigate and respond to critical CPU alert on login service.",
        steps=[
            SwarmStep(agent_id="metrics_agent", mandatory=True, min_confidence=0.9),
            SwarmStep(agent_id="semantic_agent", mandatory=True, retryable=True, min_confidence=0.8),
            SwarmStep(agent_id="rules_agent", mandatory=True, retryable=False),
        ]
    )

    # --- Execution ---
    logging.info(f"Executing swarm plan for objective: {plan.objective}")
    final_decision, run_history = await controller.aexecute_plan(plan, alert)

    # --- Output ---
    logging.info("--- Final Decision ---")
    logging.info(f"Swarm Decision ID: {final_decision.decision_id}")
    if final_decision.human_decision:
        hd = final_decision.human_decision
        logging.info(f"Human Action: {hd.action.value}")
        logging.info(f"Human Author: {hd.author} ({hd.domain_expertise})")
        if hd.action == HumanAction.OVERRIDE:
            logging.info(f"  Overridden Action: {hd.overridden_action_proposed}")
            logging.info(f"  Reason: {hd.override_reason}")

    # The final action to take is the human's override, if it exists
    authoritative_action = (final_decision.human_decision.overridden_action_proposed
                            if final_decision.human_decision and final_decision.human_decision.action == HumanAction.OVERRIDE
                            else final_decision.action_proposed)
    logging.info(f"\nAuthoritative Action to Execute: {authoritative_action}")


    # --- 4. Neo4j Persistence (Conceptual) ---
    neo4j = Neo4jAdapter("bolt://localhost:7687", "neo4j", "password")
    logging.info("\n--- Persisting Swarm Run to Neo4j (Stubbed) ---")
    neo4j.save_swarm_run(alert, plan, final_decision, run_history)

    if final_decision.human_decision and final_decision.human_decision.action == HumanAction.OVERRIDE:
        logging.info("\n--- Persisting Human Override to Neo4j (Stubbed) ---")
        # Simulate an outcome after the human's action was taken
        outcome = OperationalOutcome(status="success", resolution_time_seconds=300.5)
        neo4j.save_human_override(final_decision, final_decision.human_decision, outcome)

    neo4j.close()


if __name__ == "__main__":
    asyncio.run(main())
