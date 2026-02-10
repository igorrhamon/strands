import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock

from swarm_intelligence.core.models import (
    Evidence, EvidenceType, Alert, SwarmPlan, SwarmStep,
    Decision, Domain, SwarmRun, AgentExecution
)
from swarm_intelligence.core.enums import RiskLevel
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator
from swarm_intelligence.coordinators.swarm_run_coordinator import SwarmRunCoordinator
from swarm_intelligence.controllers.swarm_execution_controller import SwarmExecutionController
from swarm_intelligence.controllers.swarm_retry_controller import SwarmRetryController
from swarm_intelligence.controllers.swarm_decision_controller import SwarmDecisionController
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.policy.retry_policy import ExponentialBackoffPolicy

class MockAgent(Agent):
    def __init__(self, agent_id: str, should_fail_once: bool = False):
        super().__init__(agent_id)
        self.should_fail_once = should_fail_once
        self.attempts = 0

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        self.attempts += 1
        execution = AgentExecution(
            agent_id=self.agent_id, agent_version=self.version, logic_hash=self.logic_hash,
            step_id=step_id, input_parameters=params
        )

        if self.should_fail_once and self.attempts == 1:
            execution.error = Exception("Transient failure")
        else:
            execution.output_evidence.append(Evidence(
                source_agent_execution_id=execution.execution_id,
                agent_id=self.agent_id,
                content={"status": "ok"},
                confidence=0.9,
                evidence_type=EvidenceType.METRICS
            ))
        return execution

@pytest.mark.asyncio
async def test_swarm_run_coordinator_execution():
    # Setup
    agents = [MockAgent("agent_1", should_fail_once=True)]
    orchestrator = SwarmOrchestrator(agents)

    execution_controller = SwarmExecutionController(orchestrator)
    retry_controller = SwarmRetryController()

    # Mock confidence service and decision controller
    mock_confidence_service = MagicMock(spec=ConfidenceService)
    mock_confidence_service.get_last_confidence.return_value = 0.8

    mock_decision_controller = MagicMock(spec=SwarmDecisionController)
    mock_decision_controller.decide = AsyncMock(return_value=Decision(
        summary="Test decision", action_proposed="test", confidence=0.9, supporting_evidence=[]
    ))

    coordinator = SwarmRunCoordinator(
        execution_controller,
        retry_controller,
        mock_decision_controller,
        mock_confidence_service
    )

    domain = Domain(id="d1", name="Test", description="Test", risk_level=RiskLevel.LOW)
    retry_policy = ExponentialBackoffPolicy(max_attempts=2, base_delay=0.01)
    plan = SwarmPlan(objective="Test objective", steps=[
        SwarmStep(agent_id="agent_1", mandatory=True, retry_policy=retry_policy)
    ])
    alert = Alert(alert_id="a1", data={})

    # Execute - This should now NOT raise NameError
    swarm_run, retry_attempts, retry_decisions = await coordinator.aexecute_plan(
        domain, plan, alert, "run-1"
    )

    assert isinstance(swarm_run, SwarmRun)
    assert len(swarm_run.executions) == 2  # One fail, one success
    assert swarm_run.executions[0].error is not None
    assert swarm_run.executions[1].error is None
    assert len(retry_attempts) == 1
    assert swarm_run.final_decision is not None
