"""
Repository Context Agent - RAG Logic

Provides historical context for alerts by combining:
1. Semantic similarity search (Ollama embeddings)
2. Vector store (Qdrant)
3. Repository metadata (GitHub MCP)

Part of the multi-agent pipeline for enriched decision-making.
"""

import logging
from typing import Any, Optional

from src.models.cluster import AlertCluster
from src.models.decision import SemanticEvidence
from src.pipeline.refrag_pipeline import create_refrag_repository

logger = logging.getLogger(__name__)


class RepositoryContextAgent:
    """
    Agent responsible for:
    1. Building context from semantic similarity search via Ollama
    2. Enriching with repository metadata from GitHub MCP
    3. Preparing historical evidence for DecisionEngine
    
    This agent provides RAG functionality for alert decisions.
    """
    
    AGENT_NAME = "RepositoryContextAgent"
    TIMEOUT_SECONDS = 20.0
    
    def __init__(
        self,
        refrag_repo: Optional[Any] = None,
        top_k: int = 5,
        score_threshold: float = 0.75,
    ):
        """
        Initialize repository context agent.
        
        Args:
            refrag_repo: RefragRepository for semantic search and repo context.
            top_k: Maximum similar results to retrieve.
            score_threshold: Minimum similarity score.
        """
        self._refrag_repo = refrag_repo or create_refrag_repository()  # type: ignore[attr-defined]
        self._top_k = top_k
        self._score_threshold = score_threshold
    
    async def get_context(
        self,
        cluster: AlertCluster,
    ) -> dict:
        """
        Get historical context for an alert cluster.
        
        Args:
            cluster: AlertCluster to find context for.
        
        Returns:
            Dict containing:
            - semantic_evidence: List of similar past decisions
            - repository_context: Dict of repo metadata
            - context_quality: Quality score for the context
        """
        logger.info(
            f"[{self.AGENT_NAME}] Getting context for cluster {cluster.cluster_id}"
        )
        
        try:
            context = await self._refrag_repo.get_semantic_context(  # type: ignore[attr-defined]
                cluster,
                top_k=self._top_k,
                score_threshold=self._score_threshold,
            )
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Context retrieval failed: {e}")
            context = {
                "semantic_evidence": [],
                "repository_context": {},
                "context_quality": 0.0,
            }
        
        semantic_evidence = [
            SemanticEvidence(
                decision_id=e["decision_id"],
                similarity_score=e["similarity_score"],
                summary=e["summary"],
            )
            for e in context.get("semantic_evidence", [])
        ]
        
        logger.info(
            f"[{self.AGENT_NAME}] Found {len(semantic_evidence)} evidence items "
            f"(quality: {context.get('context_quality', 0.0):.2f})"
        )
        
        return {
            "semantic_evidence": semantic_evidence,
            "repository_context": context.get("repository_context", {}),
            "context_quality": context.get("context_quality", 0.0),
            "similar_count": len(semantic_evidence),
        }
    
    def get_context_sync(self, cluster: AlertCluster) -> dict:
        """
        Synchronous wrapper for context retrieval (for multi-agent tools).
        
        Args:
            cluster: AlertCluster to find context for.
        
        Returns:
            Dict with context data.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning(f"[{self.AGENT_NAME}] Cannot run async in event loop")
                return {
                    "semantic_evidence": [],
                    "repository_context": {},
                    "context_quality": 0.0,
                    "similar_count": 0,
                }
        except RuntimeError:
            pass
        
        return asyncio.run(self.get_context(cluster))
    
    def close(self) -> None:
        """Close repository connections."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Save the created task to avoid premature garbage collection
                _task = asyncio.create_task(self._refrag_repo.close())  # type: ignore[attr-defined]
            else:
                asyncio.run(self._refrag_repo.close())  # type: ignore[attr-defined]
        except RuntimeError:
            asyncio.run(self._refrag_repo.close())  # type: ignore[attr-defined]
    def _calculate_quality(self, results: list[dict]) -> float:
        """Calculate context quality score from vector search results.

        Accepts a list of dicts with key `similarity_score` and returns a
        normalized quality score in [0.0, 1.0].
        """
        if not results:
            return 0.0

        avg_score = sum(r.get("similarity_score", 0.0) for r in results) / len(results)
        high_confidence = sum(1 for r in results if r.get("similarity_score", 0.0) >= 0.9)
        confidence_bonus = min(0.2, high_confidence * 0.05)
        count_factor = min(1.0, len(results) / 3)

        quality = (avg_score * 0.6) + (count_factor * 0.2) + confidence_bonus
        return min(1.0, quality)

    async def _get_repo_metadata(self, service: str) -> dict:
        """Get repository metadata for a service."""
        return await self._refrag_repo.github_repo.get_repository_info(service)  # type: ignore[attr-defined]


# Strands agent tool definition
REPOSITORY_CONTEXT_TOOL = {
    "name": "repository_context",
    "description": "Get historical context and repository metadata for alerts",
    "parameters": {
        "type": "object",
        "properties": {
            "cluster_id": {
                "type": "string",
                "description": "ID of the cluster to get context for",
            },
            "service": {
                "type": "string",
                "description": "Service name for context lookup",
            },
            "alert_description": {
                "type": "string",
                "description": "Combined alert descriptions for similarity search",
            },
        },
        "required": ["service", "alert_description"],
    },
}


async def execute_context_tool(
    service: str,
    alert_description: str,
) -> dict:
    """
    Tool execution function for Strands integration.
    
    Returns dict format expected by Strands agent framework.
    """
    from datetime import datetime, timezone
    from src.models.alert import NormalizedAlert, ValidationStatus
    from src.models.cluster import AlertCluster
    
    # Create minimal cluster for context lookup
    mock_alert = NormalizedAlert(
        timestamp=datetime.now(timezone.utc),
        fingerprint="context-lookup",
        service=service,
        severity="warning",
        description=alert_description,
        labels={},
        validation_status=ValidationStatus.VALID,
        validation_errors=None,
    )
    cluster = AlertCluster.from_alerts([mock_alert], correlation_score=1.0)
    
    agent = RepositoryContextAgent()
    try:
        context = await agent.get_context(cluster)
        
        # Convert SemanticEvidence to serializable format
        evidence = [
            {
                "decision_id": str(e.decision_id),
                "similarity_score": e.similarity_score,
                "summary": e.summary,
            }
            for e in context["semantic_evidence"]
        ]
        
        return {
            "semantic_evidence": evidence,
            "repository_context": context["repository_context"],
            "context_quality": context["context_quality"],
            "similar_count": context["similar_count"],
        }
    finally:
        agent.close()
