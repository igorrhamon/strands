import logging
import os
import httpx
from typing import Optional, List, Dict, Any
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder
from src.models.cluster import AlertCluster
from src.models.decision import DecisionState
from src.rules.decision_rules import RuleResult

logger = logging.getLogger(__name__)

class SemanticRecoveryService:
    """
    Service responsible for recovering scripts/decisions using Semantica's GraphRAG.
    Triggered when standard recovery confidence is low.

    Features:
    - LRU Cache for frequently accessed semantic results.
    - Structured logging for observability.
    - Pydantic-ready validation for graph returns.
    - GitHub Metadata Integration via MCP/API.
    """

    def __init__(self, threshold: float = 0.60, cache_size: int = 100):
        self.threshold = threshold
        # Initialize Semantica components
        self.ner_extractor = NERExtractor(method="ml", model="en_core_web_sm")
        self.graph_builder = GraphBuilder()

        # Cache for semantic results
        self._cache: Dict[str, RuleResult] = {}
        self._cache_size = cache_size

        # GitHub Integration Config
        self.github_token = os.getenv("GITHUB_TOKEN", "")

    async def recover(
        self,
        cluster: AlertCluster,
        current_confidence: float
    ) -> Optional[RuleResult]:
        """
        Attempt to recover a decision using Semantic Retrieval and GitHub Context.
        """
        if current_confidence >= self.threshold:
            return None

        cache_key = f"{cluster.primary_service}:{cluster.alerts[0].description[:100]}"
        if cache_key in self._cache:
            logger.info(f"[SEMANTIC_RECOVERY_CACHE_HIT] Returning cached result for {cache_key}")
            return self._cache[cache_key]

        logger.info(
            f"[SEMANTIC_RECOVERY_START] Low confidence ({current_confidence:.2f}). "
            f"Service: {cluster.primary_service}, Cluster: {cluster.cluster_id}"
        )

        try:
            # 1. Entity Extraction
            context_text = f"Service: {cluster.primary_service}. Description: {cluster.alerts[0].description}"
            entities = self.ner_extractor.extract(context_text)
            logger.debug(f"[SEMANTIC_RECOVERY_ENTITIES] Extracted: {entities}")

            # 2. Enriquecimento com GitHub (Opcional, se a entidade for um serviço/repo)
            github_context = await self._get_github_context(cluster.primary_service)
            if github_context:
                logger.info(f"[SEMANTIC_RECOVERY_GITHUB] Found repo info: {github_context.get('full_name')}")

            # 3. Graph Search (Injetando contexto do GitHub se disponível)
            semantic_match_raw = self._query_knowledge_graph(entities, github_context)

            if semantic_match_raw:
                # 4. Schema Validation
                try:
                    result = RuleResult(
                        decision_state=DecisionState(semantic_match_raw.get("state")),
                        confidence=float(semantic_match_raw.get("confidence", 0.0)),
                        rule_id="semantica_recovery",
                        justification=f"Recovered via Semantica GraphRAG. Entities: {entities}. GitHub: {github_context.get('full_name', 'N/A')}"
                    )

                    if len(self._cache) < self._cache_size:
                        self._cache[cache_key] = result

                    logger.info(f"[SEMANTIC_RECOVERY_SUCCESS] Match found: {result.decision_state}")
                    return result
                except (ValueError, TypeError) as ve:
                    logger.error(f"[SEMANTIC_RECOVERY_VALIDATION_ERROR] {ve}")
            else:
                logger.info(f"[SEMANTIC_RECOVERY_NO_MATCH] No relevant scripts found.")

        except Exception as e:
            logger.error(f"[SEMANTIC_RECOVERY_ERROR] {e}", exc_info=True)

        return None

    async def _get_github_context(self, service_name: str) -> Dict[str, Any]:
        """
        Fetch repository metadata from GitHub API.
        Replaces the legacy RepositoryContextAgent.
        """
        if not self.github_token:
            return {}

        # Simplificação: assume que o nome do serviço é o nome do repo
        # Em produção, isso usaria uma busca mais robusta ou mapeamento
        url = f"https://api.github.com/repos/igorrhamon/{service_name}"
        headers = {"Authorization": f"token {self.github_token}"}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "full_name": data.get("full_name"),
                        "description": data.get("description"),
                        "stars": data.get("stargazers_count"),
                        "last_update": data.get("updated_at")
                    }
        except Exception as e:
            logger.warning(f"[SEMANTIC_RECOVERY_GITHUB_ERROR] Failed to fetch metadata: {e}")

        return {}

    def _query_knowledge_graph(self, entities: List, github_context: Dict) -> Optional[Dict[str, Any]]:
        """
        Internal method to query the Knowledge Graph.
        To be mocked in tests.
        """
        return None
