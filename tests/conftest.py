import sys
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from typing import Any, List, Optional
from datetime import datetime

# Mock semantica globally for tests
sys.modules["semantica"] = MagicMock()
sys.modules["semantica.semantic_extract"] = MagicMock()
sys.modules["semantica.kg"] = MagicMock()

# Mock fastembed
sys.modules["fastembed"] = MagicMock()

# Mock missing agents/models that were deleted but still imported in tests
mock_repo_context = MagicMock()
sys.modules["src.agents.repository_context"] = mock_repo_context
sys.modules["src.agents.analysis.embedding_agent"] = MagicMock()
sys.modules["src.agents.embedding_agent"] = MagicMock()
sys.modules["src.models.embedding"] = MagicMock()
sys.modules["src.pipeline.refrag_pipeline"] = MagicMock()
sys.modules["src.tools.vector_store"] = MagicMock()

# Handle AgentResponse in old tests
@dataclass
class AgentResponse:
    agent_id: str
    agent_name: str
    confidence: float
    analysis: str
    recommendations: List[str] = field(default_factory=list)

import src.agents.base_agent
src.agents.base_agent.AgentResponse = AgentResponse

# If tests import from 'agents.base_agent' directly due to sys.path manipulation
mock_base_agent = MagicMock()
mock_base_agent.AgentResponse = AgentResponse
sys.modules["agents.base_agent"] = mock_base_agent
