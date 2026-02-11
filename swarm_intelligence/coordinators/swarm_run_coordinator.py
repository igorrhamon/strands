import asyncio
import random
from typing import List, Dict, Optional, Callable, Any
from swarm_intelligence.core.models import (
    SwarmPlan,
    Alert,
    Decision,
    AgentExecution,
    RetryAttempt,
    RetryDecision,
    HumanDecision,
    SwarmStep,
    Domain,
    SwarmRun
)
from swarm_intelligence.controllers.swarm_execution_controller import (
    SwarmExecutionController,
)
from swarm_intelligence.controllers.swarm_retry_controller import SwarmRetryController
from swarm_intelligence.controllers.swarm_decision_controller import (
    SwarmDecisionController,
)
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.policy.confidence_policy import (
    ConfidencePolicy,
    DefaultConfidencePolicy,
)
from src.deduplication.distributed_deduplicator import DistributedEventDeduplicator, DeduplicationAction
from src.services.metrics_service import MetricsService
import time


class SwarmRunCoordinator:
    """
    Orchestrates the specialized controllers to run a swarm plan.
    This component is stateful for a single run.
    """

    def __init__(
        self,
        execution_controller: SwarmExecutionController,
        retry_controller: SwarmRetryController,
        decision_controller: SwarmDecisionController,
        confidence_service: ConfidenceService,
        llm_agent_id: Optional[str] = "llm_agent",
        deduplicator: Optional[DistributedEventDeduplicator] = None,
        metrics_service: Optional[MetricsService] = None,
    ):
        self.execution_controller = execution_controller
        self.retry_controller = retry_controller
        self.decision_controller = decision_controller
        self.confidence_service = confidence_service
        self.llm_agent_id = llm_agent_id
        self.deduplicator = deduplicator or DistributedEventDeduplicator()
        self.metrics = metrics_service or MetricsService()

    async def aexecute_plan(
        self,
        domain: Domain,
        plan: SwarmPlan,
        alert: Alert,
        run_id: str,
        confidence_policy: ConfidencePolicy = None,
        human_hook: Optional[Callable[[Decision], HumanDecision]] = None,
        replay_mode: bool = False,
        replay_results: Optional[Dict[str, AgentExecution]] = None,
        master_seed: Optional[int] = None,
        max_retry_rounds: int = 10,
        max_runtime_seconds: float = 300.0,
        max_total_attempts: int = 50,
        use_llm_fallback: bool = True,
        llm_fallback_threshold: float = 0.5,
    ) -> (SwarmRun, List[RetryAttempt], List[RetryDecision]):
        start_time = time.time()
        # 0. Distributed Deduplication Check
        if not replay_mode and self.deduplicator:
            # Generate alert signature for dedup
            source_id = alert.alert_id
            severity = alert.data.get("severity", "warning")
            service = alert.data.get("service", "unknown")
            
            # Try to acquire a distributed lock to prevent race conditions
            lock_name = f"swarm_run:{source_id}"
            if self.deduplicator.acquire_lock(lock_name):
                try:
                    action, existing_run_id = self.deduplicator.check_duplicate(
                        source_id=source_id,
                        event_data=alert.data,
                        severity=severity,
                        source_system=alert.data.get("source", "grafana")
                    )
                    
                    if action == DeduplicationAction.UPDATE_EXISTING:
                        self.metrics.record_dedup("update_existing")
                        pass 
                    else:
                        self.metrics.record_dedup("new_execution")
                finally:
                    self.deduplicator.release_lock(lock_name)

        # Use a local RNG to avoid modifying global random state
        if master_seed is None:
            master_seed = random.randint(0, 1_000_000)

        local_rng = random.Random(master_seed)

        all_retry_attempts = []
        all_retry_decisions = []
        all_executions: List[AgentExecution] = []
        successful_step_ids = set()

        round_counter = 0
        total_attempts_counter = 0
        aborted_by_limit = False

        steps_to_process = list(plan.steps)

        for step in steps_to_process:
            self.confidence_service.apply_time_decay(step.agent_id, 0.001)

        async def _internal_run():
            nonlocal steps_to_process, round_counter, total_attempts_counter, aborted_by_limit

            while steps_to_process:
                if round_counter >= max_retry_rounds or total_attempts_counter >= max_total_attempts:
                    aborted_by_limit = True
                    break

                round_counter += 1
                total_attempts_counter += len(steps_to_process)

                new_executions = await self.execution_controller.execute(
                    steps_to_process, replay_mode, replay_results
                )
                all_executions.extend(new_executions)

                retry_eval = await self.retry_controller.evaluate(
                    plan,
                    all_executions,
                    all_retry_attempts,
                    self.confidence_service,
                    run_id,
                    master_seed,
                    successful_step_ids,
                )

                all_retry_attempts.extend(retry_eval.retry_attempts)
                all_retry_decisions.extend(retry_eval.retry_decisions)
                successful_step_ids.update(retry_eval.newly_successful_step_ids)
                steps_to_process = retry_eval.steps_to_retry

                if steps_to_process and retry_eval.max_delay_seconds > 0:
                    # Use local RNG for jitter
                    jitter = local_rng.uniform(-0.1, 0.1)
                    await asyncio.sleep(retry_eval.max_delay_seconds * (1 + jitter))

        try:
            await asyncio.wait_for(_internal_run(), timeout=max_runtime_seconds)
        except asyncio.TimeoutError:
            aborted_by_limit = True

        final_successful_executions = [
            ex for ex in all_executions if ex.step_id in successful_step_ids
        ]

        swarm_run = SwarmRun(
            run_id=run_id,
            domain=domain,
            plan=plan,
            master_seed=master_seed,
            executions=all_executions,
        )
        swarm_run.metadata = {
            "total_rounds": round_counter,
            "total_attempts": total_attempts_counter,
            "aborted_by_limit": aborted_by_limit,
        }

        all_mandatory_successful = all(
            s.step_id in successful_step_ids for s in plan.steps if s.mandatory
        )

        current_avg_confidence = 0.0
        if final_successful_executions:
            all_evidence = [ev for ex in final_successful_executions for ev in ex.output_evidence]
            if all_evidence:
                current_avg_confidence = sum(ev.confidence for ev in all_evidence) / len(all_evidence)

        should_trigger_llm = (
            use_llm_fallback
            and self.llm_agent_id is not None
            and (
                (not all_mandatory_successful)
                or (current_avg_confidence <= llm_fallback_threshold)
            )
        )
        if should_trigger_llm:
            llm_input = {
                "alert": alert.data,
                "run_id": run_id,
                "evidence": [
                    {
                        "agent_id": ev.agent_id,
                        "confidence": ev.confidence,
                        "content": ev.content,
                    }
                    for ex in final_successful_executions
                    for ev in ex.output_evidence
                ],
                "avg_confidence": current_avg_confidence,
                "mandatory_success": all_mandatory_successful,
            }
            llm_step = SwarmStep(agent_id=self.llm_agent_id, mandatory=True, parameters=llm_input)
            llm_executions = await self.execution_controller.execute([llm_step])
            all_executions.extend(llm_executions)
            final_successful_executions.extend([ex for ex in llm_executions if ex and ex.is_successful()])

        decision = await self.decision_controller.decide(
            plan,
            final_successful_executions,
            alert,
            self.confidence_service,
            confidence_policy or DefaultConfidencePolicy(),
            human_hook,
            run_id,
            master_seed,
        )

        swarm_run.executions = all_executions
        swarm_run.final_decision = decision

        # Record Metrics
        duration = time.time() - start_time
        self.metrics.record_execution(duration, domain.name, alert.data.get("severity", "medium"))
        if decision:
            self.metrics.record_decision(decision.confidence, decision.decision_state.value)

        # Register successful execution in deduplicator
        if not replay_mode and self.deduplicator:
            self.deduplicator.register_execution(
                source_id=alert.alert_id,
                execution_id=run_id,
                event_data=alert.data,
                severity=alert.data.get("severity"),
                source_system=alert.data.get("source")
            )

        return swarm_run, all_retry_attempts, all_retry_decisions
