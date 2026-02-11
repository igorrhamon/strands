"""
Mock Knowledge Graph Builder for semantic graph operations.
Provides basic graph building and querying without external graph libraries.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Mock Knowledge Graph builder for semantic retrieval."""
    
    def __init__(self):
        """Initialize the graph builder."""
        self.graph = {}
        logger.info("Initialized GraphBuilder (mock)")
    
    def add_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any]) -> None:
        """
        Add an entity to the knowledge graph.
        
        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type/category of the entity
            properties: Entity properties/attributes
        """
        self.graph[entity_id] = {
            "type": entity_type,
            "properties": properties
        }
        logger.debug(f"Added entity {entity_id} ({entity_type})")
    
    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a relationship between two entities.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            relationship_type: Type of relationship
            properties: Optional relationship properties
        """
        if "relationships" not in self.graph:
            self.graph["relationships"] = []
        
        self.graph["relationships"].append({
            "source": source_id,
            "target": target_id,
            "type": relationship_type,
            "properties": properties or {}
        })
        logger.debug(f"Added relationship {source_id} -[{relationship_type}]-> {target_id}")
    
    def query(
        self,
        entity_type: str,
        query_properties: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query entities in the knowledge graph.
        
        Args:
            entity_type: Type of entities to query
            query_properties: Optional properties to filter by
            limit: Maximum number of results
            
        Returns:
            List of matching entities
        """
        results = []
        query_properties = query_properties or {}
        
        for entity_id, entity_data in self.graph.items():
            if isinstance(entity_data, dict) and entity_data.get("type") == entity_type:
                # Simple property matching
                match = True
                for key, value in query_properties.items():
                    if entity_data.get("properties", {}).get(key) != value:
                        match = False
                        break
                
                if match:
                    results.append({
                        "id": entity_id,
                        "type": entity_type,
                        **entity_data.get("properties", {})
                    })
                    
                if len(results) >= limit:
                    break
        
        logger.debug(f"Query returned {len(results)} results for type {entity_type}")
        return results
    
    def semantic_search(
        self,
        query_text: str,
        entity_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search in the knowledge graph.
        
        Args:
            query_text: Text to search for
            entity_type: Optional entity type to filter by
            limit: Maximum number of results
            
        Returns:
            List of matching entities
        """
        results = []
        query_lower = query_text.lower()
        
        for entity_id, entity_data in self.graph.items():
            if not isinstance(entity_data, dict):
                continue
                
            # Filter by entity type if specified
            if entity_type and entity_data.get("type") != entity_type:
                continue
            
            # Simple text matching in properties
            properties = entity_data.get("properties", {})
            match_score = 0
            
            for value in properties.values():
                if isinstance(value, str) and query_lower in value.lower():
                    match_score += 1
            
            if match_score > 0:
                results.append({
                    "id": entity_id,
                    "type": entity_data.get("type"),
                    "score": match_score,
                    **properties
                })
        
        # Sort by score and limit results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.debug(f"Semantic search returned {len(results[:limit])} results")
        return results[:limit]
