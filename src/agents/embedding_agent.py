"""
Embedding Agent - Vector Store Interaction Manager

Manages all interactions with the Vector Store for semantic memory.
Constitution Principle III: Only CONFIRMED decisions are embedded.
"""

import logging
from typing import Optional
from uuid import UUID

from src.models.embedding import VectorEmbedding, SimilarityResult
from src.models.decision import Decision, HumanValidationStatus
from src.tools.vector_store import VectorStore, VectorStoreError
from src.tools.embedding_client import create_embedding_text

logger = logging.getLogger(__name__)


class EmbeddingAgentError(Exception):
    """Raised when embedding agent operations fail."""
    pass


class EmbeddingAgent:
    """
    Agent responsible for:
    1. Searching semantic memory for similar past decisions
    2. Persisting embeddings for CONFIRMED decisions only
    3. Managing embedding lifecycle
    
    Constitution Principle III Enforcement:
    - persist_decision() validates confirmation status
    - Unconfirmed decisions raise an error
    """
    
    AGENT_NAME = "EmbeddingAgent"
    TIMEOUT_SECONDS = 15.0
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        top_k: int = 5,
        score_threshold: float = 0.75,
        auto_connect: bool = True,
    ):
        """
        Initialize embedding agent.
        
        Args:
            vector_store: VectorStore instance (created if None).
            top_k: Maximum similar results to return.
            score_threshold: Minimum similarity score.
            auto_connect: Whether to connect on first use.
        """
        self._store = vector_store or VectorStore(
            top_k=top_k,
            score_threshold=score_threshold,
        )
        self._auto_connect = auto_connect
        self._connected = False
    
    def _ensure_connected(self) -> None:
        """Ensure vector store is connected."""
        if not self._connected and self._auto_connect:
            try:
                self._store.connect()
                self._connected = True
            except VectorStoreError as e:
                raise EmbeddingAgentError(f"Failed to connect: {e}") from e
    
    def search_similar(
        self,
        alert_description: str,
        service: Optional[str] = None,
        severity_filter: Optional[list[str]] = None,
    ) -> list[SimilarityResult]:
        """
        Search for semantically similar past decisions.
        
        Args:
            alert_description: Current alert text to find matches for.
            service: Optional service filter.
            severity_filter: Optional severity filter.
        
        Returns:
            List of SimilarityResult objects ordered by score.
        """
        self._ensure_connected()
        
        logger.info(f"[{self.AGENT_NAME}] Searching for similar decisions")
        
        try:
            results = self._store.search_similar(
                query_text=alert_description,
                service_filter=service,
                severity_filter=severity_filter,
            )
            
            logger.info(f"[{self.AGENT_NAME}] Found {len(results)} similar decisions")
            return results
        
        except VectorStoreError as e:
            logger.error(f"[{self.AGENT_NAME}] Search failed: {e}")
            return []  # Graceful degradation
    
    async def persist_confirmed_decision(
        self,
        decision: Decision,
        alert_description: str | None = None,
        human_validator: str | None = None,
        cluster = None,  # Cluster context (optional, for backward compatibility)
        **kwargs,  # Absorb any other unexpected kwargs
    ) -> VectorEmbedding:
        """
        Persist a CONFIRMED decision to semantic memory.
        
        Constitution Principle III: Only CONFIRMED decisions are embedded.
        
        Args:
            decision: The decision to embed (must be CONFIRMED).
            alert_description: Original alert text.
            human_validator: ID of confirming human.
        
        Returns:
            VectorEmbedding representing the stored embedding.
        
        Raises:
            EmbeddingAgentError: If decision is not confirmed.
        """
        self._ensure_connected()
        
        # Constitution Principle III Enforcement
        if not decision.is_confirmed:
            raise EmbeddingAgentError(
                "Cannot persist embedding for unconfirmed decision. "
                "Constitution Principle III: Embeddings only after human confirmation."
            )
        
        logger.info(
            f"[{self.AGENT_NAME}] Persisting embedding for decision {decision.decision_id}"
        )
        
        try:
            embedding = self._store.persist_decision(
                decision=decision,
                alert_description=alert_description,
                human_validator=human_validator,
            )
            
            # Handle both string IDs (from mocks) and VectorEmbedding objects (from real store)
            embedding_id = embedding if isinstance(embedding, str) else getattr(embedding, 'vector_id', str(embedding))
            logger.info(
                f"[{self.AGENT_NAME}] Persisted embedding {embedding_id} "
                f"for decision {decision.decision_id}"
            )
            
            return embedding
        
        except VectorStoreError as e:
            raise EmbeddingAgentError(f"Failed to persist: {e}") from e
    
    def get_embedding_count(self) -> int:
        """Return total number of embeddings in store."""
        self._ensure_connected()
        return self._store.count_embeddings()
    
    def delete_embedding(self, vector_id: UUID) -> None:
        """Delete a specific embedding."""
        self._ensure_connected()
        self._store.delete_embedding(vector_id)
        logger.info(f"[{self.AGENT_NAME}] Deleted embedding {vector_id}")
    
    def close(self) -> None:
        """Close connections."""
        if self._connected:
            self._store.close()
            self._connected = False


# Strands agent tool definition
EMBEDDING_AGENT_TOOL = {
    "name": "semantic_memory_search",
    "description": "Search semantic memory for similar past decisions",
    "parameters": {
        "type": "object",
        "properties": {
            "alert_description": {
                "type": "string",
                "description": "Alert text to search for similar decisions",
            },
            "service": {
                "type": "string",
                "description": "Optional service filter",
            },
            "severity_filter": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional severity filter",
            },
        },
        "required": ["alert_description"],
    },
}


def execute_search_tool(
    alert_description: str,
    service: Optional[str] = None,
    severity_filter: Optional[list[str]] = None,
) -> dict:
    """
    Tool execution function for Strands integration.
    
    Returns dict format expected by Strands agent framework.
    """
    agent = EmbeddingAgent()
    try:
        results = agent.search_similar(
            alert_description=alert_description,
            service=service,
            severity_filter=severity_filter,
        )
        
        return {
            "result_count": len(results),
            "results": [
                {
                    "decision_id": str(r.decision_id),
                    "similarity_score": r.similarity_score,
                    "source_text": r.source_text[:200] + "..." if len(r.source_text) > 200 else r.source_text,
                    "service": r.service,
                    "rules_applied": r.rules_applied,
                }
                for r in results
            ],
        }
    finally:
        agent.close()
