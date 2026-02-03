"""
Qdrant Repository - Vector Database Access Layer

Handles storage and retrieval of vector embeddings for semantic search.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)

class QdrantRepository:
    """Repository for interacting with Qdrant vector database."""

    def __init__(self):
        self.url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = os.getenv("QDRANT_API_KEY", None)
        self.client: Optional[QdrantClient] = None
        
    def connect(self):
        """Establish connection to Qdrant."""
        if not self.client:
            try:
                self.client = QdrantClient(url=self.url, api_key=self.api_key)
                logger.info("Connected to Qdrant at %s", self.url)
            except Exception as e:
                logger.error("Failed to connect to Qdrant: %s", e)
                raise

    def ensure_collection(self, collection_name: str, vector_size: int = 1536):
        """Ensure a collection exists with the given configuration."""
        if not self.client:
            self.connect()
            
        exists = self.client.collection_exists(collection_name)
        if not exists:
            logger.info("Creating collection %s with size %d", collection_name, vector_size)
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )

    def upsert_embedding(self, collection_name: str, idx: str, embedding: List[float], payload: Dict[str, Any]):
        """Upsert a single embedding vector."""
        if not self.client:
            self.connect()
            
        self.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=idx,
                    vector=embedding,
                    payload=payload
                )
            ]
        )

    def search_similar(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[Any]:
        """Search for similar vectors."""
        if not self.client:
            self.connect()
            
        return self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
