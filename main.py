
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

def human_confirm_decision(decision: Decision) -> bool:
    """Simulates a human confirming a decision."""
    logging.info("--- HUMAN CONFIRMATION REQUIRED ---")
    logging.info(f"Summary: {decision.summary}")
    logging.info(f"Proposed Action: {decision.action_proposed}")
    logging.info(f"Confidence: {decision.confidence:.2f}")
    # In a real system, this would involve a UI or a chat message.
    # For this example, we'll auto-approve.
    user_input = "yes"
    logging.info(f"Human response: {user_input}")
    return user_input.lower() == "yes"

def human_reject_decision(decision: Decision):
    """Simulates a human rejecting a decision."""
    logging.error("--- HUMAN REJECTED DECISION ---")
    logging.error(f"Reason for rejection can be logged here.")
    # This could trigger an alert to a human operator.


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
    controller.register_human_hooks(human_confirm_decision, human_reject_decision)

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
    logging.info(f"ID: {final_decision.decision_id}")
    logging.info(f"Summary: {final_decision.summary}")
    logging.info(f"Action Proposed: {final_decision.action_proposed}")
    logging.info(f"Confidence: {final_decision.confidence:.2f}")
    logging.info(f"Is Human Confirmed: {final_decision.is_human_confirmed}")
    logging.info("Supporting Evidence:")
    for evidence in final_decision.supporting_evidence:
        logging.info(f"  - Agent: {evidence.agent_id}, Success: {evidence.is_successful()}, Confidence: {evidence.confidence:.2f}, Type: {evidence.evidence_type.value}")


    # --- 4. Neo4j Persistence (Conceptual) ---
    if final_decision.is_human_confirmed:
        logging.info("\n--- Persisting to Neo4j (Stubbed) ---")
        neo4j = Neo4jAdapter("bolt://localhost:7687", "neo4j", "password")

        # Get and print schema
        schema = neo4j.get_schema_constraints()
        logging.info("Neo4j Schema would be applied:\n" + schema)

        # Save the run
        neo4j.save_swarm_run(alert, plan, final_decision, run_history)
        neo4j.close()
    else:
        logging.warning("\n--- Decision not confirmed. Skipping persistence. ---")


if __name__ == "__main__":
    asyncio.run(main())
