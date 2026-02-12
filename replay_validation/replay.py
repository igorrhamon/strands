
from dataclasses import dataclass, field
from typing import List, Dict, Any
from swarm_intelligence.core.models import Decision, SwarmPlan, Alert, ReplayReport
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.coordinators.swarm_run_coordinator import SwarmRunCoordinator

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
        coordinator: SwarmRunCoordinator,
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
        domain_to_replay = original_run_context['domain']

        # Note: Replay mode configuration methods not available on SwarmRunCoordinator
        # coordinator.set_replay_mode(original_run_context['results'])

        alert = original_run_context.get('alert')
        original_seed = original_run_context.get('master_seed')

        replayed_run, _, _ = await coordinator.aexecute_plan(domain_to_replay, plan_to_replay, alert, run_id, master_seed=original_seed)
        replayed_decision = replayed_run.final_decision

        # coordinator.disable_replay_mode()

        original_decision = original_run_context.get('decision')
        if not original_decision:
            # If no decision data in context, skip comparison
            import uuid as uuid_module
            report = ReplayReport(
                original_decision_id=str(uuid_module.uuid4()),
                replayed_decision_id=replayed_decision.decision_id,
                causal_divergences=["Original decision data not found in context"],
                confidence_delta=0.0
            )
        else:
            # Causal comparison
            original_evidence_ids = {ev.get('id') or ev.get('evidence_id') for ev in original_run_context.get('evidence', []) if isinstance(ev, dict)}
            replayed_evidence_ids = {ev.evidence_id for ev in replayed_decision.supporting_evidence}

            divergences = []
            if original_evidence_ids != replayed_evidence_ids:
                divergences.append(f"Evidence set mismatch. Original: {original_evidence_ids}, Replayed: {replayed_evidence_ids}")

            if original_decision.get('action_proposed') != replayed_decision.action_proposed:
                divergences.append(f"Final action mismatch.")

            report = ReplayReport(
                original_decision_id=original_decision.get('id', str(uuid_module.uuid4())),
                replayed_decision_id=replayed_decision.decision_id,
                causal_divergences=divergences,
                confidence_delta=(replayed_decision.confidence - original_decision.get('confidence', 0.0))
            )

        self.neo4j_adapter.save_replay_report(report)
        return report
