"""
Repository Context Agent - RAG Logic

Provides historical context for alerts by combining:
1. Semantic similarity search (EmbeddingAgent)
2. Repository metadata (GitHub MCP)

Part of the multi-agent pipeline for enriched decision-making.
"""

import logging
from typing import Optional
from uuid import UUID

from src.models.cluster import AlertCluster
from src.models.embedding import SimilarityResult
from src.models.decision import SemanticEvidence
from src.agents.embedding_agent import EmbeddingAgent, EmbeddingAgentError

logger = logging.getLogger(__name__)


class RepositoryContextAgent:
    """
    Agent responsible for:
    1. Building context from semantic similarity search
    2. Enriching with repository metadata
    3. Preparing historical evidence for DecisionEngine
    
    This agent provides RAG functionality for alert decisions.
    """
    
    AGENT_NAME = "RepositoryContextAgent"
    TIMEOUT_SECONDS = 20.0
    
    def __init__(
        self,
        embedding_agent: Optional[EmbeddingAgent] = None,
        top_k: int = 5,
        score_threshold: float = 0.75,
    ):
        """
        Initialize repository context agent.
        
        Args:
            embedding_agent: EmbeddingAgent for semantic search.
            top_k: Maximum similar results to retrieve.
            score_threshold: Minimum similarity score.
        """
        self._embedding_agent = embedding_agent or EmbeddingAgent(
            top_k=top_k,
            score_threshold=score_threshold,
        )
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
        
        # Build query from cluster alerts
        query_text = self._build_query_text(cluster)
        
        # Search semantic memory
        try:
            similar_results = self._embedding_agent.search_similar(
                alert_description=query_text,
                service=cluster.primary_service,
            )
        except EmbeddingAgentError as e:
            logger.warning(f"[{self.AGENT_NAME}] Semantic search failed: {e}")
            similar_results = []
        
        # Convert to SemanticEvidence
        semantic_evidence = self._convert_to_evidence(similar_results)
        
        # Calculate context quality
        context_quality = self._calculate_quality(similar_results)
        
        logger.info(
            f"[{self.AGENT_NAME}] Found {len(semantic_evidence)} evidence items "
            f"(quality: {context_quality:.2f})"
        )
        
        return {
            "semantic_evidence": semantic_evidence,
            "repository_context": await self._get_repo_metadata(cluster.primary_service),
            "context_quality": context_quality,
            "similar_count": len(similar_results),
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
                # If already in async context, return empty results
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
    
    def _build_query_text(self, cluster: AlertCluster) -> str:
        """Build query text from cluster for similarity search."""
        # Combine all alert descriptions
        descriptions = [a.description for a in cluster.alerts]
        combined = " | ".join(descriptions[:5])  # Limit to first 5
        
        return f"Service: {cluster.primary_service} | Severity: {cluster.primary_severity} | {combined}"
    
    def _convert_to_evidence(
        self, results: list[SimilarityResult]
    ) -> list[SemanticEvidence]:
        """Convert SimilarityResult to SemanticEvidence for decision context."""
        return [
            SemanticEvidence(
                decision_id=r.decision_id,
                similarity_score=r.similarity_score,
                summary=self._summarize_source_text(r.source_text),
            )
            for r in results
            if r.similarity_score >= self._score_threshold
        ]
    
    def _summarize_source_text(self, source_text: str, max_length: int = 150) -> str:
        """Create a brief summary of the source text."""
        if len(source_text) <= max_length:
            return source_text
        return source_text[:max_length] + "..."
    
    def _calculate_quality(self, results: list[SimilarityResult]) -> float:
        """
        Calculate context quality score.
        
        Quality factors:
        - Number of results
        - Average similarity score
        - Presence of high-confidence matches
        """
        if not results:
            return 0.0
        
        # Average score
        avg_score = sum(r.similarity_score for r in results) / len(results)
        
        # Bonus for high-confidence matches
        high_confidence = sum(1 for r in results if r.similarity_score >= 0.9)
        confidence_bonus = min(0.2, high_confidence * 0.05)
        
        # Count factor (more results = more confidence, up to a point)
        count_factor = min(1.0, len(results) / 3)  # Max at 3 results
        
        quality = (avg_score * 0.6) + (count_factor * 0.2) + confidence_bonus
        return min(1.0, quality)
    
    async def _get_repo_metadata(self, service: str) -> dict:
        """
        Get repository metadata for a service.
        
        Args:
            service: Service name to look up.
        
        Returns:
            Dict with repository information.
        """
        # Placeholder - would use github_mcp.py in real implementation
        return {
            "service": service,
            "repository": f"org/{service}",
            "team": "platform",
            "on_call": None,  # Would be populated by OnCall integration
        }
    
    def close(self) -> None:
        """Close agent connections."""
        self._embedding_agent.close()


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
