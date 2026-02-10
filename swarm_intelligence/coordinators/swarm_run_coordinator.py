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
    ):
        self.execution_controller = execution_controller
        self.retry_controller = retry_controller
        self.decision_controller = decision_controller
        self.confidence_service = confidence_service
        self.llm_agent_id = llm_agent_id

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
    ) -> (SwarmRun, List[RetryAttempt], List[RetryDecision]):
        master_seed = (
            master_seed
            if master_seed is not None
            else random.randint(0, 1_000_000)
        )

        all_retry_attempts = []
        all_retry_decisions = []

        sequence_id = 0

        all_executions: List[AgentExecution] = []
        all_retry_attempts: List[RetryAttempt] = []
        all_retry_decisions: List[RetryDecision] = []
        successful_step_ids = set()

        steps_to_process = list(plan.steps)

        for step in steps_to_process:
            self.confidence_service.apply_time_decay(step.agent_id, 0.001)

        while steps_to_process:
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

            if retry_eval.max_delay_seconds > 0:
                await asyncio.sleep(retry_eval.max_delay_seconds)

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

        if not all(s.step_id in successful_step_ids for s in plan.steps if s.mandatory):
            if self.llm_agent_id:
                llm_step = SwarmStep(agent_id=self.llm_agent_id, mandatory=True)
                llm_executions = await self.execution_controller.execute([llm_step])
                all_executions.extend(llm_executions)
                final_successful_executions.extend(llm_executions)

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

        return swarm_run, all_retry_attempts, all_retry_decisions
