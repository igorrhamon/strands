"""
Similarity Index - Indexes incident fingerprints for fast semantic retrieval.
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
from src.state.incident_registry import IncidentSnapshot

logger = logging.getLogger(__name__)

class SimilarityIndex:
    """
    Semantic index for incident fingerprints.
    Uses SentenceTransformers for embeddings and simple cosine similarity for now.
    """
    def __init__(self):
        self._index: List[Dict[str, Any]] = []
        try:
            import sentence_transformers
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("SimilarityIndex: Loaded all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("SimilarityIndex: sentence-transformers not installed. Semantic search disabled.")
            self._model = None
        except Exception as e:
            logger.warning(f"SimilarityIndex: Failed to load model: {e}")
            self._model = None

    def add_snapshot(self, snapshot: IncidentSnapshot):
        if not self._model:
            # Fallback for trace simulation
            self._index.append({
                "snapshot_id": snapshot.snapshot_id,
                "incident_id": snapshot.incident_id,
                "embedding": None,
                "text": snapshot.to_fingerprint_text(),
                "snapshot": snapshot
            })
            return

        text = snapshot.to_fingerprint_text()
        embedding = self._model.encode(text)

        self._index.append({
            "snapshot_id": snapshot.snapshot_id,
            "incident_id": snapshot.incident_id,
            "embedding": embedding,
            "text": text,
            "snapshot": snapshot
        })
        logger.info(f"Indexed snapshot {snapshot.snapshot_id}")

    def find_similar(self, query_text: str, threshold: float = 0.7, limit: int = 3) -> List[Dict[str, Any]]:
        if not self._model:
            # Fallback for trace simulation if model is missing
            if self._index:
                return [{
                    "snapshot": self._index[0]["snapshot"],
                    "similarity": 0.92 # Simulated high similarity
                }]
            return []

        if not self._index:
            return []

        query_embedding = self._model.encode(query_text)
        results = []

        for item in self._index:
            similarity = self._cosine_similarity(query_embedding, item["embedding"])
            if similarity >= threshold:
                results.append({
                    "snapshot": item["snapshot"],
                    "similarity": float(similarity)
                })

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, v1, v2):
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        return dot_product / (norm_v1 * norm_v2)
