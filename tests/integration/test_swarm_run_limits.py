import pytest
import asyncio
import time
from typing import Dict, Any, List
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
from swarm_intelligence.policy.retry_policy import RetryPolicy, RetryContext

class AlwaysFailRetryPolicy(RetryPolicy):
    def __init__(self, max_attempts: int = 100):
        super().__init__()
        self.max_attempts = max_attempts
        self.logic_hash = "test_hash"

    def should_retry(self, context: RetryContext) -> bool:
        return context.attempt < self.max_attempts

    def next_delay(self, context: RetryContext) -> float:
        return 0.01

    def to_dict(self) -> Dict[str, Any]:
        return {"max_attempts": self.max_attempts}

class MockFailingAgent(Agent):
    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        execution = AgentExecution(
            agent_id=self.agent_id, agent_version=self.version, logic_hash=self.logic_hash,
            step_id=step_id, input_parameters=params
        )
        execution.error = Exception("Permanent failure")
        return execution

class MockHangingAgent(Agent):
    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        await asyncio.sleep(10)
        return AgentExecution(
            agent_id=self.agent_id, agent_version=self.version, logic_hash=self.logic_hash,
            step_id=step_id, input_parameters=params
        )

@pytest.mark.asyncio
async def test_max_retry_rounds():
    agents = [MockFailingAgent("agent_1")]
    orchestrator = SwarmOrchestrator(agents)
    execution_controller = SwarmExecutionController(orchestrator)
    retry_controller = SwarmRetryController()
    mock_confidence_service = MagicMock(spec=ConfidenceService)
    mock_confidence_service.get_last_confidence.return_value = 0.5
    mock_decision_controller = MagicMock(spec=SwarmDecisionController)
    mock_decision_controller.decide = AsyncMock(return_value=Decision(
        summary="Test", action_proposed="test", confidence=0.5, supporting_evidence=[]
    ))

    coordinator = SwarmRunCoordinator(
        execution_controller, retry_controller, mock_decision_controller, mock_confidence_service
    )

    domain = Domain(id="d1", name="Test", description="Test", risk_level=RiskLevel.LOW)
    plan = SwarmPlan(objective="Test", steps=[
        SwarmStep(agent_id="agent_1", mandatory=True, retry_policy=AlwaysFailRetryPolicy(max_attempts=100))
    ])

    # Set max_retry_rounds to 3
    swarm_run, _, _ = await coordinator.aexecute_plan(
        domain, plan, Alert(alert_id="a1"), "run-1",
        max_retry_rounds=3
    )

    assert swarm_run.metadata["total_rounds"] == 3
    assert swarm_run.metadata["aborted_by_limit"] is True
    assert len(swarm_run.executions) == 3

@pytest.mark.asyncio
async def test_max_total_attempts():
    agents = [MockFailingAgent("agent_1"), MockFailingAgent("agent_2")]
    orchestrator = SwarmOrchestrator(agents)
    execution_controller = SwarmExecutionController(orchestrator)
    retry_controller = SwarmRetryController()
    mock_confidence_service = MagicMock(spec=ConfidenceService)
    mock_confidence_service.get_last_confidence.return_value = 0.5
    mock_decision_controller = MagicMock(spec=SwarmDecisionController)
    mock_decision_controller.decide = AsyncMock(return_value=Decision(
        summary="Test", action_proposed="test", confidence=0.5, supporting_evidence=[]
    ))

    coordinator = SwarmRunCoordinator(
        execution_controller, retry_controller, mock_decision_controller, mock_confidence_service
    )

    domain = Domain(id="d1", name="Test", description="Test", risk_level=RiskLevel.LOW)
    plan = SwarmPlan(objective="Test", steps=[
        SwarmStep(agent_id="agent_1", mandatory=True, retry_policy=AlwaysFailRetryPolicy()),
        SwarmStep(agent_id="agent_2", mandatory=True, retry_policy=AlwaysFailRetryPolicy())
    ])

    # Set max_total_attempts to 3
    swarm_run, _, _ = await coordinator.aexecute_plan(
        domain, plan, Alert(alert_id="a1"), "run-1",
        max_total_attempts=3
    )

    assert swarm_run.metadata["total_attempts"] == 4
    assert swarm_run.metadata["aborted_by_limit"] is True
    assert len(swarm_run.executions) == 4

