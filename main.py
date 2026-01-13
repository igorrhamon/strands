
import asyncio
import logging
from typing import Dict, Any, List

# Core Models and Components
from swarm_intelligence.core.models import (
    SwarmResult, EvidenceType, Alert, SwarmPlan, SwarmStep,
    Decision, HumanAction, HumanDecision, OperationalOutcome
)
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator
from swarm_intelligence.controller import SwarmController

# Expert-Level Frameworks
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.policy.retry_policy import ExponentialBackoffRetryPolicy
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.replay import ReplayEngine

# --- 1. Mock Agent Implementations ---

class MetricsAgent(Agent):
    """A deterministic agent that succeeds reliably."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        await asyncio.sleep(0.05)
        return SwarmResult(agent_id=self.agent_id, output={"cpu": 0.8}, confidence=0.99, actionable=True, evidence_type=EvidenceType.METRICS)

semantic_agent_attempts = 0
class SemanticAnalysisAgent(Agent):
    """An agent designed to fail twice before succeeding, to test retry policies."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        global semantic_agent_attempts
        semantic_agent_attempts += 1
        await asyncio.sleep(0.1)
        if semantic_agent_attempts <= 2:
            return SwarmResult(agent_id=self.agent_id, output=None, confidence=0.1, actionable=False, evidence_type=EvidenceType.SEMANTIC, error="API connection timed out")
        return SwarmResult(agent_id=self.agent_id, output={"threat_signature": "SIG-001"}, confidence=0.8, actionable=True, evidence_type=EvidenceType.SEMANTIC)

class LLMAgent(Agent):
    """A mock LLM agent for hypothesis generation."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        await asyncio.sleep(0.2)
        return SwarmResult(agent_id=self.agent_id, output={"summary": "Likely crypto-mining activity.", "action": "isolate_and_scan"}, confidence=0.7, actionable=True, evidence_type=EvidenceType.HYPOTHESIS)

# --- 2. Human-in-the-Loop Hook ---

def human_review_decision(decision: Decision) -> HumanDecision:
    """Simulates a human expert overriding the swarm's decision."""
    logging.info("--- HUMAN REVIEW REQUIRED ---")
    logging.info(f"Swarm's Proposed Action: {decision.action_proposed}")
    logging.warning("Human disagrees. Overriding with a safer, more informed action.")
    return HumanDecision(
        action=HumanAction.OVERRIDE,
        author="expert_analyst_carlos",
        override_reason="Isolating is too slow. The signature matches a known threat that requires immediate kernel-level quarantine.",
        overridden_action_proposed="kernel_quarantine_and_reboot"
    )

# --- 3. End-to-End Execution Flow ---

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("--- Starting Expert-Level Swarm Intelligence System ---")

    # --- Setup ---
    # NOTE: In production, these credentials would come from a secure config.
    neo4j_adapter = Neo4jAdapter("bolt://localhost:7687", "neo4j", "password")
    neo4j_adapter.setup_schema()

    confidence_service = ConfidenceService(neo4j_adapter)

    agents = [MetricsAgent("metrics_agent"), SemanticAnalysisAgent("semantic_agent"), LLMAgent("llm_agent")]
    orchestrator = SwarmOrchestrator(agents)
    controller = SwarmController(orchestrator, confidence_service, llm_agent_id="llm_agent")
    controller.register_human_hooks(human_review_decision)

    # --- Define Plan with Policies ---
    alert = Alert(alert_id="alert-777", data={"hostname": "web-prod-1"})

    # The semantic_agent will use a retry policy. It will fail twice then succeed.
    retry_policy = ExponentialBackoffRetryPolicy(max_retries=3, base_delay=0.1)

    plan = SwarmPlan(
        objective="Investigate and neutralize potential threat on web-prod-1.",
        steps=[
            SwarmStep(agent_id="metrics_agent", mandatory=True),
            SwarmStep(agent_id="semantic_agent", mandatory=True, retry_policy=retry_policy, min_confidence=0.7),
            # No LLM in the initial plan, it's for escalation only.
        ]
    )

    # --- Execution ---
    final_decision, run_history = await controller.aexecute_plan(plan, alert)

    # --- Governance and Learning ---
    if final_decision.human_decision:
        hd = final_decision.human_decision
        if hd.action == HumanAction.OVERRIDE:
            logging.info("Applying confidence penalty due to human override.")
            for evidence in final_decision.supporting_evidence:
                confidence_service.penalize_agent_after_override(evidence.agent_id)

    # --- Persistence ---
    logging.info("\n--- Persisting Causal Graph to Neo4j ---")
    neo4j_adapter.save_swarm_run(plan, alert, run_history, final_decision)

    if final_decision.human_decision:
        outcome = OperationalOutcome(status="success", impact_level="low", resolution_time_seconds=120)
        neo4j_adapter.save_human_override(final_decision, final_decision.human_decision, outcome)

    # --- Replay for Audit ---
    logging.info("\n--- Initiating Decision Replay for Audit ---")
    replay_engine = ReplayEngine(neo4j_adapter)
    # In a real scenario, you would pass a controller with updated policies/agents
    replay_report = await replay_engine.replay_run(plan.plan_id, controller)

    logging.info("--- Replay Report ---")
    logging.info(f"Original Decision: {replay_report.original_decision}")
    logging.info(f"Replayed Action: {replay_report.replayed_decision.action_proposed}")
    logging.info(f"Confidence Delta: {replay_report.confidence_delta:.2f}")
    for divergence in replay_report.divergences:
        logging.warning(f"Divergence Found: {divergence}")

    # --- Cleanup ---
    neo4j_adapter.close()

if __name__ == "__main__":
    # A running Neo4j instance is required for this example.
    # e.g., via Docker: docker run --rm -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/password neo4j:latest
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"An error occurred: {e}. Is Neo4j running and accessible?")
