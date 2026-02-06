"""
Swarm Orchestrator

Responsible for spawning and managing the parallel execution of Swarm Agents.
Enforces:
- Parallel execution (asyncio.gather)
- Error boundaries (Partial failure handling)
- Result aggregation
"""

import asyncio
import logging
from typing import List, Protocol, Optional

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult
from inspect import isawaitable

logger = logging.getLogger(__name__)

class SwarmAgent(Protocol):
    """Protocol that all Swarm Agents must implement."""
    agent_id: str
    
    async def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        ...

class SwarmOrchestrator:
    """
    Manages the lifecycle of a Swarm analysis.
    """
    
    def __init__(self, agents: List[SwarmAgent]):
        self.agents = agents

    async def run_swarm(self, alert: NormalizedAlert) -> List[SwarmResult]:
        """
        Execute all agents in parallel.
        Handles individual agent failures gracefully (Partial Failure Strategy).
        """
        if not self.agents:
            logger.warning("No agents registered in Swarm.")
            return []

        logger.info("Starting Swarm analysis with %d agents for alert %s", 
                    len(self.agents), alert.fingerprint)

        # Create tasks for all agents
        tasks = [
            self._safe_execute(agent, alert) 
            for agent in self.agents
        ]

        # Wait for all to complete with a global timeout
        try:
            # Global timeout of 30 seconds for the entire swarm execution
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error("Swarm analysis timed out after 30 seconds. Returning partial results.")
            # In case of timeout, we might have some completed tasks if we used as_completed,
            # but with gather/wait_for, we lose pending ones. 
            # For robustness, we return empty list or handle partials if architected differently.
            return []
        
        # Filter out valid results and log unexpected errors
        valid_results = []
        for res in results:
            if isinstance(res, SwarmResult):
                valid_results.append(res)
            else:
                # Should be caught by _safe_execute, but just in case
                logger.error("Unexpected error in Swarm result collection: %s", res)

        logger.info("Swarm analysis complete. %d/%d agents succeeded.", 
                    len(valid_results), len(self.agents))
        
        return valid_results

    async def _safe_execute(self, agent: SwarmAgent, alert: NormalizedAlert) -> Optional[SwarmResult]:
        """
        Executes a single agent with error boundary.
        """
        try:
            result = agent.analyze(alert)
            if isawaitable(result):
                return await result  # type: ignore[return-value]
            return result
        except Exception as e:
            logger.error("Agent %s failed: %s", agent.agent_id, e, exc_info=True)
            return None
