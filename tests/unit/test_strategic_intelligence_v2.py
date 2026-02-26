"""
Unit tests for the critical flows introduced in feature/strategic-intelligence-v2.

Covers:
  - SwarmRunCoordinator.aexecute_plan() — central orchestration flow
  - ConfidenceService ↔ Neo4jAdapter integration (snapshot, decay, reinforce, penalize)
  - ExponentialBackoffPolicy deterministic retry (logic_hash immutability, delay, should_retry)
  - MetricsService recording (execution, decision, override, dedup)
  - HumanAction.ACCEPT / REJECT / OVERRIDE decision cycle
  - Decision.decision_state field present and correctly propagated
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Optional

from swarm_intelligence.core.models import (
    Alert, SwarmPlan, SwarmStep, Decision, Evidence, AgentExecution,
    HumanDecision, Domain, SwarmRun, RetryAttempt, RetryDecision,
    RetryEvaluationResult,
)
from swarm_intelligence.core.enums import EvidenceType, HumanAction, RiskLevel
from swarm_intelligence.policy.retry_policy import ExponentialBackoffPolicy, RetryContext
from swarm_intelligence.policy.confidence_policy import DefaultConfidencePolicy
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.controllers.swarm_decision_controller import SwarmDecisionController
from swarm_intelligence.coordinators.swarm_run_coordinator import SwarmRunCoordinator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(agent_id="agent-1", confidence=0.9) -> Evidence:
    return Evidence(
        source_agent_execution_id="exec-1",
        agent_id=agent_id,
        content={"finding": "ok"},
        confidence=confidence,
        evidence_type=EvidenceType.METRICS,
    )


def _make_execution(agent_id="agent-1", step_id="step-1", success=True) -> AgentExecution:
    ex = AgentExecution(
        agent_id=agent_id,
        agent_version="1.0",
        logic_hash="abc",
        step_id=step_id,
        input_parameters={},
    )
    ex.output_evidence = [_make_evidence(agent_id)]
    if not success:
        ex.error = RuntimeError("simulated failure")
    return ex


def _make_plan(agent_ids=("agent-1",)) -> SwarmPlan:
    steps = [SwarmStep(agent_id=aid) for aid in agent_ids]
    return SwarmPlan(objective="test-objective", steps=steps)


def _make_alert() -> Alert:
    return Alert(alert_id="alert-1", data={"severity": "critical", "service": "svc"})


def _make_domain() -> Domain:
    return Domain(id="dom-1", name="Infra", description="d", risk_level=RiskLevel.MEDIUM)


# ---------------------------------------------------------------------------
# 1. Decision.decision_state field
# ---------------------------------------------------------------------------

class TestDecisionStateField:
    def test_default_value_is_pending(self):
        d = Decision(
            summary="s",
            action_proposed="a",
            confidence=0.8,
            supporting_evidence=[],
        )
        assert d.decision_state == "pending"

    def test_custom_value_is_preserved(self):
        d = Decision(
            summary="s",
            action_proposed="a",
            confidence=0.8,
            supporting_evidence=[],
            decision_state="approved",
        )
        assert d.decision_state == "approved"


# ---------------------------------------------------------------------------
# 2. ExponentialBackoffPolicy — determinism, logic_hash as property
# ---------------------------------------------------------------------------

class TestExponentialBackoffPolicy:
    def test_logic_hash_is_deterministic(self):
        p1 = ExponentialBackoffPolicy(max_attempts=3, base_delay=0.5)
        p2 = ExponentialBackoffPolicy(max_attempts=3, base_delay=0.5)
        assert p1.logic_hash == p2.logic_hash

    def test_logic_hash_changes_when_params_change(self):
        p1 = ExponentialBackoffPolicy(max_attempts=3, base_delay=0.5)
        p2 = ExponentialBackoffPolicy(max_attempts=5, base_delay=0.5)
        assert p1.logic_hash != p2.logic_hash

    def test_logic_hash_is_a_property_not_cached(self):
        """Mutating max_attempts must be reflected immediately in logic_hash."""
        p = ExponentialBackoffPolicy(max_attempts=3)
        original_hash = p.logic_hash
        p.max_attempts = 7
        assert p.logic_hash != original_hash

    def test_should_retry_within_limit(self):
        p = ExponentialBackoffPolicy(max_attempts=3)
        ctx = RetryContext(run_id="r", step_id="s", agent_id="a", attempt=1)
        assert p.should_retry(ctx) is True
        ctx.attempt = 3
        assert p.should_retry(ctx) is True

    def test_should_not_retry_beyond_limit(self):
        p = ExponentialBackoffPolicy(max_attempts=3)
        ctx = RetryContext(run_id="r", step_id="s", agent_id="a", attempt=4)
        assert p.should_retry(ctx) is False

    def test_should_not_retry_on_fatal_error(self):
        p = ExponentialBackoffPolicy(max_attempts=5)
        err = RuntimeError("fatal")
        err.fatal = True
        ctx = RetryContext(run_id="r", step_id="s", agent_id="a", attempt=1, error=err)
        assert p.should_retry(ctx) is False

    def test_next_delay_is_deterministic_for_same_seed(self):
        p = ExponentialBackoffPolicy(base_delay=1.0, use_jitter=True)
        ctx = RetryContext(run_id="r", step_id="s", agent_id="a", attempt=2, random_seed=42)
        assert p.next_delay(ctx) == p.next_delay(ctx)

    def test_next_delay_capped_at_max_delay(self):
        p = ExponentialBackoffPolicy(base_delay=10.0, max_delay=5.0, use_jitter=False)
        ctx = RetryContext(run_id="r", step_id="s", agent_id="a", attempt=10, random_seed=0)
        assert p.next_delay(ctx) <= 5.0

    def test_to_dict_contains_logic_hash(self):
        p = ExponentialBackoffPolicy(max_attempts=2)
        d = p.to_dict()
        assert d["logic_hash"] == p.logic_hash
        assert d["policy_version"] == p.version


# ---------------------------------------------------------------------------
# 3. ConfidenceService ↔ Neo4jAdapter (stubbed)
# ---------------------------------------------------------------------------

class TestConfidenceService:
    def _make_adapter(self):
        adapter = MagicMock()
        # Default: no existing snapshots → sequence starts at 1
        adapter.run_write_transaction.return_value = {"sequence_id": 1}
        adapter.run_read_transaction.return_value = []
        adapter.create_confidence_snapshot.return_value = "snap-uuid-1"
        return adapter

    def test_get_last_confidence_returns_default_when_no_snapshots(self):
        adapter = self._make_adapter()
        adapter.run_read_transaction.return_value = []
        svc = ConfidenceService(adapter)
        assert svc.get_last_confidence("agent-x") == 1.0

    def test_get_last_confidence_returns_value_from_db(self):
        adapter = self._make_adapter()
        adapter.run_read_transaction.return_value = [{"value": 0.72}]
        svc = ConfidenceService(adapter)
        assert svc.get_last_confidence("agent-x") == 0.72

    def test_record_confidence_snapshot_calls_adapter(self):
        adapter = self._make_adapter()
        svc = ConfidenceService(adapter)
        svc.record_confidence_snapshot("agent-1", 0.85, "test_event")
        adapter.create_confidence_snapshot.assert_called_once_with("agent-1", 0.85, "test_event", 1)

    def test_record_confidence_snapshot_clamps_above_1(self):
        adapter = self._make_adapter()
        svc = ConfidenceService(adapter)
        svc.record_confidence_snapshot("agent-1", 1.5, "test_event")
        adapter.create_confidence_snapshot.assert_called_once_with("agent-1", 1.0, "test_event", 1)

    def test_record_confidence_snapshot_clamps_below_0(self):
        adapter = self._make_adapter()
        svc = ConfidenceService(adapter)
        svc.record_confidence_snapshot("agent-1", -0.3, "test_event")
        adapter.create_confidence_snapshot.assert_called_once_with("agent-1", 0.0, "test_event", 1)

    def test_record_confidence_snapshot_links_cause_when_provided(self):
        adapter = self._make_adapter()
        svc = ConfidenceService(adapter)
        svc.record_confidence_snapshot("agent-1", 0.7, "human_override", cause_id="dec-1", cause_type="Decision")
        adapter.link_snapshot_to_cause.assert_called_once_with("snap-uuid-1", "dec-1", "Decision")

    def test_record_confidence_snapshot_skips_link_on_failed_create(self):
        adapter = self._make_adapter()
        adapter.create_confidence_snapshot.return_value = None  # Simulates failure
        svc = ConfidenceService(adapter)
        svc.record_confidence_snapshot("agent-1", 0.7, "event", cause_id="c", cause_type="Decision")
        adapter.link_snapshot_to_cause.assert_not_called()

    def test_apply_time_decay_reduces_confidence(self):
        adapter = self._make_adapter()
        adapter.run_read_transaction.return_value = [{"value": 0.8}]
        svc = ConfidenceService(adapter)
        svc.apply_time_decay("agent-1", 0.1)
        # Expected decayed value: 0.8 * (1 - 0.1) = 0.72
        adapter.create_confidence_snapshot.assert_called_once_with("agent-1", pytest.approx(0.72), "time_decay", 1)

    def test_penalize_for_override(self):
        adapter = self._make_adapter()
        adapter.run_read_transaction.return_value = [{"value": 0.9}]
        policy = DefaultConfidencePolicy()
        svc = ConfidenceService(adapter)
        svc.penalize_for_override("agent-1", "decision-1", policy)
        # Expected: 0.9 - 0.1 = 0.8
        adapter.create_confidence_snapshot.assert_called_once_with(
            "agent-1", pytest.approx(0.8), "human_override", 1
        )

    def test_reinforce_for_success(self):
        adapter = self._make_adapter()
        adapter.run_read_transaction.return_value = [{"value": 0.8}]
        policy = DefaultConfidencePolicy()
        svc = ConfidenceService(adapter)
        svc.reinforce_for_success("agent-1", "decision-1", policy)
        # Expected: 0.8 + 0.05 = 0.85
        adapter.create_confidence_snapshot.assert_called_once_with(
            "agent-1", pytest.approx(0.85), "successful_outcome", 1
        )

    def test_sequence_id_uses_atomic_write_transaction(self):
        """_get_next_sequence_id must use run_write_transaction, not run_read_transaction."""
        adapter = self._make_adapter()
        adapter.run_write_transaction.return_value = {"sequence_id": 7}
        svc = ConfidenceService(adapter)
        seq = svc._get_next_sequence_id()
        assert seq == 7
        adapter.run_write_transaction.assert_called_once()
        # Verify it did NOT use run_read_transaction for sequence
        # (run_read_transaction is only used by get_last_confidence)
        adapter.run_read_transaction.assert_not_called()


# ---------------------------------------------------------------------------
# 4. MetricsService recording
# ---------------------------------------------------------------------------

class TestMetricsService:
    def test_record_execution_calls_histogram(self):
        from src.services.metrics_service import MetricsService
        svc = MetricsService()
        with patch.object(svc.swarm_execution_time, 'labels') as mock_labels:
            mock_obs = MagicMock()
            mock_labels.return_value = mock_obs
            svc.record_execution(1.5, "Infra", "critical")
            mock_labels.assert_called_once_with(domain="Infra", risk_level="critical")
            mock_obs.observe.assert_called_once_with(1.5)

    def test_record_decision_calls_histogram(self):
        from src.services.metrics_service import MetricsService
        svc = MetricsService()
        with patch.object(svc.decision_confidence, 'labels') as mock_labels:
            mock_obs = MagicMock()
            mock_labels.return_value = mock_obs
            svc.record_decision(0.85, "pending")
            mock_labels.assert_called_once_with(decision_state="pending")
            mock_obs.observe.assert_called_once_with(0.85)

    def test_record_override_increments_counter(self):
        from src.services.metrics_service import MetricsService
        svc = MetricsService()
        with patch.object(svc.human_override_rate, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            svc.record_override("confirmed")
            mock_labels.assert_called_once_with(status="confirmed")
            mock_counter.inc.assert_called_once()

    def test_record_dedup_increments_counter(self):
        from src.services.metrics_service import MetricsService
        svc = MetricsService()
        with patch.object(svc.deduplication_events, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            svc.record_dedup("new_execution")
            mock_labels.assert_called_once_with(action="new_execution")
            mock_counter.inc.assert_called_once()


# ---------------------------------------------------------------------------
# 5. SwarmDecisionController — HumanAction.ACCEPT / REJECT / OVERRIDE cycle
# ---------------------------------------------------------------------------

class TestSwarmDecisionController:
    def _make_controller(self):
        return SwarmDecisionController()

    def _make_confidence_service(self):
        adapter = MagicMock()
        adapter.run_write_transaction.return_value = {"sequence_id": 1}
        adapter.run_read_transaction.return_value = [{"value": 0.9}]
        adapter.create_confidence_snapshot.return_value = "snap-1"
        return ConfidenceService(adapter)

    async def test_decide_with_no_human_hook(self):
        ctrl = self._make_controller()
        svc = self._make_confidence_service()
        plan = _make_plan()
        alert = _make_alert()
        executions = [_make_execution()]
        decision = await ctrl.decide(plan, executions, alert, svc, DefaultConfidencePolicy(), None, "run-1", 42)
        assert isinstance(decision, Decision)
        assert decision.human_decision is None

    async def test_decide_with_accept_hook(self):
        ctrl = self._make_controller()
        svc = self._make_confidence_service()
        plan = _make_plan()
        alert = _make_alert()
        executions = [_make_execution()]

        def accept_hook(d: Decision) -> Optional[HumanDecision]:
            return HumanDecision(action=HumanAction.ACCEPT, author="reviewer-1")

        decision = await ctrl.decide(plan, executions, alert, svc, DefaultConfidencePolicy(), accept_hook, "run-1", 42)
        assert decision.human_decision is not None
        assert decision.human_decision.action == HumanAction.ACCEPT

    async def test_decide_with_reject_hook(self):
        ctrl = self._make_controller()
        svc = self._make_confidence_service()
        plan = _make_plan()
        alert = _make_alert()
        executions = [_make_execution()]

        def reject_hook(d: Decision) -> Optional[HumanDecision]:
            return HumanDecision(action=HumanAction.REJECT, author="reviewer-1")

        decision = await ctrl.decide(plan, executions, alert, svc, DefaultConfidencePolicy(), reject_hook, "run-1", 42)
        assert decision.human_decision.action == HumanAction.REJECT

    async def test_decide_with_override_penalizes_agents(self):
        ctrl = self._make_controller()
        adapter = MagicMock()
        adapter.run_write_transaction.return_value = {"sequence_id": 1}
        adapter.run_read_transaction.return_value = [{"value": 0.9}]
        adapter.create_confidence_snapshot.return_value = "snap-1"
        svc = ConfidenceService(adapter)

        plan = _make_plan()
        alert = _make_alert()
        executions = [_make_execution()]

        def override_hook(d: Decision) -> Optional[HumanDecision]:
            return HumanDecision(action=HumanAction.OVERRIDE, author="expert",
                                 override_reason="Disagree", overridden_action_proposed="manual_fix")

        decision = await ctrl.decide(plan, executions, alert, svc, DefaultConfidencePolicy(), override_hook, "run-1", 42)
        assert decision.human_decision.action == HumanAction.OVERRIDE
        # Penalty should have been recorded via create_confidence_snapshot
        adapter.create_confidence_snapshot.assert_called()

    async def test_decide_produces_manual_review_with_no_evidence(self):
        ctrl = self._make_controller()
        svc = self._make_confidence_service()
        plan = _make_plan()
        alert = _make_alert()

        decision = await ctrl.decide(plan, [], alert, svc, DefaultConfidencePolicy(), None, "run-1", 42)
        assert decision.action_proposed == "manual_review"
        assert decision.confidence == 0.0


# ---------------------------------------------------------------------------
# 6. SwarmRunCoordinator.aexecute_plan() — central orchestration
# ---------------------------------------------------------------------------

class TestSwarmRunCoordinator:
    def _build_coordinator(self, executions=None, retry_eval=None):
        """Builds a coordinator with mocked sub-controllers."""
        if executions is None:
            executions = [_make_execution()]
        if retry_eval is None:
            retry_eval = RetryEvaluationResult(
                steps_to_retry=[],
                retry_attempts=[],
                retry_decisions=[],
                max_delay_seconds=0.0,
                newly_successful_step_ids={"step-1"},
            )

        exec_ctrl = MagicMock()
        exec_ctrl.execute = AsyncMock(return_value=executions)

        retry_ctrl = MagicMock()
        retry_ctrl.evaluate = AsyncMock(return_value=retry_eval)

        adapter = MagicMock()
        adapter.run_write_transaction.return_value = {"sequence_id": 1}
        adapter.run_read_transaction.return_value = [{"value": 0.9}]
        adapter.create_confidence_snapshot.return_value = "snap-1"
        confidence_svc = ConfidenceService(adapter)

        decision_ctrl = SwarmDecisionController()

        deduplicator = MagicMock()
        deduplicator.acquire_lock.return_value = True
        deduplicator.check_duplicate.return_value = (MagicMock(name="DeduplicationAction"), None)

        metrics = MagicMock()

        coordinator = SwarmRunCoordinator(
            execution_controller=exec_ctrl,
            retry_controller=retry_ctrl,
            decision_controller=decision_ctrl,
            confidence_service=confidence_svc,
            deduplicator=deduplicator,
            metrics_service=metrics,
        )
        return coordinator, metrics

    async def test_aexecute_plan_returns_swarm_run_tuple(self):
        coordinator, _ = self._build_coordinator()
        plan = _make_plan()
        alert = _make_alert()
        domain = _make_domain()
        result = await coordinator.aexecute_plan(domain, plan, alert, "run-1", master_seed=42)
        swarm_run, retry_attempts, retry_decisions = result
        assert isinstance(swarm_run, SwarmRun)
        assert isinstance(retry_attempts, list)
        assert isinstance(retry_decisions, list)

    async def test_aexecute_plan_records_metrics(self):
        coordinator, metrics = self._build_coordinator()
        plan = _make_plan()
        alert = _make_alert()
        domain = _make_domain()
        await coordinator.aexecute_plan(domain, plan, alert, "run-1", master_seed=42)
        metrics.record_execution.assert_called_once()
        metrics.record_decision.assert_called_once()

    async def test_aexecute_plan_decision_state_passed_to_metrics(self):
        """record_decision must be called with the string decision_state, not .value"""
        coordinator, metrics = self._build_coordinator()
        plan = _make_plan()
        alert = _make_alert()
        domain = _make_domain()
        await coordinator.aexecute_plan(domain, plan, alert, "run-1", master_seed=42)
        _, kwargs = metrics.record_decision.call_args
        # Either positional or keyword — just check second arg is a string
        args, _ = metrics.record_decision.call_args
        assert isinstance(args[1], str), "decision_state must be a str, not an Enum"

    async def test_aexecute_plan_with_human_hook(self):
        coordinator, _ = self._build_coordinator()
        plan = _make_plan()
        alert = _make_alert()
        domain = _make_domain()

        def accept_hook(d: Decision) -> Optional[HumanDecision]:
            return HumanDecision(action=HumanAction.ACCEPT, author="reviewer")

        swarm_run, _, _ = await coordinator.aexecute_plan(
            domain, plan, alert, "run-1", human_hook=accept_hook, master_seed=42
        )
        assert swarm_run.final_decision is not None
        assert swarm_run.final_decision.human_decision is not None

    async def test_aexecute_plan_aborts_on_timeout(self):
        exec_ctrl = MagicMock()

        async def slow_execute(steps, *a, **kw):
            await asyncio.sleep(10)
            return []

        exec_ctrl.execute = slow_execute

        retry_ctrl = MagicMock()
        retry_eval = RetryEvaluationResult(
            steps_to_retry=[],
            newly_successful_step_ids=set(),
        )
        retry_ctrl.evaluate = AsyncMock(return_value=retry_eval)

        adapter = MagicMock()
        adapter.run_write_transaction.return_value = {"sequence_id": 1}
        adapter.run_read_transaction.return_value = []
        adapter.create_confidence_snapshot.return_value = "snap-1"
        confidence_svc = ConfidenceService(adapter)
        decision_ctrl = SwarmDecisionController()
        metrics = MagicMock()

        deduplicator = MagicMock()
        deduplicator.acquire_lock.return_value = True
        deduplicator.check_duplicate.return_value = (MagicMock(), None)

        coordinator = SwarmRunCoordinator(
            execution_controller=exec_ctrl,
            retry_controller=retry_ctrl,
            decision_controller=decision_ctrl,
            confidence_service=confidence_svc,
            metrics_service=metrics,
            deduplicator=deduplicator,
        )

        plan = _make_plan()
        alert = _make_alert()
        domain = _make_domain()

        swarm_run, _, _ = await coordinator.aexecute_plan(
            domain, plan, alert, "run-1",
            master_seed=42,
            max_runtime_seconds=0.01,
            use_llm_fallback=False,
        )
        assert swarm_run.metadata["aborted_by_limit"] is True


# ---------------------------------------------------------------------------
# 7. Neo4jAdapter — Cypher injection guard on link_snapshot_to_cause
# ---------------------------------------------------------------------------

class TestNeo4jAdapterCypherInjection:
    def _make_adapter_instance(self):
        from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
        # Patch GraphDatabase.driver so no real connection is made
        with patch("swarm_intelligence.memory.neo4j_adapter.GraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = MagicMock()
            adapter = Neo4jAdapter("bolt://localhost:7687", "neo4j", "test")
        return adapter

    def test_allowed_cause_type_does_not_raise(self):
        adapter = self._make_adapter_instance()
        adapter.run_transaction = MagicMock()
        # Should not raise
        adapter.link_snapshot_to_cause("snap-1", "cause-1", "Decision")
        adapter.run_transaction.assert_called_once()

    def test_invalid_cause_type_raises_value_error(self):
        adapter = self._make_adapter_instance()
        adapter.run_transaction = MagicMock()
        with pytest.raises(ValueError, match="Invalid cause_type"):
            adapter.link_snapshot_to_cause("snap-1", "cause-1", "'; DROP TABLE agents; --")

    def test_all_allowed_cause_types_are_accepted(self):
        adapter = self._make_adapter_instance()
        adapter.run_transaction = MagicMock()
        for cause_type in adapter._ALLOWED_CAUSE_TYPES:
            adapter.run_transaction.reset_mock()
            adapter.link_snapshot_to_cause("snap-1", "cause-1", cause_type)
            adapter.run_transaction.assert_called_once()
