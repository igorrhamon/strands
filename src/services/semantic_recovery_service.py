import logging
import functools
from typing import Optional, List, Dict, Any
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder
from src.models.cluster import AlertCluster
from src.models.decision import DecisionState, SemanticEvidence
from src.rules.decision_rules import RuleResult

logger = logging.getLogger(__name__)

class SemanticRecoveryService:
    """
    Service responsible for recovering scripts/decisions using Semantica's GraphRAG.
    Triggered when standard recovery confidence is low.
    
    Includes:
    - LRU Cache for frequently accessed semantic results.
    - Structured logging for observability.
    - Pydantic-ready validation for graph returns.
    """
    
    def __init__(self, threshold: float = 0.60, cache_size: int = 100):
        self.threshold = threshold
        # Initialize Semantica components
        self.ner_extractor = NERExtractor(method="ml", model="en_core_web_sm")
        self.graph_builder = GraphBuilder()
        
        # Simple in-memory cache for demonstration
        # In production, this could be Redis or a more robust async cache
        self._cache: Dict[str, RuleResult] = {}
        self._cache_size = cache_size

    async def recover(
        self, 
        cluster: AlertCluster, 
        current_confidence: float
    ) -> Optional[RuleResult]:
        """
        Attempt to recover a decision using Semantic Retrieval if confidence is low.
        """
        if current_confidence >= self.threshold:
            logger.debug(
                f"[RECOVERY_SKIP] Confidence {current_confidence:.2f} >= {self.threshold}. "
                f"Cluster: {cluster.cluster_id}"
            )
            return None

        # Cache key based on service and first alert description
        cache_key = f"{cluster.primary_service}:{cluster.alerts[0].description[:100]}"
        if cache_key in self._cache:
            logger.info(f"[SEMANTIC_RECOVERY_CACHE_HIT] Returning cached result for {cache_key}")
            return self._cache[cache_key]

        logger.info(
            f"[SEMANTIC_RECOVERY_START] Low confidence ({current_confidence:.2f}). "
            f"Service: {cluster.primary_service}, Cluster: {cluster.cluster_id}"
        )
        
        try:
            # 1. Entity Extraction (Mapeamento de Entidades)
            context_text = f"Service: {cluster.primary_service}. Description: {cluster.alerts[0].description}"
            entities = self.ner_extractor.extract(context_text)
            
            logger.debug(f"[SEMANTIC_RECOVERY_ENTITIES] Extracted: {entities}")
            
            # 2. Graph Search
            semantic_match_raw = self._query_knowledge_graph(entities)
            
            if semantic_match_raw:
                # 3. Schema Validation & Transformation
                # RuleResult is a Pydantic model, so we use it for validation
                try:
                    result = RuleResult(
                        decision_state=DecisionState(semantic_match_raw.get("state")),
                        confidence=float(semantic_match_raw.get("confidence", 0.0)),
                        rule_id="semantica_recovery",
                        justification=f"Recovered via Semantica GraphRAG. Entities: {entities}"
                    )
                    
                    # Update cache
                    if len(self._cache) < self._cache_size:
                        self._cache[cache_key] = result
                        
                    logger.info(
                        f"[SEMANTIC_RECOVERY_SUCCESS] Match found. "
                        f"State: {result.decision_state}, Confidence: {result.confidence:.2f}"
                    )
                    return result
                except (ValueError, TypeError) as ve:
                    logger.error(f"[SEMANTIC_RECOVERY_VALIDATION_ERROR] Malformed graph return: {ve}")
            else:
                logger.info(f"[SEMANTIC_RECOVERY_NO_MATCH] No relevant scripts found in Knowledge Graph.")
                
        except Exception as e:
            logger.error(f"[SEMANTIC_RECOVERY_ERROR] Unexpected failure: {e}", exc_info=True)
            
        return None

    def _query_knowledge_graph(self, entities: List) -> Optional[Dict[str, Any]]:
        """
        Internal method to query the Knowledge Graph.
        To be mocked in tests.
        """
        # This would normally use semantica.graph_store
        return None
