
import asyncio
import logging
from typing import Dict, Any

from swarm_intelligence.core.models import (
    SwarmResult, EvidenceType, Alert, SwarmPlan, SwarmStep,
    Decision, HumanAction, HumanDecision, OperationalOutcome, ReplayReport
)
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator
from swarm_intelligence.controller import SwarmController
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.policy.retry_policy import ExponentialBackoffPolicy
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.replay import ReplayEngine

# --- Mock Agent Implementations ---

class ThreatIntelAgent(Agent):
    _attempts = 0
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        ThreatIntelAgent._attempts += 1
        await asyncio.sleep(0.01)
        if ThreatIntelAgent._attempts <= 1:
            return SwarmResult(agent_id=self.agent_id, output=None, confidence=0.1, actionable=False,
                               evidence_type=EvidenceType.RAW_DATA, error="API_TIMEOUT")
        return SwarmResult(agent_id=self.agent_id, output={"threat_level": "critical"}, confidence=0.9,
                           actionable=True, evidence_type=EvidenceType.SEMANTIC)

class LogAnalysisAgent(Agent):
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        await asyncio.sleep(0.01)
        return SwarmResult(agent_id=self.agent_id, output={"error_count": 5000}, confidence=0.95,
                           actionable=True, evidence_type=EvidenceType.METRICS)

# --- Human Governance Hook ---

def expert_human_review(decision: Decision) -> HumanDecision:
    logging.info("--- Human Expert Review ---")
    logging.warning("Expert OVERRULES swarm decision.")
    return HumanDecision(
        action=HumanAction.OVERRIDE,
        author="chief_analyst_ryu",
        override_reason="The proposed action is insufficient. This pattern indicates a persistent threat requiring host-level quarantine.",
        overridden_action_proposed="quarantine_and_reimage_host"
    )

# --- Main Execution ---

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    neo4j = None
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
        retry_policy = ExponentialBackoffPolicy(max_attempts=2, base_delay=0.1)
        plan = SwarmPlan(
            objective="Neutralize threat on host web-prod-03.",
            steps=[
                SwarmStep(agent_id="log_analysis", mandatory=True),
                SwarmStep(agent_id="threat_intel", mandatory=True, retry_policy=retry_policy)
            ]
        )
        alert = Alert(alert_id="sec-alert-101", data={"hostname": "web-prod-03"})

        # --- 3. Live Execution & Causal Persistence ---
        decision, history, retries = await controller.aexecute_plan(plan, alert)
        neo4j.save_swarm_run(plan, alert, history, decision, retries)

        # --- 4. Governance and Learning ---
        if decision.human_decision:
            outcome = OperationalOutcome(status="success")
            neo4j.save_human_override(decision, decision.human_decision, outcome, plan, history)
            logging.info("Human override persisted as a learning signal, impacting agent reputations.")

        # --- 5. Deterministic Replay for Audit ---
        logging.info("\n--- Initiating Deterministic Replay ---")
        replay_engine = ReplayEngine(neo4j)
        report = await replay_engine.replay_decision(plan.plan_id, controller)
        logging.info(f"Replay Report ({report.report_id}) generated and saved.")

    except Exception as e:
        logging.error(f"FATAL: {e}. Is Neo4j running?")
    finally:
        if neo4j:
            neo4j.close()

if __name__ == "__main__":
    asyncio.run(main())
