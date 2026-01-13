
from dataclasses import dataclass, field
from typing import List, Dict, Any
from swarm_intelligence.core.models import Decision, SwarmPlan, Alert, ReplayReport
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.controller import SwarmController

class ReplayEngine:
    """
    Executes a deterministic replay of a past swarm run for auditing and
    evaluating the impact of new policies or agent versions.
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
        original_run_context = self.neo4j_adapter.fetch_full_run_context(run_id)
        if not original_run_context:
            raise ValueError(f"No data found for run_id: {run_id}")

        plan_to_replay = new_plan if new_plan else original_run_context['plan']

        controller.set_replay_mode(original_run_context['results'])

        alert = original_run_context['alert']
        replayed_decision, _, _ = await controller.aexecute_plan(plan_to_replay, alert)

        controller.disable_replay_mode()

        original_decision = original_run_context['decision']

        divergences = []
        if replayed_decision.action_proposed != original_decision['action_proposed']:
            divergences.append(
                f"Action mismatch: original='{original_decision['action_proposed']}', "
                f"replayed='{replayed_decision.action_proposed}'"
            )

        report = ReplayReport(
            original_decision_id=original_decision['id'],
            replayed_decision_id=replayed_decision.decision_id,
            causal_divergences=divergences,
            confidence_delta=(replayed_decision.confidence - original_decision['confidence'])
        )

        self.neo4j_adapter.save_replay_report(report)
        return report
