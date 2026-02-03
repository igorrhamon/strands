"""
Qdrant Client - Vector Database Connection Management

Handles connection to Qdrant (Docker or Cloud), collection management,
and low-level vector operations.

Research Decision: Use Docker deployment with cosine distance (see research.md).
"""

import logging
from typing import Optional
from uuid import UUID

from qdrant_client import QdrantClient as QdrantSDKClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)

logger = logging.getLogger(__name__)


# Default configuration (from research.md)
DEFAULT_QDRANT_HOST = "localhost"
DEFAULT_QDRANT_PORT = 6333
DEFAULT_COLLECTION_NAME = "alert_decisions"
VECTOR_DIM = 384  # text-embedding-3-small


class QdrantConnectionError(Exception):
    """Raised when unable to connect to Qdrant."""
    pass


class QdrantClientWrapper:
    """
    Wrapper around Qdrant SDK for alert decision embeddings.
    
    Handles:
    - Connection management
    - Collection creation with 384-dim vectors
    - CRUD operations for embeddings
    """
    
    def __init__(
        self,
        host: str = DEFAULT_QDRANT_HOST,
        port: int = DEFAULT_QDRANT_PORT,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        timeout: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.timeout = timeout
        self._client: Optional[QdrantSDKClient] = None
    
    def connect(self) -> "QdrantClientWrapper":
        """
        Establish connection to Qdrant.
        
        Raises:
            QdrantConnectionError: If connection fails.
        """
        try:
            self._client = QdrantSDKClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            )
            # Verify connection by checking collections
            self._client.get_collections()
            logger.info(f"Connected to Qdrant at {self.host}:{self.port}")
            return self
        except Exception as e:
            raise QdrantConnectionError(f"Failed to connect to Qdrant: {e}") from e
    
    def ensure_collection(self) -> None:
        """
        Create collection if it doesn't exist.
        
        Uses 384-dim vectors with Cosine distance (per research.md).
        """
        if not self._client:
            raise QdrantConnectionError("Not connected to Qdrant")
        
        collections = self._client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=VECTOR_DIM,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created collection '{self.collection_name}' with {VECTOR_DIM} dimensions")
        else:
            logger.debug(f"Collection '{self.collection_name}' already exists")
    
    def upsert_point(
        self,
        point_id: UUID,
        vector: list[float],
        payload: dict,
    ) -> None:
        """
        Insert or update a single embedding point.
        
        Args:
            point_id: Unique identifier for the point.
            vector: 384-dimensional embedding vector.
            payload: Metadata for filtering (service, severity, etc.).
        """
        if not self._client:
            raise QdrantConnectionError("Not connected to Qdrant")
        
        if len(vector) != VECTOR_DIM:
            raise ValueError(f"Expected {VECTOR_DIM} dimensions, got {len(vector)}")
        
        point = PointStruct(
            id=str(point_id),
            vector=vector,
            payload=payload,
        )
        
        self._client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )
        logger.debug(f"Upserted point {point_id}")
    
    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float = 0.75,
        service_filter: Optional[str] = None,
        severity_filter: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Search for similar embeddings with optional filtering.
        
        Args:
            query_vector: 384-dimensional query embedding.
            top_k: Maximum number of results to return.
            score_threshold: Minimum similarity score (cosine).
            service_filter: Filter by specific service name.
            severity_filter: Filter by severity levels.
        
        Returns:
            List of matched points with scores and payloads.
        """
        if not self._client:
            raise QdrantConnectionError("Not connected to Qdrant")
        
        # Build filter
        filter_conditions = []
        if service_filter:
            filter_conditions.append(
                FieldCondition(key="service", match=MatchValue(value=service_filter))
            )
        if severity_filter:
            filter_conditions.append(
                FieldCondition(key="severity", match=MatchAny(any=severity_filter))
            )
        
        query_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        results = self._client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]
    
    def delete_point(self, point_id: UUID) -> None:
        """Delete a single point by ID."""
        if not self._client:
            raise QdrantConnectionError("Not connected to Qdrant")
        
        self._client.delete(
            collection_name=self.collection_name,
            points_selector=[str(point_id)],
        )
        logger.debug(f"Deleted point {point_id}")
    
    def count_points(self) -> int:
        """Return the number of points in the collection."""
        if not self._client:
            raise QdrantConnectionError("Not connected to Qdrant")
        
        collection_info = self._client.get_collection(self.collection_name)
        return collection_info.points_count or 0
    
    def close(self) -> None:
        """Close the connection to Qdrant."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Disconnected from Qdrant")
