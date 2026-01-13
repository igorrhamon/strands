
from datetime import datetime
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.core.swarm import Agent

class ConfidenceService:
    """
    Manages the dynamic credibility of agents by creating traceable
    ConfidenceSnapshot nodes in the graph.
    """
    def __init__(self, neo4j_adapter: Neo4jAdapter, decay_rate: float = 0.001):
        self.neo4j_adapter = neo4j_adapter
        self.decay_rate = decay_rate

    def get_last_confidence(self, agent_id: str) -> float:
        """Fetches the latest confidence score for an agent."""
        query = """
        MATCH (a:Agent {id: $agent_id})-[:HAS_CONFIDENCE]->(s:ConfidenceSnapshot)
        RETURN s.value ORDER BY s.timestamp DESC LIMIT 1
        """
        result = self.neo4j_adapter.run_read_transaction(query, {"agent_id": agent_id})
        return result[0]['s.value'] if result else 1.0  # Default to 1.0 if no history

    def record_confidence_snapshot(self, agent_id: str, value: float, source_event: str, linked_decision_id: str = None):
        """Creates a new ConfidenceSnapshot, ensuring the value is clamped."""
        clamped_value = max(0.0, min(1.0, value))
        query = """
        MATCH (a:Agent {id: $agent_id})
        CREATE (s:ConfidenceSnapshot {
            id: randomUUID(),
            value: $value,
            source_event: $source_event,
            linked_decision_id: $linked_decision_id,
            timestamp: datetime()
        })
        CREATE (a)-[:HAS_CONFIDENCE]->(s)
        """
        self.neo4j_adapter.run_transaction(query, {
            "agent_id": agent_id,
            "value": clamped_value,
            "source_event": source_event,
            "linked_decision_id": linked_decision_id
        })

    def apply_time_decay(self, agent_id: str):
        """Applies time-based decay and records a snapshot."""
        last_credibility = self.get_last_confidence(agent_id)
        decayed_value = last_credibility * (1 - self.decay_rate)
        self.record_confidence_snapshot(agent_id, decayed_value, "time_decay")

    def penalize_for_override(self, agent_id: str, decision_id: str, penalty: float = 0.1):
        """Applies a penalty for a human override and records a snapshot."""
        last_credibility = self.get_last_confidence(agent_id)
        penalized_value = last_credibility - penalty
        self.record_confidence_snapshot(agent_id, penalized_value, "human_override", linked_decision_id=decision_id)

    def reinforce_for_success(self, agent_id: str, decision_id: str, reinforcement: float = 0.05):
        """Applies a reinforcement for a successful outcome and records a snapshot."""
        last_credibility = self.get_last_confidence(agent_id)
        reinforced_value = last_credibility + reinforcement
        self.record_confidence_snapshot(agent_id, reinforced_value, "successful_outcome", linked_decision_id=decision_id)
