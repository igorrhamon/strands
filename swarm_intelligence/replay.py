
from dataclasses import dataclass, field
from typing import List, Dict, Any
from swarm_intelligence.core.models import Decision, SwarmPlan, Alert
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.controller import SwarmController

@dataclass
class ReplayReport:
    """A detailed report comparing an original decision with a replayed one."""
    run_id: str
    original_action: str
    replayed_action: str
    confidence_delta: float
    divergences: List[str] = field(default_factory=list)

class ReplayEngine:
    """
    Executes a deterministic replay of a past swarm run to audit decisions
    and evaluate the impact of new policies or agent versions.
    """
    def __init__(self, neo4j_adapter: Neo4jAdapter):
        self.neo4j_adapter = neo4j_adapter

    async def replay_decision(
        self,
        run_id: str,
        controller: SwarmController,
        new_plan: SwarmPlan = None
    ) -> ReplayReport:
        """
        Replays a decision, optionally with a new plan or policies.
        It uses historical results from Neo4j to ensure determinism.
        """
        # 1. Fetch the historical context
        original_run_context = self.neo4j_adapter.fetch_full_run_context(run_id)
        if not original_run_context:
            raise ValueError(f"No data found for run_id: {run_id}")

        # 2. Use the new plan if provided, otherwise use the original
        plan_to_replay = new_plan if new_plan else original_run_context['plan']

        # 3. Set the controller to replay mode
        controller.set_replay_mode(original_run_context['results'])

        # 4. Re-execute with the historical context
        alert = original_run_context['alert']
        replayed_decision, _ = await controller.aexecute_plan(plan_to_replay, alert)

        # 5. Reset controller mode and generate report
        controller.disable_replay_mode()

        original_decision = original_run_context['decision']

        divergences = []
        if replayed_decision.action_proposed != original_decision['action_proposed']:
            divergences.append(
                f"Action mismatch: original='{original_decision['action_proposed']}', "
                f"replayed='{replayed_decision.action_proposed}'"
            )

        return ReplayReport(
            run_id=run_id,
            original_action=original_decision['action_proposed'],
            replayed_action=replayed_decision.action_proposed,
            confidence_delta=(replayed_decision.confidence - original_decision['confidence']),
            divergences=divergences
        )
