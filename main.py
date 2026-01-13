
import asyncio
import logging
from typing import Dict, Any

from swarm_intelligence.core.models import (
    SwarmResult, EvidenceType, Alert, SwarmPlan, SwarmStep,
    Decision, HumanAction, HumanDecision, OperationalOutcome
)
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator
from swarm_intelligence.controller import SwarmController
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.policy.retry_policy import ExponentialBackoffPolicy
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.replay import ReplayEngine

# --- Mock Agent Implementations ---

class ThreatIntelAgent(Agent):
    """An agent that provides threat intelligence, designed to fail intermittently."""
    _attempts = 0

    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        ThreatIntelAgent._attempts += 1
        await asyncio.sleep(0.1)
        if ThreatIntelAgent._attempts <= 2:
            return SwarmResult(agent_id=self.agent_id, output=None, confidence=0.1, actionable=False,
                               evidence_type=EvidenceType.RAW_DATA, error="API_TIMEOUT")
        return SwarmResult(agent_id=self.agent_id, output={"threat_level": "high"}, confidence=0.85,
                           actionable=True, evidence_type=EvidenceType.SEMANTIC)

class LogAnalysisAgent(Agent):
    """A reliable agent for analyzing logs."""
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        await asyncio.sleep(0.05)
        return SwarmResult(agent_id=self.agent_id, output={"error_count": 1024}, confidence=0.98,
                           actionable=True, evidence_type=EvidenceType.METRICS)

# --- Human Governance Hook ---

def expert_human_review(decision: Decision) -> HumanDecision:
    """Simulates an expert overriding a decision, providing a structured reason."""
    logging.info("--- Human Expert Review Initiated ---")
    logging.warning("Expert disagrees with the swarm's proposed action. Providing an override.")
    return HumanDecision(
        action=HumanAction.OVERRIDE,
        author="security_officer_davis",
        override_reason="The proposed action is insufficient. The combination of high threat level and massive error counts indicates a compromised host, requiring immediate isolation.",
        overridden_action_proposed="isolate_host_and_reimage"
    )

# --- Main Execution ---

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        # --- 1. Initialization ---
        neo4j = Neo4jAdapter("bolt://localhost:7687", "neo4j", "password")
        neo4j.setup_schema()
        confidence_service = ConfidenceService(neo4j)
        agents = [ThreatIntelAgent("threat_intel"), LogAnalysisAgent("log_analysis")]
        orchestrator = SwarmOrchestrator(agents)
        controller = SwarmController(orchestrator, confidence_service)
        controller.register_human_hooks(expert_human_review)

        # --- 2. Plan Definition with Policy ---
        retry_policy = ExponentialBackoffPolicy(max_attempts=3, base_delay=0.2)
        plan = SwarmPlan(
            objective="Assess and respond to security alert on host db-prod-01.",
            steps=[
                SwarmStep(agent_id="log_analysis", mandatory=True),
                SwarmStep(agent_id="threat_intel", mandatory=True, retry_policy=retry_policy)
            ]
        )
        alert = Alert(alert_id="sec-alert-991", data={"hostname": "db-prod-01"})

        # --- 3. Live Execution & Governance ---
        decision, history = await controller.aexecute_plan(plan, alert)

        # --- 4. Causal Persistence & Learning ---
        neo4j.save_swarm_run(plan, alert, history, decision)
        if decision.human_decision and decision.human_decision.action == HumanAction.OVERRIDE:
            outcome = OperationalOutcome(status="success")
            neo4j.save_human_override(decision, decision.human_decision, outcome, plan, history)
            logging.info("Human override has been persisted as a learning signal.")
        elif decision.human_decision and decision.human_decision.action == HumanAction.ACCEPT:
            outcome = OperationalOutcome(status="success")
            # In a real system, you would have a mechanism to report the outcome.
            # Here, we assume an accepted decision resulted in a successful outcome.
            if outcome.status == "success":
                for evidence in decision.supporting_evidence:
                    confidence_service.reinforce_for_success(evidence.agent_id)
        # --- 5. Deterministic Replay ---
        logging.info("\n--- Initiating Deterministic Replay for Audit ---")
        replay_engine = ReplayEngine(neo4j)
        report = await replay_engine.replay_decision(plan.plan_id, controller)
        logging.info(f"Replay Report for run {report.run_id}:")
        logging.info(f"  - Original Action: {report.original_action}")
        logging.info(f"  - Replayed Action: {report.replayed_action}")
        logging.info(f"  - Confidence Delta: {report.confidence_delta:.2f}")

    except Exception as e:
        logging.error(f"Execution failed: {e}. Ensure Neo4j is running and accessible.")
    finally:
        if 'neo4j' in locals():
            neo4j.close()

if __name__ == "__main__":
    asyncio.run(main())
