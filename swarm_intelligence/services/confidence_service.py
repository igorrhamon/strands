
import logging
from datetime import datetime
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.core.swarm import Agent
from swarm_intelligence.policy.confidence_policy import ConfidencePolicy

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

    def _get_next_sequence_id(self) -> int:
        """Fetches the latest sequence_id and increments it."""
        query = """
        MATCH (s:ConfidenceSnapshot)
        RETURN s.sequence_id ORDER BY s.sequence_id DESC LIMIT 1
        """
        result = self.neo4j_adapter.run_read_transaction(query)
        return result[0]['s.sequence_id'] + 1 if result else 1

    def record_confidence_snapshot(self, agent_id: str, value: float, source_event: str, cause_id: str = None, cause_type: str = None):
        """Creates a snapshot and optionally links it to its cause."""
        clamped_value = max(0.0, min(1.0, value))
        sequence_id = self._get_next_sequence_id()

        # Create the snapshot node
        snapshot_id = self.neo4j_adapter.create_confidence_snapshot(agent_id, clamped_value, source_event, sequence_id)
        
        if snapshot_id is None:
            logging.warning(f"Failed to create confidence snapshot for agent {agent_id}, skipping cause linkage")
            return

        # Link it to its cause
        if cause_id and cause_type:
            self.neo4j_adapter.link_snapshot_to_cause(snapshot_id, cause_id, cause_type)

    def apply_time_decay(self, agent_id: str, decay_rate: float):
        """Applies time-based decay and records a snapshot."""
        last_credibility = self.get_last_confidence(agent_id)
        decayed_value = last_credibility * (1 - decay_rate)
        self.record_confidence_snapshot(agent_id, decayed_value, "time_decay", cause_id=agent_id, cause_type="SystemEvent")

    def penalize_for_override(self, agent_id: str, decision_id: str, policy: ConfidencePolicy):
        """Applies a penalty from a policy and records a snapshot causally linked to the decision."""
        last_credibility = self.get_last_confidence(agent_id)
        penalty = policy.get_penalty_for_override()
        penalized_value = last_credibility - penalty
        self.record_confidence_snapshot(agent_id, penalized_value, "human_override", cause_id=decision_id, cause_type="Decision")

    def reinforce_for_success(self, agent_id: str, decision_id: str, policy: ConfidencePolicy):
        """Applies a reinforcement from a policy and records a snapshot causally linked to the decision."""
        last_credibility = self.get_last_confidence(agent_id)
        reinforcement = policy.get_reinforcement_for_success()
        reinforced_value = last_credibility + reinforcement
        self.record_confidence_snapshot(agent_id, reinforced_value, "successful_outcome", cause_id=decision_id, cause_type="Decision")
