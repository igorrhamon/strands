"""
Graph Agent - Knowledge Graph and RAG for Decision Support

Manages semantic search over past decisions and maintains
a knowledge graph of alert-decision relationships.

Constitution Principle III: Provide semantic evidence from similar cases.
"""

import logging
import os
from typing import TYPE_CHECKING, List, Optional, Any
from uuid import UUID
from datetime import datetime, timezone

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    # Type stubs for when Qdrant is not available
    if not TYPE_CHECKING:
        QdrantClient = None  # type: ignore
        Distance = None  # type: ignore
        VectorParams = None  # type: ignore
        PointStruct = None  # type: ignore

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    if not TYPE_CHECKING:
        GraphDatabase = None  # type: ignore

if TYPE_CHECKING:
    from qdrant_client import QdrantClient as QdrantClientType
    from neo4j import Driver as Neo4jDriver
else:
    QdrantClientType = Any
    Neo4jDriver = Any

from src.models.decision import Decision, SemanticEvidence
from src.models.cluster import AlertCluster

logger = logging.getLogger(__name__)


class GraphAgent:
    """
    Agent responsible for:
    1. Storing confirmed decisions in vector database (Qdrant)
    2. Retrieving semantically similar past decisions (RAG)
    3. Building knowledge graph of alert patterns (Neo4j)
    
    This agent enhances decision-making with historical context.
    """
    
    AGENT_NAME = "GraphAgent"
    COLLECTION_NAME = "alert_decisions"
    VECTOR_SIZE = 384  # Default for sentence-transformers/all-MiniLM-L6-v2
    
    def __init__(
        self,
        qdrant_client: Optional[QdrantClientType] = None,
        neo4j_driver: Optional[Neo4jDriver] = None,
        collection_name: str = COLLECTION_NAME,
        enable_qdrant: bool = False,
        enable_neo4j: bool = False,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """
        Initialize graph agent.
        """
        self._collection_name = collection_name
        self.enable_qdrant = enable_qdrant and QDRANT_AVAILABLE
        self.enable_neo4j = enable_neo4j and NEO4J_AVAILABLE
        self._client = qdrant_client
        self._neo4j_driver = neo4j_driver
        
        # Use environment variables for security as suggested by ChatGPT
        neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = neo4j_user or os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "strads123")
        
        # Initialize embedding model
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info(f"[{self.AGENT_NAME}] Initialized real embedding model: all-MiniLM-L6-v2")
        except Exception as e:
            logger.warning(f"[{self.AGENT_NAME}] Failed to load embedding model, falling back to dummy: {e}")
            self._model = None

        # In-memory fallback for offline mode
        self._memory_store: List[dict] = []
        
        # Initialize Qdrant
        if self.enable_qdrant and not self._client:
            if not QDRANT_AVAILABLE:
                logger.warning(f"[{self.AGENT_NAME}] Qdrant not available (package not installed)")
                self.enable_qdrant = False
            else:
                try:
                    self._client = QdrantClient(host="localhost", port=6333)  # type: ignore
                    self._ensure_collection()
                    logger.info(f"[{self.AGENT_NAME}] Connected to Qdrant at localhost:6333")
                except Exception as e:
                    logger.warning(f"[{self.AGENT_NAME}] Failed to connect to Qdrant: {e}")
                    self.enable_qdrant = False
        
        # Initialize Neo4j
        if self.enable_neo4j and not self._neo4j_driver:
            if not NEO4J_AVAILABLE:
                logger.warning(f"[{self.AGENT_NAME}] Neo4j not available (package not installed)")
                self.enable_neo4j = False
            else:
                try:
                    self._neo4j_driver = GraphDatabase.driver(  # type: ignore
                        neo4j_uri,
                        auth=(neo4j_user, neo4j_password)
                    )
                    # Test connection
                    self._neo4j_driver.verify_connectivity()
                    self._ensure_neo4j_constraints()
                    logger.info(f"[{self.AGENT_NAME}] Connected to Neo4j at {neo4j_uri}")
                except Exception as e:
                    logger.warning(f"[{self.AGENT_NAME}] Failed to connect to Neo4j: {e}")
                    self.enable_neo4j = False
        
        backend = []
        if self.enable_qdrant:
            backend.append("Qdrant")
        if self.enable_neo4j:
            backend.append("Neo4j")
        if not backend:
            backend.append("memory-only")
            
        logger.info(f"[{self.AGENT_NAME}] Running with: {', '.join(backend)}")
    
    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        if not self._client or not QDRANT_AVAILABLE:
            return
        
        try:
            collections = self._client.get_collections().collections
            if not any(c.name == self._collection_name for c in collections):
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(  # type: ignore
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE  # type: ignore
                    )
                )
                logger.info(f"[{self.AGENT_NAME}] Created collection: {self._collection_name}")
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Failed to ensure collection: {e}")
    
    def _ensure_neo4j_constraints(self):
        """Create Neo4j constraints and indexes."""
        if not self._neo4j_driver or not NEO4J_AVAILABLE:
            return
        
        try:
            with self._neo4j_driver.session() as session:
                # Create unique constraint on Decision ID
                session.run("""
                    CREATE CONSTRAINT decision_id_unique IF NOT EXISTS
                    FOR (d:Decision) REQUIRE d.id IS UNIQUE
                """)
                
                # Create unique constraint on Service name
                session.run("""
                    CREATE CONSTRAINT service_name_unique IF NOT EXISTS
                    FOR (s:Service) REQUIRE s.name IS UNIQUE
                """)
                
                # Create index on Decision state
                session.run("""
                    CREATE INDEX decision_state_idx IF NOT EXISTS
                    FOR (d:Decision) ON (d.state)
                """)
                
                # Create index on timestamp
                session.run("""
                    CREATE INDEX decision_created_idx IF NOT EXISTS
                    FOR (d:Decision) ON (d.created_at)
                """)
                
                logger.info(f"[{self.AGENT_NAME}] Neo4j constraints and indexes ensured")
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Failed to ensure Neo4j constraints: {e}")
    
    def _store_in_neo4j(self, decision: Decision, cluster: AlertCluster):
        """Store decision and relationships in Neo4j knowledge graph."""
        if not self._neo4j_driver or not self.enable_neo4j:
            return
        
        try:
            with self._neo4j_driver.session() as session:
                # Create Decision node and Service node with relationships
                session.run("""
                    MERGE (s:Service {name: $service})
                    ON CREATE SET 
                        s.created_at = datetime($now)
                    
                    CREATE (d:Decision {
                        id: $decision_id,
                        state: $state,
                        confidence: $confidence,
                        justification: $justification,
                        llm_used: $llm_used,
                        created_at: datetime($created_at),
                        validated_by: $validated_by
                    })
                    
                    CREATE (a:AlertCluster {
                        id: $cluster_id,
                        severity: $severity,
                        alert_count: $alert_count,
                        correlation_score: $correlation_score
                    })
                    
                    CREATE (d)-[:FOR_SERVICE]->(s)
                    CREATE (d)-[:BASED_ON]->(a)
                    
                    WITH d
                    UNWIND $rules AS rule_name
                    MERGE (r:Rule {name: rule_name})
                    CREATE (d)-[:APPLIED_RULE]->(r)
                """, {
                    "service": cluster.primary_service,
                    "decision_id": str(decision.decision_id),
                    "state": decision.decision_state.value,
                    "confidence": decision.confidence,
                    "justification": decision.justification,
                    "llm_used": decision.llm_contribution,
                    "created_at": decision.created_at.isoformat(),
                    "validated_by": decision.validated_by,
                    "cluster_id": str(cluster.cluster_id),
                    "severity": cluster.primary_severity,
                    "alert_count": cluster.alert_count,
                    "correlation_score": cluster.correlation_score,
                    "rules": decision.rules_applied,
                    "now": datetime.now(timezone.utc).isoformat()
                })
                
                logger.debug(f"[{self.AGENT_NAME}] Stored decision {decision.decision_id} in Neo4j")
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Failed to store in Neo4j: {e}")
    
    def store_decision(
        self,
        decision: Decision,
        cluster: AlertCluster,
        embedding: Optional[List[float]] = None
    ) -> bool:
        """
        Store a confirmed decision for future retrieval.
        """
        if not decision.is_confirmed:
            logger.warning(f"[{self.AGENT_NAME}] Skipping unconfirmed decision {decision.decision_id}")
            return False
            
        # Generate summary and embedding if not provided
        summary = self._generate_summary(decision, cluster)
        if not embedding:
            embedding = self._generate_embedding(summary)
            
        # 1. Store in Neo4j (Knowledge Graph)
        self._store_in_neo4j(decision, cluster)
        
        # 2. Store in Qdrant (Vector Search)
        if self.enable_qdrant and self._client:
            try:
                self._client.upsert(
                    collection_name=self._collection_name,
                    points=[
                        PointStruct(
                            id=str(decision.decision_id),
                            vector=embedding,
                            payload={
                                "service": cluster.primary_service,
                                "severity": cluster.primary_severity,
                                "decision_state": decision.decision_state.value,
                                "confidence": decision.confidence,
                                "summary": summary,
                                "created_at": decision.created_at.isoformat()
                            }
                        )
                    ]
                )
                logger.debug(f"[{self.AGENT_NAME}] Stored decision {decision.decision_id} in Qdrant")
            except Exception as e:
                logger.error(f"[{self.AGENT_NAME}] Failed to store in Qdrant: {e}")
        
        # 3. Always store in memory as fallback
        self._memory_store.append({
            "id": str(decision.decision_id),
            "vector": embedding,
            "payload": {
                "service": cluster.primary_service,
                "severity": cluster.primary_severity,
                "decision_state": decision.decision_state.value,
                "confidence": decision.confidence,
                "summary": summary,
                "created_at": decision.created_at.isoformat()
            }
        })
        
        return True

    def find_similar_decisions(
        self,
        cluster: AlertCluster,
        top_k: int = 3,
        min_similarity: float = 0.7
    ) -> List[SemanticEvidence]:
        """
        Find past decisions semantically similar to the current cluster.
        """
        # Generate query text from cluster context
        symptoms = [a.description for a in cluster.alerts[:3]]
        query_text = f"Service: {cluster.primary_service} | Severity: {cluster.primary_severity} | Symptoms: {' | '.join(symptoms)}"
        query_embedding = self._generate_embedding(query_text)
        
        # Search in Qdrant if enabled
        if self.enable_qdrant and self._client:
            try:
                results = self._client.search(
                    collection_name=self._collection_name,
                    query_vector=query_embedding,
                    limit=top_k,
                    score_threshold=min_similarity
                )
                
                evidence = [
                    SemanticEvidence(
                        decision_id=UUID(str(res.id)),
                        similarity=res.score,
                        summary=res.payload.get("summary", ""),
                        metadata=res.payload
                    )
                    for res in results
                ]
                
                logger.info(f"[{self.AGENT_NAME}] Found {len(evidence)} similar decisions in Qdrant")
                return evidence
            except Exception as e:
                logger.error(f"[{self.AGENT_NAME}] Failed to search Qdrant: {e}")
        
        # Fallback: search in memory (naive cosine similarity)
        evidence = self._search_memory(query_embedding, top_k, min_similarity)
        logger.debug(f"[{self.AGENT_NAME}] Found {len(evidence)} similar decisions in memory")
        return evidence

    def _generate_summary(self, decision: Decision, cluster: AlertCluster) -> str:
        """
        Generate a rich semantic summary of the decision for embedding.
        Includes symptoms, metrics, and context as suggested by ChatGPT.
        """
        # Extract symptoms from alerts
        symptoms = [a.description for a in cluster.alerts[:3]]
        
        # Extract relevant metrics from labels if available
        metrics = []
        for alert in cluster.alerts:
            for k, v in alert.labels.items():
                if any(m in k.lower() for m in ["cpu", "memory", "error", "latency", "rate", "count"]):
                    metrics.append(f"{k}={v}")
        
        summary_parts = [
            f"Service: {cluster.primary_service}",
            f"Severity: {cluster.primary_severity}",
            f"Symptoms: {' | '.join(symptoms)}",
            f"Metrics: {', '.join(list(set(metrics))[:5])}",
            f"Decision: {decision.decision_state.value}",
            f"Confidence: {decision.confidence:.2f}",
            f"Rules: {', '.join(decision.rules_applied)}",
            f"Justification: {decision.justification}"
        ]
        return " | ".join(summary_parts)
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate real embedding for text using sentence-transformers.
        """
        if hasattr(self, '_model') and self._model:
            try:
                embedding = self._model.encode(text)
                return embedding.tolist()
            except Exception as e:
                logger.error(f"[{self.AGENT_NAME}] Embedding generation failed: {e}")
        
        # Fallback to dummy embedding if model is not available
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        import random
        random.seed(hash_val)
        return [random.random() for _ in range(self.VECTOR_SIZE)]

    def _search_memory(
        self,
        query_embedding: List[float],
        top_k: int,
        min_similarity: float
    ) -> List[SemanticEvidence]:
        """Search in-memory store using cosine similarity."""
        if not self._memory_store:
            return []
        
        import math
        
        def cosine_similarity(v1: List[float], v2: List[float]) -> float:
            dot_product = sum(a * b for a, b in zip(v1, v2))
            mag1 = math.sqrt(sum(a * a for a in v1))
            mag2 = math.sqrt(sum(a * a for a in v2))
            if mag1 == 0 or mag2 == 0:
                return 0
            return dot_product / (mag1 * mag2)
            
        results = []
        for item in self._memory_store:
            sim = cosine_similarity(query_embedding, item["vector"])
            if sim >= min_similarity:
                results.append(
                    SemanticEvidence(
                        decision_id=UUID(item["id"]),
                        similarity=sim,
                        summary=item["payload"].get("summary", ""),
                        metadata=item["payload"]
                    )
                )
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]

    def get_service_history(self, service_name: str, limit: int = 10) -> List[dict]:
        """Retrieve recent decisions for a service from Neo4j."""
        if not self.enable_neo4j or not self._neo4j_driver:
            return []
        
        try:
            with self._neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (s:Service {name: $service})<-[:FOR_SERVICE]-(d:Decision)
                    MATCH (d)-[:APPLIED_RULE]->(r:Rule)
                    RETURN d.id as id, 
                           d.state as state, 
                           d.confidence as confidence, 
                           d.justification as justification,
                           d.created_at as created_at,
                           collect(r.name) as rules
                    ORDER BY d.created_at DESC
                    LIMIT $limit
                """, {"service": service_name, "limit": limit})
                
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Failed to get service history: {e}")
            return []
    
    def get_common_patterns(self, min_occurrences: int = 3) -> List[dict]:
        """Find common decision patterns from Neo4j."""
        if not self.enable_neo4j or not self._neo4j_driver:
            return []
        
        try:
            with self._neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (d:Decision)-[:FOR_SERVICE]->(s:Service)
                    MATCH (d)-[:APPLIED_RULE]->(r:Rule)
                    WITH s.name as service, r.name as rule, d.state as state, count(*) as occurrences
                    WHERE occurrences >= $min_occurrences
                    RETURN service, rule, state, occurrences
                    ORDER BY occurrences DESC
                    LIMIT 20
                """, {"min_occurrences": min_occurrences})
                
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Failed to get common patterns: {e}")
            return []
    
    def close(self):
        """Close connections to databases."""
        if self._neo4j_driver:
            self._neo4j_driver.close()
            logger.info(f"[{self.AGENT_NAME}] Closed Neo4j connection")
