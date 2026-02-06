import uuid
from typing import List, Dict, Optional, Set
from swarm_intelligence.core.models import (
    SwarmPlan,
    SwarmStep,
    AgentExecution,
    RetryAttempt,
    RetryDecision,
    RetryEvaluationResult,
)
from swarm_intelligence.policy.retry_policy import RetryContext
from swarm_intelligence.services.confidence_service import ConfidenceService


class SwarmRetryController:
    """
    Evaluates failed executions and decides if, when, and why a retry should happen.
    This controller is a stateless policy engine.
    """

    async def evaluate(
        self,
        plan: SwarmPlan,
        executions: List[AgentExecution],
        previous_attempts: List[RetryAttempt],
        confidence_service: ConfidenceService,
        run_id: str,
        master_seed: int,
        successful_step_ids: Set[str],
    ) -> RetryEvaluationResult:
        steps_to_retry = []
        new_retry_attempts = []
        new_retry_decisions = []
        newly_successful_step_ids = set()
        max_delay = 0.0

        executed_step_ids = {ex.step_id for ex in executions}

        for step in plan.steps:
            if step.step_id in successful_step_ids or step.step_id not in executed_step_ids:
                continue

            latest_execution = next(
                (ex for ex in reversed(executions) if ex.step_id == step.step_id), None
            )
            if not latest_execution:
                continue

            if latest_execution.is_successful():
                newly_successful_step_ids.add(step.step_id)
                continue

            if step.mandatory and step.retry_policy:
                retries_for_step = [
                    r for r in previous_attempts if r.step_id == step.step_id
                ]
                attempt_num = len(retries_for_step) + 1

                context = RetryContext(
                    run_id=run_id,
                    step_id=step.step_id,
                    agent_id=step.agent_id,
                    attempt=attempt_num,
                    error=latest_execution.error,
                    random_seed=master_seed + attempt_num,
                    last_confidence=confidence_service.get_last_confidence(
                        step.agent_id
                    ),
                    domain_hints=[],  # Placeholder
                )

                if step.retry_policy.should_retry(context):
                    delay = step.retry_policy.next_delay(context)
                    max_delay = max(max_delay, delay)

                    attempt_id = str(uuid.uuid4())

                    decision = RetryDecision(
                        step_id=step.step_id,
                        reason=str(context.error),
                        policy_name=step.retry_policy.__class__.__name__,
                        policy_version=step.retry_policy.version,
                        policy_logic_hash=step.retry_policy.logic_hash,
                        attempt_id=attempt_id,
                    )
                    new_retry_decisions.append(decision)

                    new_retry_attempts.append(
                        RetryAttempt(
                            step_id=step.step_id,
                            attempt_number=context.attempt,
                            delay_seconds=delay,
                            reason=str(context.error),
                            failed_execution_id=latest_execution.execution_id,
                            attempt_id=attempt_id,
                        )
                    )
                    steps_to_retry.append(step)

        return RetryEvaluationResult(
            steps_to_retry=steps_to_retry,
            retry_attempts=new_retry_attempts,
            retry_decisions=new_retry_decisions,
            max_delay_seconds=max_delay,
            newly_successful_step_ids=newly_successful_step_ids,
        )
