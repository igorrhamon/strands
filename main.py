
import asyncio
import logging
import hashlib
import random
from typing import Dict, Any

from swarm_intelligence.core.models import (
    Evidence, EvidenceType, Alert, SwarmPlan, SwarmStep,
    Decision, HumanAction, HumanDecision, OperationalOutcome, RetryAttempt, AgentExecution
)
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator
from swarm_intelligence.controller import SwarmController
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.policy.retry_policy import ExponentialBackoffPolicy
from swarm_intelligence.policy.confidence_policy import DefaultConfidencePolicy
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.replay import ReplayEngine

# --- Agent Implementations ---

class ThreatIntelAgent(Agent):
    _attempts = 0

    def __init__(self, agent_id: str):
        logic_str = "if attempts <= 1 then fail else success"
        super().__init__(agent_id, version="1.3", logic_hash=hashlib.md5(logic_str.encode()).hexdigest())

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        ThreatIntelAgent._attempts += 1
        await asyncio.sleep(0.01)

        execution = AgentExecution(
            agent_id=self.agent_id, agent_version=self.version, logic_hash=self.logic_hash,
            step_id=step_id, input_parameters=params
        )

        if ThreatIntelAgent._attempts <= 1:
            execution.error = "API_TIMEOUT"
        else:
            evidence = Evidence(
                source_agent_execution_id=execution.execution_id,
                agent_id=self.agent_id,
                content={"threat_level": "critical"},
                confidence=0.9,
                evidence_type=EvidenceType.SEMANTIC
            )
            execution.output_evidence.append(evidence)

        return execution

class LogAnalysisAgent(Agent):
    def __init__(self, agent_id: str):
        logic_str = "return error_count: 5000"
        super().__init__(agent_id, version="1.0", logic_hash=hashlib.md5(logic_str.encode()).hexdigest())

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        await asyncio.sleep(0.01)
        execution = AgentExecution(
            agent_id=self.agent_id, agent_version=self.version, logic_hash=self.logic_hash,
            step_id=step_id, input_parameters=params
        )
        evidence = Evidence(
            source_agent_execution_id=execution.execution_id,
            agent_id=self.agent_id,
            content={"error_count": 5000},
            confidence=0.95,
            evidence_type=EvidenceType.METRICS
        )
        execution.output_evidence.append(evidence)
        return execution

# --- Human Governance Hook ---

def expert_human_review(decision: Decision) -> HumanDecision:
    logging.info("--- Human Expert Review ---")
    logging.warning("Expert OVERRULES swarm decision.")
    return HumanDecision(action=HumanAction.OVERRIDE, author="chief_analyst_ryu",
                         override_reason="The proposed action is insufficient.",
                         overridden_action_proposed="quarantine_and_reimage_host")

# --- Main Execution ---

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    neo4j = None
    try:
        neo4j = Neo4jAdapter("bolt://localhost:7687", "neo4j", "password")
        neo4j.setup_schema()
        confidence_service = ConfidenceService(neo4j)
        agents = [ThreatIntelAgent("threat_intel"), LogAnalysisAgent("log_analysis")]
        orchestrator = SwarmOrchestrator(agents)
        controller = SwarmController(orchestrator, confidence_service, confidence_policy=DefaultConfidencePolicy())
        controller.register_human_hooks(expert_human_review)

        retry_policy = ExponentialBackoffPolicy(max_attempts=2, base_delay=0.1)
        plan = SwarmPlan(objective="Neutralize threat on host web-prod-03.",
                         steps=[SwarmStep(agent_id="log_analysis", mandatory=True),
                                SwarmStep(agent_id="threat_intel", mandatory=True, retry_policy=retry_policy)])
        alert = Alert(alert_id="sec-alert-101", data={"hostname": "web-prod-03"})
        run_id = f"run-{alert.alert_id}"

        decision, executions, retries, retry_decisions, master_seed = await controller.aexecute_plan(plan, alert, run_id)

        neo4j.save_swarm_run(plan, alert, executions, decision, retries, retry_decisions, master_seed)

        if decision.human_decision:
            outcome = OperationalOutcome(status="success")
            neo4j.save_human_override(decision, decision.human_decision, outcome)
            logging.info("Human override persisted.")

        logging.info("\n--- Initiating Deterministic Replay ---")
        replay_engine = ReplayEngine(neo4j)
        report = await replay_engine.replay_decision(run_id, controller)
        logging.info(f"Replay Report ({report.report_id}) generated and saved.")

    except Exception as e:
        logging.error(f"FATAL: {e}. Is Neo4j running?")
    finally:
        if neo4j:
            neo4j.close()

if __name__ == "__main__":
    asyncio.run(main())
