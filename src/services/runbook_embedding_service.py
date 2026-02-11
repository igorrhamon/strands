"""
Runbook Embedding Service - Semantic Indexing of Operational Procedures
Processes Markdown runbooks and stores them in Qdrant for semantic retrieval.
"""

import os
import logging
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    MODEL_AVAILABLE = True
except ImportError:
    MODEL_AVAILABLE = False

logger = logging.getLogger(__name__)

class RunbookEmbeddingService:
    """
    Service responsible for:
    1. Loading Markdown runbooks from a configured path.
    2. Generating semantic embeddings for each procedure.
    3. Indexing them in Qdrant for RAG-based incident response.
    """
    
    COLLECTION_NAME = "runbooks"
    VECTOR_SIZE = 384 # Matches all-MiniLM-L6-v2
    
    def __init__(
        self,
        runbooks_path: Optional[str] = None,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333
    ):
        self.runbooks_path = runbooks_path or os.getenv("RUNBOOKS_PATH", "/home/ubuntu/strands/docs")
        self._qdrant_host = qdrant_host
        self._qdrant_port = qdrant_port
        self._client = None
        self._model = None
        
        if QDRANT_AVAILABLE:
            try:
                self._client = QdrantClient(host=self._qdrant_host, port=self._qdrant_port)
                self._ensure_collection()
            except Exception as e:
                logger.error(f"[RUNBOOK_SERVICE] Failed to connect to Qdrant: {e}")
        
        if MODEL_AVAILABLE:
            try:
                self._model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("[RUNBOOK_SERVICE] Loaded embedding model")
            except Exception as e:
                logger.error(f"[RUNBOOK_SERVICE] Failed to load model: {e}")

    def _ensure_collection(self):
        """Create Qdrant collection for runbooks if it doesn't exist."""
        if not self._client:
            return
        try:
            collections = self._client.get_collections().collections
            if not any(c.name == self.COLLECTION_NAME for c in collections):
                self._client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE)
                )
                logger.info(f"[RUNBOOK_SERVICE] Created collection: {self.COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"[RUNBOOK_SERVICE] Error ensuring collection: {e}")

    def index_runbooks(self) -> Dict[str, int]:
        """
        Scan the runbooks directory and index all Markdown files.
        """
        if not self._model or not self._client:
            return {"indexed": 0, "errors": 1, "message": "Model or Qdrant not available"}
            
        path = Path(self.runbooks_path)
        if not path.exists():
            logger.warning(f"[RUNBOOK_SERVICE] Path {self.runbooks_path} does not exist")
            return {"indexed": 0, "errors": 1}
            
        indexed_count = 0
        files = list(path.glob("**/*.md"))
        
        points = []
        for md_file in files:
            try:
                content = md_file.read_text(encoding="utf-8")
                if not content.strip():
                    continue
                    
                # Generate a unique ID based on file path
                file_id = hashlib.md5(str(md_file).encode()).hexdigest()
                
                # Generate embedding
                embedding = self._model.encode(content).tolist()
                
                points.append(PointStruct(
                    id=file_id,
                    vector=embedding,
                    payload={
                        "file_name": md_file.name,
                        "path": str(md_file),
                        "content": content[:1000], # Store a snippet
                        "full_content": content
                    }
                ))
                indexed_count += 1
            except Exception as e:
                logger.error(f"[RUNBOOK_SERVICE] Failed to index {md_file}: {e}")
                
        if points:
            self._client.upsert(collection_name=self.COLLECTION_NAME, points=points)
            
        logger.info(f"[RUNBOOK_SERVICE] Indexed {indexed_count} runbooks from {self.runbooks_path}")
        return {"indexed": indexed_count, "total_files": len(files)}

    def search_procedures(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant procedures based on an incident description.
        """
        if not self._model or not self._client:
            return []
            
        query_vector = self._model.encode(query).tolist()
        
        try:
            results = self._client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=limit
            )
            
            return [
                {
                    "score": res.score,
                    "file_name": res.payload.get("file_name"),
                    "content": res.payload.get("full_content"),
                    "path": res.payload.get("path")
                }
                for res in results
            ]
        except Exception as e:
            logger.error(f"[RUNBOOK_SERVICE] Search failed: {e}")
            return []
