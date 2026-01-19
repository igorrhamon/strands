
from datetime import datetime
from typing import Optional
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.core.swarm import Agent
from swarm_intelligence.policy.confidence_policy import ConfidencePolicy
from swarm_intelligence.core.enums import ConfidenceCauseType
from swarm_intelligence.core.models import SystemEvent

class ConfidenceService:
    """
    Manages the dynamic credibility of agents by creating traceable
    ConfidenceSnapshot nodes and their causal links in the graph.
    """
    def __init__(self, neo4j_adapter: Neo4jAdapter):
        self.neo4j_adapter = neo4j_adapter

    def get_last_confidence(self, agent_id: str) -> float:
        """Fetches the latest confidence score for an agent, ordered by sequence."""
        query = """
        MATCH (a:Agent {id: $agent_id})-[:HAS_CONFIDENCE]->(s:ConfidenceSnapshot)
        RETURN s.value ORDER BY s.sequence_id DESC LIMIT 1
        """
        result = self.neo4j_adapter.run_read_transaction(query, {"agent_id": agent_id})
        return result[0]['s.value'] if result else 1.0  # Default to 1.0

    def record_confidence_snapshot(
        self,
        agent_id: str,
        value: float,
        source_event: str,
        sequence_id: int,
        cause_id: Optional[str] = None,
        cause_type: Optional[ConfidenceCauseType] = None
    ) -> float:
        """
        Creates a snapshot, optionally links it to its cause, and returns the clamped value.
        """
        clamped_value = max(0.0, min(1.0, value))

        # Create the snapshot node
        snapshot_id = self.neo4j_adapter.create_confidence_snapshot(agent_id, clamped_value, source_event, sequence_id)

        # Link it to its cause
        if cause_id and cause_type:
            self.neo4j_adapter.link_snapshot_to_cause(snapshot_id, cause_id, cause_type.value)

        return clamped_value

    def apply_time_decay(
        self,
        agent_id: str,
        sequence_id: int,
        decay_rate: float,
        last_confidence: Optional[float] = None
    ) -> float:
        """
        Applies time-based decay, records a snapshot, and returns the new confidence.
        """
        base_confidence = last_confidence if last_confidence is not None else self.get_last_confidence(agent_id)
        decayed_value = base_confidence * (1 - decay_rate)

        system_event = SystemEvent(
            event_type="TIME_DECAY",
            description=f"Time decay applied to agent {agent_id} with rate {decay_rate}",
            sequence_id=sequence_id
        )
        event_id = self.neo4j_adapter.create_system_event(system_event)

        return self.record_confidence_snapshot(
            agent_id,
            decayed_value,
            "time_decay",
            sequence_id,
            cause_id=event_id,
            cause_type=ConfidenceCauseType.SYSTEM_EVENT
        )

    def penalize_for_override(
        self,
        agent_id: str,
        decision_id: str,
        sequence_id: int,
        policy: ConfidencePolicy,
        last_confidence: Optional[float] = None
    ) -> float:
        """
        Applies a penalty, records a snapshot, and returns the new confidence.
        """
        base_confidence = last_confidence if last_confidence is not None else self.get_last_confidence(agent_id)
        penalty = policy.get_penalty_for_override()
        penalized_value = base_confidence - penalty

        return self.record_confidence_snapshot(
            agent_id,
            penalized_value,
            "human_override",
            sequence_id,
            cause_id=decision_id,
            cause_type=ConfidenceCauseType.DECISION
        )

    def reinforce_for_success(
        self,
        agent_id: str,
        decision_id: str,
        sequence_id: int,
        policy: ConfidencePolicy,
        last_confidence: Optional[float] = None
    ) -> float:
        """
        Applies reinforcement, records a snapshot, and returns the new confidence.
        """
        base_confidence = last_confidence if last_confidence is not None else self.get_last_confidence(agent_id)
        reinforcement = policy.get_reinforcement_for_success()
        reinforced_value = base_confidence + reinforcement

        return self.record_confidence_snapshot(
            agent_id,
            reinforced_value,
            "successful_outcome",
            sequence_id,
            cause_id=decision_id,
            cause_type=ConfidenceCauseType.DECISION
        )
