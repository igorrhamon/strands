
import math
from datetime import datetime, timedelta
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.core.models import HumanDecision, OperationalOutcome
from swarm_intelligence.core.swarm import Agent

class ConfidenceService:
    """
    Manages the dynamic confidence of agents, applying decay, penalties,
    and reinforcements based on outcomes.
    """
    def __init__(self, neo4j_adapter: Neo4jAdapter, decay_rate: float = 0.01):
        self.neo4j_adapter = neo4j_adapter
        self.decay_rate = decay_rate

    def get_agent_credibility(self, agent_id: str) -> float:
        """Retrieves the current credibility score of an agent from the graph."""
        # This is a conceptual implementation. It would fetch the agent's current score.
        # For this example, we'll return a default value.
        return 1.0

    def calculate_effective_confidence(self, agent_id: str, base_confidence: float) -> float:
        """Calculates the effective confidence by factoring in the agent's credibility."""
        credibility = self.get_agent_credibility(agent_id)
        return base_confidence * credibility

    def apply_time_decay_to_all_agents(self):
        """Applies a time-based decay to the credibility of all agents."""
        # This would be a system-wide maintenance task.
        query = """
        MATCH (a:Agent)
        SET a.credibility = a.credibility * (1 - $decay_rate)
        """
        self.neo4j_adapter.run_transaction(query, {"decay_rate": self.decay_rate})

    def penalize_agent_after_override(self, agent_id: str, penalty: float = 0.1):
        """Penalizes an agent's credibility after its decision was overridden."""
        query = """
        MATCH (a:Agent {id: $agent_id})
        SET a.credibility = a.credibility - $penalty
        """
        self.neo4j_adapter.run_transaction(query, {"agent_id": agent_id, "penalty": penalty})

    def reinforce_agent_after_success(self, agent_id: str, reinforcement: float = 0.05):
        """Reinforces an agent's credibility after a successful operational outcome."""
        query = """
        MATCH (a:Agent {id: $agent_id})
        SET a.credibility = a.credibility + $reinforcement
        """
        self.neo4j_adapter.run_transaction(query, {"agent_id": agent_id, "reinforcement": reinforcement})
