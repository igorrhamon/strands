from typing import List, Dict, Optional
from swarm_intelligence.core.models import SwarmStep, AgentExecution
from swarm_intelligence.core.swarm import SwarmOrchestrator


class SwarmExecutionController:
    """
    Executes a single attempt of a set of SwarmSteps and returns the AgentExecution.
    This controller is a pure, stateless executor.
    """

    def __init__(self, orchestrator: SwarmOrchestrator):
        self.orchestrator = orchestrator

    async def execute(
        self,
        steps: List[SwarmStep],
        replay_mode: bool = False,
        replay_results: Optional[Dict[str, AgentExecution]] = None,
    ) -> List[AgentExecution]:
        if replay_mode:
            if replay_results is None:
                replay_results = {}
            return [replay_results.get(s.step_id) for s in steps]
        else:
            return await self.orchestrator.execute_swarm(steps)
