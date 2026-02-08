import logging
from typing import Optional, List
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
    """
    
    def __init__(self, threshold: float = 0.60):
        self.threshold = threshold
        # Initialize Semantica components
        self.ner_extractor = NERExtractor(method="ml", model="en_core_web_sm")
        self.graph_builder = GraphBuilder()
        
    async def recover(
        self, 
        cluster: AlertCluster, 
        current_confidence: float
    ) -> Optional[RuleResult]:
        """
        Attempt to recover a decision using Semantic Retrieval if confidence is low.
        """
        if current_confidence >= self.threshold:
            logger.info(f"Confidence {current_confidence} is above threshold {self.threshold}. Skipping semantic recovery.")
            return None

        logger.info(f"Low confidence ({current_confidence}). Starting Semantic Recovery via Semantica.")
        
        try:
            # 1. Entity Extraction (Mapeamento de Entidades)
            # We use the cluster description and service for context
            context_text = f"Service: {cluster.primary_service}. Description: {cluster.alerts[0].description}"
            entities = self.ner_extractor.extract(context_text)
            
            # 2. Graph Search (Simulated for now as we need a pre-built KG or mock)
            # In a real scenario, we would query the GraphStore
            # For this implementation, we'll follow the TDD approach and mock this in tests
            
            # Simulated search result from Knowledge Graph
            semantic_match = self._query_knowledge_graph(entities)
            
            if semantic_match:
                return RuleResult(
                    decision_state=semantic_match["state"],
                    confidence=semantic_match["confidence"],
                    rule_id="semantica_recovery",
                    justification=f"Recovered via Semantica GraphRAG. Entities: {entities}"
                )
                
        except Exception as e:
            logger.error(f"Error during Semantic Recovery: {e}")
            
        return None

    def _query_knowledge_graph(self, entities: List) -> Optional[dict]:
        """
        Internal method to query the Knowledge Graph.
        To be mocked in tests.
        """
        # This would normally use semantica.graph_store
        return None
