
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Coroutine, Sequence
from .models import AgentExecution, SwarmStep, Evidence

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
    for given steps and returns the resulting AgentExecution events.
    """
    def __init__(self, agents: Sequence[Agent]):
        self._agents = {agent.agent_id: agent for agent in agents}

    async def _execute_agent(self, step: SwarmStep) -> AgentExecution:
        """A wrapper to execute a single agent and handle exceptions."""
        agent = self._agents.get(step.agent_id)
        if not agent:
            return AgentExecution(
                agent_id=step.agent_id, agent_version="N/A", logic_hash="N/A",
                step_id=step.step_id, input_parameters=step.parameters,
                error=Exception(f"Agent '{step.agent_id}' not found.")
            )
        try:
            return await agent.execute(step.parameters, step.step_id)
        except Exception as e:
            return AgentExecution(
                agent_id=agent.agent_id, agent_version=agent.version, logic_hash=agent.logic_hash,
                step_id=step.step_id, input_parameters=step.parameters,
                error=e
            )

    async def execute_swarm(self, steps: List[SwarmStep]) -> List[AgentExecution]:
        """
        Executes the given steps in parallel and returns a list of AgentExecution events.
        """
        if not steps:
            return []

        tasks: List[Coroutine[Any, Any, AgentExecution]] = [self._execute_agent(step) for step in steps]
        results: List[AgentExecution] = await asyncio.gather(*tasks, return_exceptions=False)
        return results
