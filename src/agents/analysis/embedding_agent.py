"""
Embedding Agent

Finds semantically similar past incidents.
Wraps: src/graph/qdrant_repo.py
"""

import logging
from datetime import datetime, timezone

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType
from src.models.decision import DecisionCandidate
from src.graph.qdrant_repo import QdrantRepository
from src.tools.embedding_client import EmbeddingClient
from uuid import UUID

logger = logging.getLogger(__name__)

class EmbeddingAgent:
    agent_id = "embedding_agent"
    
    def __init__(self, qdrant_repo: QdrantRepository):
        self.repo = qdrant_repo

    def analyze(self, _alert: NormalizedAlert) -> SwarmResult:
        logger.info(f"[{self.agent_id}] Searching for similar incidents...")

        # Generate embedding for the alert description
        embedder = EmbeddingClient()
        try:
            query_vector = embedder.embed(_alert.description)
        except Exception as e:
            logger.exception("Embedding generation failed")
            # Return a SwarmResult with low confidence and error evidence
            return SwarmResult(
                agent_id=self.agent_id,
                hypothesis="Failed to generate embedding",
                confidence=0.0,
                evidence=[
                    EvidenceItem(
                        type=EvidenceType.DOCUMENT,
                        description=f"Embedding error: {str(e)}",
                        source_url="",
                        timestamp=datetime.now(timezone.utc)
                    )
                ],
                suggested_actions=[]
            )

        # Query Qdrant for similar incidents
        try:
            raw_matches = self.repo.search_similar("incidents", query_vector)
        except Exception:
            logger.exception("Qdrant search failed")
            raw_matches = []

        # Build hypothesis & evidence from matches
        if raw_matches:
            top = raw_matches[0]
            # qdrant_client returns objects with 'payload' and 'score' or may be models.PointStruct
            score = getattr(top, "score", None) or (top.get("score") if isinstance(top, dict) else None)
            payload = getattr(top, "payload", None) or (top.get("payload") if isinstance(top, dict) else {})

            hypothesis = f"Similar incident found: {payload.get('source_text', 'unknown')}"
            confidence = float(score) if score is not None else 0.6
            evidence = [
                EvidenceItem(
                    type=EvidenceType.DOCUMENT,
                    description=payload.get("source_text", "Similar incident"),
                    source_url=payload.get("source_url", ""),
                    timestamp=datetime.now(timezone.utc)
                )
            ]
        else:
            hypothesis = "No similar incidents found"
            confidence = 0.15
            evidence = []

        return SwarmResult(
            agent_id=self.agent_id,
            hypothesis=hypothesis,
            confidence=confidence,
            evidence=evidence,
            suggested_actions=[]
        )

    def index_resolution(self, _candidate: DecisionCandidate):
        """
        Indexes the resolved incident for future retrieval.
        T028: Implement Vector Indexing
        """
        cid = getattr(_candidate, 'decision_id', None)
        logger.info(f"[{self.agent_id}] Indexing resolution for {getattr(_candidate, 'decision_id', '<unknown>')}")
        if cid is None:
            logger.error("No decision_id on DecisionCandidate; skipping indexing")
            return

        # Build text to embed
        text = f"{_candidate.summary}\n{_candidate.primary_hypothesis}"

        embedder = EmbeddingClient()
        try:
            vector = embedder.embed(text)
        except Exception:
            logger.exception("Failed to generate embedding for resolution; skipping upsert")
            return

        payload = {
            "source_decision_id": str(cid),
            "source_text": text,
            "service": getattr(_candidate, 'alert_reference', 'unknown'),
            "severity": getattr(_candidate, 'severity', 'info') if hasattr(_candidate, 'severity') else 'info',
            "rules_applied": getattr(_candidate, 'supporting_evidence', []),
            "human_validator": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Ensure collection exists and upsert the vector
            self.repo.ensure_collection("incidents", vector_size=len(vector))
            self.repo.upsert_embedding("incidents", str(cid), vector, payload)
            logger.info("Indexed decision %s into Qdrant", cid)
        except Exception:
            logger.exception("Failed to upsert embedding into Qdrant")

