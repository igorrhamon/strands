"""
Stub module for semantica library.
Provides mock implementations of semantic extraction and knowledge graph functions.
"""

from .semantic_extract import NERExtractor
from .kg import GraphBuilder

__all__ = ["NERExtractor", "GraphBuilder"]
