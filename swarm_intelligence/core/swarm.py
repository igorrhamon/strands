
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Coroutine, Tuple
from .models import AgentExecution, SwarmStep, RetryAttempt
from ..policy.retry_policy import RetryContext

class Agent(ABC):
    """Abstract base class for all agents in the swarm."""

    def __init__(self, agent_id: str, version: str = "1.0", logic_hash: str = "undefined"):
        self.agent_id = agent_id
        self.version = version
        self.logic_hash = logic_hash

    @abstractmethod
    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        """Executes the agent's logic and returns an AgentExecution event."""
        pass

class SwarmOrchestrator:
    """
    The pure execution engine for the swarm. It executes a list of agents
    for given steps, handling retries according to each step's policy,
    and returns the resulting AgentExecution and RetryAttempt events.
    """
    def __init__(self, agents: List[Agent]):
        self._agents = {agent.agent_id: agent for agent in agents}

    async def _execute_agent(self, step: SwarmStep) -> AgentExecution:
        """A wrapper to execute a single agent and handle exceptions."""
        agent = self._agents.get(step.agent_id)
        if not agent:
            return AgentExecution(
                agent_id=step.agent_id, agent_version="N/A", logic_hash="N/A",
                step_id=step.step_id, input_parameters=step.parameters,
                error=f"Agent '{step.agent_id}' not found."
            )
        try:
            return await agent.execute(step.parameters, step.step_id)
        except Exception as e:
            return AgentExecution(
                agent_id=agent.agent_id, agent_version=agent.version, logic_hash=agent.logic_hash,
                step_id=step.step_id, input_parameters=step.parameters,
                error=str(e)
            )

    async def _execute_step_with_retries(
        self, step: SwarmStep, run_id: str, master_seed: int, context_data: Dict[str, Any]
    ) -> Tuple[List[AgentExecution], List[RetryAttempt]]:
        """
        Executes a single SwarmStep, applying its retry policy if execution fails.
        """
        executions: List[AgentExecution] = []
        retries: List[RetryAttempt] = []
        attempt_num = 0

        while True:
            attempt_num += 1
            execution = await self._execute_agent(step)
            executions.append(execution)

            if execution.is_successful():
                break

            # If failed, check for a retry policy
            if not step.retry_policy:
                break # No policy, no retry

            context = RetryContext(
                run_id=run_id,
                step_id=step.step_id,
                agent_id=step.agent_id,
                attempt=attempt_num,
                error=Exception(execution.error),
                random_seed=master_seed + attempt_num, # Deterministic seed
                last_confidence=context_data.get("last_confidence", 1.0),
                domain_hints=context_data.get("domain_hints", [])
            )

            if not step.retry_policy.should_retry(context):
                break # Policy decided not to retry

            delay = step.retry_policy.next_delay(context)
            logging.info(f"Retrying step '{step.step_id}' in {delay:.2f}s (Attempt {attempt_num})...")

            retries.append(RetryAttempt(
                step_id=step.step_id,
                attempt_number=context.attempt,
                delay_seconds=delay,
                reason=str(context.error),
                failed_execution_id=execution.execution_id,
            ))

            await asyncio.sleep(delay)

        return executions, retries

    async def execute_swarm(
        self, steps: List[SwarmStep], run_id: str, master_seed: int, steps_context: Dict[str, Any]
    ) -> Tuple[List[AgentExecution], List[RetryAttempt]]:
        """
        Executes the given steps in parallel, each with its own retry logic,
        and returns a flattened list of all executions and retry attempts.
        """
        if not steps:
            return [], []

        tasks = [self._execute_step_with_retries(step, run_id, master_seed, steps_context.get(step.step_id, {})) for step in steps]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        all_executions = [ex for res in results for ex in res[0]]
        all_retries = [retry for res in results for retry in res[1]]

        return all_executions, all_retries
