"""ConfidenceService for managing agent credibility and confidence tracking."""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConfidencePolicy:
    """Policy for confidence penalties and reinforcements."""
    
    def __init__(self, penalty_override: float = 0.1, reinforcement_success: float = 0.05):
        """Initialize confidence policy.
        
        Args:
            penalty_override: Penalty for human override (0.0-1.0)
            reinforcement_success: Reinforcement for success (0.0-1.0)
        """
        self.penalty_override = penalty_override
        self.reinforcement_success = reinforcement_success
    
    def get_penalty_for_override(self) -> float:
        """Get penalty value for human override."""
        return self.penalty_override
    
    def get_reinforcement_for_success(self) -> float:
        """Get reinforcement value for successful outcome."""
        return self.reinforcement_success


class ConfidenceService:
    """Manages the dynamic credibility of agents by creating traceable confidence snapshots."""
    
    def __init__(self, neo4j_adapter=None):
        """Initialize confidence service.
        
        Args:
            neo4j_adapter: Optional Neo4j adapter for persistence
        """
        self.neo4j_adapter = neo4j_adapter
        self._confidence_cache: Dict[str, float] = {}
    
    def get_last_confidence(self, agent_id: str) -> float:
        """Fetch the latest confidence score for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Confidence score (0.0-1.0), defaults to 1.0
        """
        if agent_id in self._confidence_cache:
            return self._confidence_cache[agent_id]
        
        # If Neo4j adapter available, query from database
        if self.neo4j_adapter:
            try:
                query = """
                MATCH (a:Agent {id: $agent_id})-[:HAS_CONFIDENCE]->(s:ConfidenceSnapshot)
                RETURN s.value ORDER BY s.sequence_id DESC LIMIT 1
                """
                result = self.neo4j_adapter.run_read_transaction(query, {"agent_id": agent_id})
                if result:
                    confidence = result[0]['s.value']
                    self._confidence_cache[agent_id] = confidence
                    return confidence
            except Exception as e:
                logger.warning(f"Failed to query confidence from Neo4j: {e}")
        
        return 1.0  # Default confidence
    
    def _get_next_sequence_id(self) -> int:
        """Fetch the latest sequence_id and increment it."""
        if not self.neo4j_adapter:
            return 1
        
        try:
            query = """
            MATCH (s:ConfidenceSnapshot)
            RETURN s.sequence_id ORDER BY s.sequence_id DESC LIMIT 1
            """
            result = self.neo4j_adapter.run_read_transaction(query)
            return result[0]['s.sequence_id'] + 1 if result else 1
        except Exception as e:
            logger.warning(f"Failed to get sequence ID: {e}")
            return 1
    
    def record_confidence_snapshot(self, agent_id: str, value: float, source_event: str, 
                                  cause_id: Optional[str] = None, cause_type: Optional[str] = None) -> None:
        """Create a confidence snapshot and optionally link it to its cause.
        
        Args:
            agent_id: Agent identifier
            value: Confidence value (0.0-1.0)
            source_event: Source event type
            cause_id: Optional cause identifier
            cause_type: Optional cause type
        """
        # Clamp value to valid range
        clamped_value = max(0.0, min(1.0, value))
        
        # Update cache
        self._confidence_cache[agent_id] = clamped_value
        
        # Persist to Neo4j if available
        if self.neo4j_adapter:
            try:
                sequence_id = self._get_next_sequence_id()
                snapshot_id = self.neo4j_adapter.create_confidence_snapshot(
                    agent_id, clamped_value, source_event, sequence_id
                )
                
                if snapshot_id and cause_id and cause_type:
                    self.neo4j_adapter.link_snapshot_to_cause(snapshot_id, cause_id, cause_type)
                
                logger.debug(f"Recorded confidence snapshot for {agent_id}: {clamped_value}")
            except Exception as e:
                logger.warning(f"Failed to record confidence snapshot: {e}")
    
    def apply_time_decay(self, agent_id: str, decay_rate: float) -> None:
        """Apply time-based decay to agent confidence.
        
        Args:
            agent_id: Agent identifier
            decay_rate: Decay rate (0.0-1.0)
        """
        last_credibility = self.get_last_confidence(agent_id)
        decayed_value = last_credibility * (1 - decay_rate)
        self.record_confidence_snapshot(
            agent_id, decayed_value, "time_decay",
            cause_id=agent_id, cause_type="SystemEvent"
        )
        logger.debug(f"Applied time decay to {agent_id}: {last_credibility} -> {decayed_value}")
    
    def penalize_for_override(self, agent_id: str, decision_id: str, policy: ConfidencePolicy) -> None:
        """Apply a penalty for human override.
        
        Args:
            agent_id: Agent identifier
            decision_id: Decision identifier
            policy: Confidence policy with penalty value
        """
        last_credibility = self.get_last_confidence(agent_id)
        penalty = policy.get_penalty_for_override()
        penalized_value = max(0.0, last_credibility - penalty)
        self.record_confidence_snapshot(
            agent_id, penalized_value, "human_override",
            cause_id=decision_id, cause_type="Decision"
        )
        logger.info(f"Penalized {agent_id} for override: {last_credibility} -> {penalized_value}")
    
    def reinforce_for_success(self, agent_id: str, decision_id: str, policy: ConfidencePolicy) -> None:
        """Apply reinforcement for successful outcome.
        
        Args:
            agent_id: Agent identifier
            decision_id: Decision identifier
            policy: Confidence policy with reinforcement value
        """
        last_credibility = self.get_last_confidence(agent_id)
        reinforcement = policy.get_reinforcement_for_success()
        reinforced_value = min(1.0, last_credibility + reinforcement)
        self.record_confidence_snapshot(
            agent_id, reinforced_value, "successful_outcome",
            cause_id=decision_id, cause_type="Decision"
        )
        logger.info(f"Reinforced {agent_id} for success: {last_credibility} -> {reinforced_value}")
    
    def get_confidence_summary(self, agent_id: str) -> Dict[str, Any]:
        """Get summary of agent confidence.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Dictionary with confidence summary
        """
        return {
            "agent_id": agent_id,
            "current_confidence": self.get_last_confidence(agent_id),
            "cached": agent_id in self._confidence_cache
        }
