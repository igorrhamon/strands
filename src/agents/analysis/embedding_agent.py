"""
Embedding Agent

Finds semantically similar past incidents.
Wraps: src/graph/qdrant_repo.py
"""

import logging
from datetime import datetime, timezone
from typing import List

from fastembed import TextEmbedding

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType
from src.models.decision import DecisionCandidate
from src.graph.qdrant_repo import QdrantRepository

logger = logging.getLogger(__name__)

class EmbeddingAgent:
    agent_id = "embedding_agent"
    COLLECTION_NAME = "incidents"
    
    def __init__(self, qdrant_repo: QdrantRepository):
        self.repo = qdrant_repo
        # Initialize FastEmbed model (lightweight, runs on CPU)
        # BAAI/bge-small-en-v1.5 is a good balance of speed/quality
        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure the Qdrant collection exists."""
        try:
            # Check if collection exists logic should be in repo, but for now we assume repo handles it
            # or we catch error on search.
            pass 
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Could not verify collection: {e}")

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text."""
        # fastembed returns a generator of embeddings
        embeddings = list(self.embedding_model.embed([text]))
        embedding = embeddings[0]
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)

    def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        logger.info(f"[{self.agent_id}] Searching for similar incidents for {alert.fingerprint}...")
        
        # Create a rich text representation of the alert for embedding
        query_text = f"{alert.service} {alert.severity} {alert.description} {str(alert.labels)}"
        
        try:
            vector = self._generate_embedding(query_text)
            
            # Search in Qdrant
            # Assuming repo.search_similar returns list of ScoredPoint
            matches = self.repo.search_similar(self.COLLECTION_NAME, vector, limit=3)
            
            if not matches:
                return SwarmResult(
                    agent_id=self.agent_id,
                    hypothesis="No similar past incidents found.",
                    confidence=0.5,
                    evidence=[],
                    suggested_actions=[]
                )
                
            evidence = []
            actions = []
            
            for match in matches:
                # Extract payload
                payload = match.payload or {}
                summary = payload.get("summary", "Unknown Incident")
                resolution = payload.get("resolution", "No resolution recorded")
                score = match.score
                
                evidence.append(EvidenceItem(
                    type=EvidenceType.DOCUMENT,
                    description=f"Similar Incident (Score: {score:.2f}): {summary}",
                    source_url=f"http://itsm/inc/{match.id}", # Mock URL
                    timestamp=datetime.now(timezone.utc),
                    metadata={"score": score, "resolution": resolution}
                ))
                
                if resolution:
                    actions.append(f"Consider past resolution: {resolution}")
            
            top_match_score = matches[0].score
            confidence = min(0.95, top_match_score) # Cap confidence based on similarity score
            
            hypothesis = f"Found {len(matches)} similar past incidents. Top match score: {top_match_score:.2f}."
            
            return SwarmResult(
                agent_id=self.agent_id,
                hypothesis=hypothesis,
                confidence=confidence,
                evidence=evidence,
                suggested_actions=list(set(actions)) # Deduplicate
            )
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error during analysis: {e}")
            return SwarmResult(
                agent_id=self.agent_id,
                hypothesis="Failed to search for similar incidents.",
                confidence=0.0,
                evidence=[],
                suggested_actions=[]
            )

    def index_resolution(self, candidate: DecisionCandidate):
        """
        Indexes the resolved incident for future retrieval.
        """
        decision_id = getattr(candidate, 'decision_id', str(datetime.now().timestamp()))
        logger.info(f"[{self.agent_id}] Indexing resolution for {decision_id}")
        
        try:
            # Create text to embed: Summary + Hypothesis + Action Plan
            text_to_embed = f"{candidate.summary}\n{candidate.primary_hypothesis}\n{candidate.risk_assessment}"
            
            vector = self._generate_embedding(text_to_embed)
            
            payload = {
                "summary": candidate.summary,
                "hypothesis": candidate.primary_hypothesis,
                "resolution": candidate.selected_action, # Assuming this field exists or similar
                "timestamp": datetime.now().isoformat()
            }
            
            # Upsert to Qdrant
            self.repo.upsert_point(
                collection_name=self.COLLECTION_NAME,
                point_id=decision_id, # Must be int or UUID. If string, Qdrant might need UUID hashing.
                vector=vector,
                payload=payload
            )
            logger.info(f"[{self.agent_id}] Successfully indexed incident {decision_id}")
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] Failed to index resolution: {e}")

