
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Coroutine
from .models import SwarmResult, SwarmStep, EvidenceType

class Agent(ABC):
    """Abstract base class for all agents in the swarm."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> SwarmResult:
        """Executes the agent's logic and returns a SwarmResult."""
        pass

class SwarmOrchestrator:
    """
    The pure execution engine for the swarm.
    It takes a list of agents and executes them in parallel.
    """
    def __init__(self, agents: List[Agent]):
        self._agents = {agent.agent_id: agent for agent in agents}

    async def _execute_agent(self, step: SwarmStep) -> SwarmResult:
        """A wrapper to execute a single agent and handle exceptions."""
        agent = self._agents.get(step.agent_id)
        if not agent:
            return SwarmResult(
                agent_id=step.agent_id,
                output=None,
                confidence=0.0,
                actionable=False,
                evidence_type=EvidenceType.RAW_DATA,
                error=f"Agent '{step.agent_id}' not found."
            )
        try:
            return await agent.execute(step.parameters)
        except Exception as e:
            return SwarmResult(
                agent_id=step.agent_id,
                output=None,
                confidence=0.0,
                actionable=False,
                evidence_type=EvidenceType.RAW_DATA,
                error=str(e)
            )

    async def execute_swarm(self, steps: List[SwarmStep]) -> List[SwarmResult]:
        """
        Executes the given steps in parallel.
        The controller is responsible for interpreting these results.
        """
        if not steps:
            return []

        tasks: List[Coroutine[Any, Any, SwarmResult]] = [self._execute_agent(step) for step in steps]
        results: List[SwarmResult] = await asyncio.gather(*tasks, return_exceptions=False)
        return results
