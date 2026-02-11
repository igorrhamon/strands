"""
Mock Named Entity Recognizer for semantic extraction.
Provides basic NER functionality without requiring external NLP libraries.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class NERExtractor:
    """Mock Named Entity Recognizer using simple pattern matching."""
    
    def __init__(self, method: str = "ml", model: str = "en_core_web_sm"):
        """
        Initialize the NER extractor.
        
        Args:
            method: Extraction method (ignored in mock)
            model: Model name (ignored in mock)
        """
        self.method = method
        self.model = model
        logger.info(f"Initialized NERExtractor (mock) - method={method}, model={model}")
    
    def extract(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text using simple pattern matching.
        
        Args:
            text: Input text to extract entities from
            
        Returns:
            Dictionary with entity types and their values
        """
        entities = {
            "PERSON": [],
            "ORG": [],
            "GPE": [],
            "PRODUCT": [],
            "SERVICE": [],
        }
        
        # Simple pattern-based extraction
        words = text.split()
        
        # Look for common service/product names
        service_keywords = ["service", "api", "database", "cache", "queue", "storage"]
        for word in words:
            word_lower = word.lower().rstrip('.,;:')
            if any(kw in word_lower for kw in service_keywords):
                entities["SERVICE"].append(word.rstrip('.,;:'))
        
        logger.debug(f"Extracted entities: {entities}")
        return entities