@pytest.mark.asyncio
async def test_max_runtime_seconds():
    agents = [MockHangingAgent("agent_1")]
    orchestrator = SwarmOrchestrator(agents, step_timeout=1.0)
    execution_controller = SwarmExecutionController(orchestrator)
    retry_controller = SwarmRetryController()
    mock_confidence_service = MagicMock(spec=ConfidenceService)
    mock_confidence_service.get_last_confidence.return_value = 0.5
    mock_decision_controller = MagicMock(spec=SwarmDecisionController)
    mock_decision_controller.decide = AsyncMock(return_value=Decision(
        summary="Test", action_proposed="test", confidence=0.5, supporting_evidence=[]
    ))

    coordinator = SwarmRunCoordinator(
        execution_controller, retry_controller, mock_decision_controller, mock_confidence_service
    )

    domain = Domain(id="d1", name="Test", description="Test", risk_level=RiskLevel.LOW)
    plan = SwarmPlan(objective="Test", steps=[
        SwarmStep(agent_id="agent_1", mandatory=True, retry_policy=AlwaysFailRetryPolicy())
    ])

    # Mock evaluate to return a large delay, and mock sleep to verify it's cancelled
    retry_controller.evaluate = AsyncMock(return_value=MagicMock(
        steps_to_retry=[plan.steps[0]],
        retry_attempts=[],
        retry_decisions=[],
        max_delay_seconds=10.0,
        newly_successful_step_ids=set()
    ))

    start_time = time.time()
    swarm_run, _, _ = await coordinator.aexecute_plan(
        domain, plan, Alert(alert_id="a1"), "run-1",
        max_runtime_seconds=0.5
    )
    end_time = time.time()

    # It should take around 0.5 seconds + some overhead for execution
    assert end_time - start_time < 2.0
    assert swarm_run.metadata["aborted_by_limit"] is True

@pytest.mark.asyncio
async def test_llm_fallback_conditions():
    # Case 1: Confidence too low, fallback should NOT trigger
    agents = [MockFailingAgent("agent_1"), MockFailingAgent("llm_agent")]
    orchestrator = SwarmOrchestrator(agents)
    execution_controller = SwarmExecutionController(orchestrator)
    retry_controller = SwarmRetryController()
    mock_confidence_service = MagicMock(spec=ConfidenceService)
    mock_confidence_service.get_last_confidence.return_value = 0.5
    mock_decision_controller = MagicMock(spec=SwarmDecisionController)
    mock_decision_controller.decide = AsyncMock(return_value=Decision(
        summary="Test", action_proposed="test", confidence=0.3, supporting_evidence=[]
    ))

    coordinator = SwarmRunCoordinator(
        execution_controller, retry_controller, mock_decision_controller, mock_confidence_service,
        llm_agent_id="llm_agent"
    )

    domain = Domain(id="d1", name="Test", description="Test", risk_level=RiskLevel.LOW)
    plan = SwarmPlan(objective="Test", steps=[
        SwarmStep(agent_id="agent_1", mandatory=True, retry_policy=AlwaysFailRetryPolicy(max_attempts=1))
    ])

    # llm_fallback_threshold is 0.5 by default.
    # Since we have no successful executions, current_avg_confidence will be 0.0.
    # So LLM fallback should NOT trigger.
    swarm_run, _, _ = await coordinator.aexecute_plan(
        domain, plan, Alert(alert_id="a1"), "run-1",
        use_llm_fallback=True, llm_fallback_threshold=0.5
    )

    # Only 1 execution (agent_1)
    assert len(swarm_run.executions) == 1
    assert all(ex.agent_id != "llm_agent" for ex in swarm_run.executions)

    # Case 2: One success (with high confidence) and one fail, fallback SHOULD trigger
    class SuccessAgent(Agent):
        async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
            ex = AgentExecution(agent_id=self.agent_id, agent_version="1", logic_hash="1", step_id=step_id, input_parameters=params)
            ex.output_evidence.append(Evidence(source_agent_execution_id="1", agent_id=self.agent_id, content="ok", confidence=0.9, evidence_type=EvidenceType.METRICS))
            return ex

    agents = [MockFailingAgent("agent_1"), SuccessAgent("agent_2"), MockFailingAgent("llm_agent")]
    orchestrator = SwarmOrchestrator(agents)
    execution_controller = SwarmExecutionController(orchestrator)

    coordinator = SwarmRunCoordinator(
        execution_controller, retry_controller, mock_decision_controller, mock_confidence_service,
        llm_agent_id="llm_agent"
    )

    plan = SwarmPlan(objective="Test", steps=[
        SwarmStep(agent_id="agent_1", mandatory=True, retry_policy=AlwaysFailRetryPolicy(max_attempts=1)),
        SwarmStep(agent_id="agent_2", mandatory=False)
    ])

    swarm_run, _, _ = await coordinator.aexecute_plan(
        domain, plan, Alert(alert_id="a1"), "run-2",
        use_llm_fallback=True, llm_fallback_threshold=0.5
    )

    # Agent 1 (fail), Agent 2 (success), LLM Agent (triggered because agent_1 failed and agent_2 provided >0.5 confidence)
    assert any(ex.agent_id == "llm_agent" for ex in swarm_run.executions)

@pytest.mark.asyncio
async def test_step_timeout():
    agents = [MockHangingAgent("agent_1")]
    # Set step_timeout to 0.1s
    orchestrator = SwarmOrchestrator(agents, step_timeout=0.1)

    plan = SwarmPlan(objective="Test", steps=[
        SwarmStep(agent_id="agent_1", mandatory=True)
    ])

    executions = await orchestrator.execute_swarm(plan.steps)

    assert len(executions) == 1
    assert executions[0].error is not None
    assert "timed out after 0.1s" in str(executions[0].error)
