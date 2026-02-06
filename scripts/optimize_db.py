#!/usr/bin/env python3
"""
Database Optimization Script for Strands

This script implements performance optimizations for Neo4j and Qdrant databases:
1. Creates necessary indexes and constraints in Neo4j
2. Optimizes Qdrant collection settings and indexes
3. Configures connection pooling parameters
"""

import os
import time
import logging
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db-optimizer")

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

def optimize_neo4j():
    """Create indexes and constraints for Neo4j."""
    logger.info("Optimizing Neo4j database...")
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # 1. Create constraints (automatically creates indexes)
            constraints = [
                "CREATE CONSTRAINT incident_id_unique IF NOT EXISTS FOR (i:Incident) REQUIRE i.id IS UNIQUE",
                "CREATE CONSTRAINT agent_id_unique IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE",
                "CREATE CONSTRAINT finding_id_unique IF NOT EXISTS FOR (f:Finding) REQUIRE f.id IS UNIQUE"
            ]
            
            for constraint in constraints:
                logger.info(f"Applying constraint: {constraint}")
                session.run(constraint)
                
            # 2. Create composite indexes for frequent query patterns
            indexes = [
                "CREATE INDEX incident_status_severity IF NOT EXISTS FOR (i:Incident) ON (i.status, i.severity)",
                "CREATE INDEX incident_created_at IF NOT EXISTS FOR (i:Incident) ON (i.created_at)",
                "CREATE INDEX finding_confidence IF NOT EXISTS FOR (f:Finding) ON (f.confidence)"
            ]
            
            for index in indexes:
                logger.info(f"Creating index: {index}")
                session.run(index)
                
            # 3. Optimize full-text search indexes
            fts_indexes = [
                "CREATE FULLTEXT INDEX incident_text_search IF NOT EXISTS FOR (i:Incident) ON EACH [i.title, i.description]",
                "CREATE FULLTEXT INDEX finding_text_search IF NOT EXISTS FOR (f:Finding) ON EACH [f.description]"
            ]
            
            for index in fts_indexes:
                logger.info(f"Creating full-text index: {index}")
                session.run(index)
                
        driver.close()
        logger.info("Neo4j optimization completed successfully.")
        
    except Exception as e:
        logger.error(f"Failed to optimize Neo4j: {e}")

def optimize_qdrant():
    """Optimize Qdrant collection settings."""
    logger.info("Optimizing Qdrant database...")
    
    try:
        client = QdrantClient(url=Qdrant_URL)
        collection_name = "strands_knowledge_base"
        
        # Check if collection exists
        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if not exists:
            logger.warning(f"Collection {collection_name} does not exist. Creating with optimized settings...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=384,  # Default for all-MiniLM-L6-v2
                    distance=models.Distance.COSINE
                ),
                # Optimization: HNSW index settings
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                    memmap_threshold=20000,
                    indexing_threshold=10000,
                    flush_interval_sec=5,
                    max_optimization_threads=2
                ),
                # Optimization: Quantization for memory efficiency
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True
                    )
                )
            )
        else:
            logger.info(f"Updating settings for collection {collection_name}...")
            client.update_collection(
                collection_name=collection_name,
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                    memmap_threshold=20000,
                    indexing_threshold=10000,
                    flush_interval_sec=5,
                    max_optimization_threads=2
                )
            )
            
        # Create payload indexes for filtering
        payload_indexes = ["type", "source", "timestamp", "severity"]
        for field in payload_indexes:
            logger.info(f"Creating payload index for field: {field}")
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            
        logger.info("Qdrant optimization completed successfully.")
        
    except Exception as e:
        logger.error(f"Failed to optimize Qdrant: {e}")

if __name__ == "__main__":
    logger.info("Starting database optimization...")
    optimize_neo4j()
    optimize_qdrant()
    logger.info("Database optimization finished.")
