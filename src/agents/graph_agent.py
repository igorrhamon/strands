"""
Graph Agent - Knowledge Graph and RAG for Decision Support

Manages semantic search over past decisions and maintains
a knowledge graph of alert-decision relationships.

Constitution Principle III: Provide semantic evidence from similar cases.
"""

import logging
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
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "strads123"
    ):
        """
        Initialize graph agent.
        
        Args:
            qdrant_client: Optional Qdrant client (for testing).
            neo4j_driver: Optional Neo4j driver (for testing).
            collection_name: Name of Qdrant collection.
            enable_qdrant: Enable Qdrant storage (requires running instance).
            enable_neo4j: Enable Neo4j knowledge graph (requires running instance).
            neo4j_uri: Neo4j connection URI.
            neo4j_user: Neo4j username.
            neo4j_password: Neo4j password.
        """
        self._collection_name = collection_name
        self.enable_qdrant = enable_qdrant and QDRANT_AVAILABLE
        self.enable_neo4j = enable_neo4j and NEO4J_AVAILABLE
        self._client = qdrant_client
        self._neo4j_driver = neo4j_driver
        
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
        
        Args:
            decision: Confirmed decision to store.
            cluster: Alert cluster that led to this decision.
            embedding: Optional embedding vector (generated if None).
        
        Returns:
            True if stored successfully.
        """
        if not decision.is_confirmed:
            logger.debug(f"[{self.AGENT_NAME}] Skipping unconfirmed decision {decision.decision_id}")
            return False
        
        # Create summary for semantic search
        summary = self._create_summary(decision, cluster)
        
        # Generate or use provided embedding
        if embedding is None:
            embedding = self._generate_embedding(summary)
        
        # Store in Qdrant if enabled
        qdrant_success = False
        if self.enable_qdrant and self._client and QDRANT_AVAILABLE:
            try:
                point = PointStruct(  # type: ignore
                    id=str(decision.decision_id),
                    vector=embedding,
                    payload={
                        "decision_state": decision.decision_state.value,
                        "confidence": decision.confidence,
                        "summary": summary,
                        "service": cluster.primary_service,
                        "severity": cluster.primary_severity,
                        "alert_count": cluster.alert_count,
                        "rules_applied": decision.rules_applied,
                        "created_at": decision.created_at.isoformat(),
                        "validated_by": decision.validated_by
                    }
                )
                self._client.upsert(
                    collection_name=self._collection_name,
                    points=[point]
                )
                logger.info(f"[{self.AGENT_NAME}] Stored decision {decision.decision_id} in Qdrant")
                qdrant_success = True
            except Exception as e:
                logger.error(f"[{self.AGENT_NAME}] Failed to store in Qdrant: {e}")
        
        # Store in Neo4j knowledge graph if enabled
        if self.enable_neo4j:
            self._store_in_neo4j(decision, cluster)
        
        # Fallback: store in memory if no other backend succeeded
        if not qdrant_success and not self.enable_neo4j:
            self._memory_store.append({
                "decision_id": str(decision.decision_id),
                "decision_state": decision.decision_state.value,
                "confidence": decision.confidence,
                "summary": summary,
                "service": cluster.primary_service,
                "severity": cluster.primary_severity,
                "embedding": embedding
            })
            logger.debug(f"[{self.AGENT_NAME}] Stored decision {decision.decision_id} in memory")
        
        return True
    
    def find_similar_decisions(
        self,
        cluster: AlertCluster,
        top_k: int = 3,
        min_similarity: float = 0.7
    ) -> List[SemanticEvidence]:
        """
        Find semantically similar past decisions.
        
        Args:
            cluster: Current alert cluster to match.
            top_k: Number of similar decisions to return.
            min_similarity: Minimum similarity score (0-1).
        
        Returns:
            List of SemanticEvidence objects.
        """
        # Create query summary
        query_summary = f"Service: {cluster.primary_service}, Severity: {cluster.primary_severity}, " \
                       f"Alerts: {cluster.alert_count}, Score: {cluster.correlation_score:.2f}"
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query_summary)
        
        # Search in Qdrant if enabled
        if self.enable_qdrant and self._client and QDRANT_AVAILABLE:
            try:
                results = self._client.query_points(  # type: ignore
                    collection_name=self._collection_name,
                    query=query_embedding,
                    limit=top_k,
                    score_threshold=min_similarity
                ).points
                
                evidence = []
                for result in results:
                    evidence.append(SemanticEvidence(
                        decision_id=UUID(result.id),
                        similarity_score=result.score,
                        summary=result.payload.get("summary", "")
                    ))
                
                logger.info(f"[{self.AGENT_NAME}] Found {len(evidence)} similar decisions in Qdrant")
                return evidence
            except Exception as e:
                logger.error(f"[{self.AGENT_NAME}] Failed to search Qdrant: {e}")
        
        # Fallback: search in memory (naive cosine similarity)
        evidence = self._search_memory(query_embedding, top_k, min_similarity)
        logger.debug(f"[{self.AGENT_NAME}] Found {len(evidence)} similar decisions in memory")
        return evidence
    
    def _create_summary(self, decision: Decision, cluster: AlertCluster) -> str:
        """Create searchable summary from decision and cluster."""
        return (
            f"Service: {cluster.primary_service}, "
            f"Severity: {cluster.primary_severity}, "
            f"Decision: {decision.decision_state.value}, "
            f"Confidence: {decision.confidence:.2f}, "
            f"Rules: {', '.join(decision.rules_applied)}, "
            f"Justification: {decision.justification}"
        )
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        TODO: Integrate with actual embedding model (sentence-transformers).
        For now, returns dummy embedding.
        """
        # Dummy embedding for offline mode
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        
        # Generate deterministic pseudo-random vector
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
        
        # Calculate cosine similarity for each stored decision
        import math
        
        def cosine_similarity(v1: List[float], v2: List[float]) -> float:
            dot_product = sum(a * b for a, b in zip(v1, v2))
            mag1 = math.sqrt(sum(a * a for a in v1))
            mag2 = math.sqrt(sum(b * b for b in v2))
            return dot_product / (mag1 * mag2) if mag1 and mag2 else 0.0
        
        # Score all stored decisions
        scored = []
        for item in self._memory_store:
            similarity = cosine_similarity(query_embedding, item["embedding"])
            if similarity >= min_similarity:
                scored.append((similarity, item))
        
        # Sort by similarity and take top_k
        scored.sort(reverse=True, key=lambda x: x[0])
        
        evidence = []
        for similarity, item in scored[:top_k]:
            evidence.append(SemanticEvidence(
                decision_id=UUID(item["decision_id"]),
                similarity_score=similarity,
                summary=item["summary"]
            ))
        
        return evidence
    
    def get_stats(self) -> dict:
        """Get statistics about stored decisions."""
        stats = {
            "backends": [],
            "total_decisions": 0,
            "neo4j_nodes": None,
            "neo4j_relationships": None
        }
        
        if self.enable_qdrant and self._client:
            try:
                info = self._client.get_collection(self._collection_name)
                stats["backends"].append("qdrant")
                stats["total_decisions"] = info.points_count
                stats["qdrant_collection"] = self._collection_name
            except Exception as e:
                logger.error(f"[{self.AGENT_NAME}] Failed to get Qdrant stats: {e}")
        
        if self.enable_neo4j and self._neo4j_driver:
            try:
                with self._neo4j_driver.session() as session:
                    result = session.run("""
                        MATCH (d:Decision)
                        RETURN count(d) as decisions,
                               count{(d)-[:FOR_SERVICE]->()} as services,
                               count{(d)-[:APPLIED_RULE]->()} as rules
                    """)
                    record = result.single()
                    stats["backends"].append("neo4j")
                    stats["neo4j_nodes"] = {
                        "decisions": record["decisions"],
                        "services": record["services"],
                        "rules": record["rules"]
                    }
            except Exception as e:
                logger.error(f"[{self.AGENT_NAME}] Failed to get Neo4j stats: {e}")
        
        if not stats["backends"]:
            stats["backends"].append("memory")
            stats["total_decisions"] = len(self._memory_store)
        
        stats["backends"] = ", ".join(stats["backends"])
        return stats
    
    def get_service_history(self, service_name: str, limit: int = 10) -> List[dict]:
        """Get decision history for a specific service from Neo4j."""
        if not self.enable_neo4j or not self._neo4j_driver:
            return []
        
        try:
            with self._neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (d:Decision)-[:FOR_SERVICE]->(s:Service {name: $service})
                    OPTIONAL MATCH (d)-[:APPLIED_RULE]->(r:Rule)
                    RETURN d.id as decision_id,
                           d.state as state,
                           d.confidence as confidence,
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
