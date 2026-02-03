"""
Unit Tests for RAG Client (Repository Context Agent)

Tests:
- Semantic similarity search integration
- Context quality calculation
- SemanticEvidence conversion
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime

from src.models.cluster import AlertCluster
from src.models.alert import NormalizedAlert, ValidationStatus
from src.models.embedding import SimilarityResult
from src.models.decision import SemanticEvidence
from src.agents.embedding_agent import EmbeddingAgent, EmbeddingAgentError
from src.agents.repository_context import RepositoryContextAgent


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_embedding_agent():
    """Mock EmbeddingAgent for testing."""
    agent = Mock(spec=EmbeddingAgent)
    
    # Default: return 3 similar results
    agent.search_similar.return_value = [
        SimilarityResult(
            decision_id=uuid4(),
            similarity_score=0.92,
            source_text="Previous alert: High CPU on checkout-service, closed as resolved",
            service="checkout-service",
            rules_applied=["rule_auto_recovery"],
        ),
        SimilarityResult(
            decision_id=uuid4(),
            similarity_score=0.85,
            source_text="Previous alert: Memory spike on checkout-service, escalated to team",
            service="checkout-service",
            rules_applied=["rule_memory_threshold"],
        ),
        SimilarityResult(
            decision_id=uuid4(),
            similarity_score=0.78,
            source_text="Previous alert: Request latency on checkout-service, observed for 30min",
            service="checkout-service",
            rules_applied=["rule_latency_check"],
        ),
    ]
    
    agent.close = Mock()
    return agent


@pytest.fixture
def sample_cluster():
    """Create a sample AlertCluster for testing."""
    alerts = [
        NormalizedAlert(
            timestamp=datetime.utcnow(),
            fingerprint="fp-001",
            service="checkout-service",
            severity="critical",
            description="High CPU usage detected",
            labels={},
            validation_status=ValidationStatus.VALID,
        ),
        NormalizedAlert(
            timestamp=datetime.utcnow(),
            fingerprint="fp-002",
            service="checkout-service",
            severity="warning",
            description="Memory usage elevated",
            labels={},
            validation_status=ValidationStatus.VALID,
        ),
    ]
    return AlertCluster.from_alerts(alerts, correlation_score=0.9)


# ============================================================================
# RepositoryContextAgent Tests
# ============================================================================

class TestRepositoryContextAgent:
    """Tests for RepositoryContextAgent."""
    
    @pytest.mark.asyncio
    async def test_get_context_success(self, mock_embedding_agent, sample_cluster):
        """Test successful context retrieval."""
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        context = await agent.get_context(sample_cluster)
        
        assert "semantic_evidence" in context
        assert "repository_context" in context
        assert "context_quality" in context
        assert context["similar_count"] == 3
    
    @pytest.mark.asyncio
    async def test_semantic_evidence_converted(self, mock_embedding_agent, sample_cluster):
        """Test that SimilarityResult is converted to SemanticEvidence."""
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        context = await agent.get_context(sample_cluster)
        
        assert len(context["semantic_evidence"]) == 3
        for evidence in context["semantic_evidence"]:
            assert isinstance(evidence, SemanticEvidence)
            assert evidence.similarity_score >= 0.75
    
    @pytest.mark.asyncio
    async def test_context_quality_high_scores(self, mock_embedding_agent, sample_cluster):
        """Test context quality with high similarity scores."""
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        context = await agent.get_context(sample_cluster)
        
        # With high scores, quality should be good
        assert context["context_quality"] >= 0.5
    
    @pytest.mark.asyncio
    async def test_context_quality_no_results(self, mock_embedding_agent, sample_cluster):
        """Test context quality with no results."""
        mock_embedding_agent.search_similar.return_value = []
        
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        context = await agent.get_context(sample_cluster)
        
        assert context["context_quality"] == 0.0
        assert context["similar_count"] == 0
    
    @pytest.mark.asyncio
    async def test_embedding_agent_error_handled(self, mock_embedding_agent, sample_cluster):
        """Test graceful handling of EmbeddingAgent errors."""
        mock_embedding_agent.search_similar.side_effect = EmbeddingAgentError("Connection failed")
        
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        # Should not raise, but return empty results
        context = await agent.get_context(sample_cluster)
        
        assert context["semantic_evidence"] == []
        assert context["similar_count"] == 0
    
    @pytest.mark.asyncio
    async def test_score_threshold_filtering(self, mock_embedding_agent, sample_cluster):
        """Test that low-score results are filtered out."""
        # Add a low-score result
        mock_embedding_agent.search_similar.return_value = [
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.92,
                source_text="High score match",
                service="checkout-service",
                rules_applied=[],
            ),
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.60,  # Below default threshold of 0.75
                source_text="Low score match",
                service="checkout-service",
                rules_applied=[],
            ),
        ]
        
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        context = await agent.get_context(sample_cluster)
        
        # Only the high-score result should be in evidence
        assert len(context["semantic_evidence"]) == 1
        assert context["semantic_evidence"][0].similarity_score == 0.92
    
    @pytest.mark.asyncio
    async def test_repository_context_populated(self, mock_embedding_agent, sample_cluster):
        """Test that repository context is included."""
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        context = await agent.get_context(sample_cluster)
        
        repo_context = context["repository_context"]
        assert "service" in repo_context
        assert repo_context["service"] == "checkout-service"
    
    def test_close_closes_embedding_agent(self, mock_embedding_agent):
        """Test that close() closes the embedding agent."""
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        agent.close()
        
        mock_embedding_agent.close.assert_called_once()


class TestBuildQueryText:
    """Tests for query text building."""
    
    @pytest.mark.asyncio
    async def test_query_includes_service(self, mock_embedding_agent, sample_cluster):
        """Test that query includes service name."""
        agent = RepositoryContextAgent(embedding_agent=mock_embedding_agent)
        
        await agent.get_context(sample_cluster)
        
        # Check that search was called with service in the query
        mock_embedding_agent.search_similar.assert_called_once()
        call_kwargs = mock_embedding_agent.search_similar.call_args[1]
        assert call_kwargs["service"] == "checkout-service"


class TestContextQualityCalculation:
    """Tests for context quality calculation."""
    
    def test_quality_zero_for_empty(self):
        """Test quality is 0 for empty results."""
        agent = RepositoryContextAgent()
        quality = agent._calculate_quality([])
        
        assert quality == 0.0
    
    def test_quality_high_for_good_results(self):
        """Test quality is high for high-scoring results."""
        results = [
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.95,
                source_text="Test",
                service="test",
                rules_applied=[],
            ),
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.92,
                source_text="Test",
                service="test",
                rules_applied=[],
            ),
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.90,
                source_text="Test",
                service="test",
                rules_applied=[],
            ),
        ]
        
        agent = RepositoryContextAgent()
        quality = agent._calculate_quality(results)
        
        assert quality >= 0.7  # High quality expected
    
    def test_quality_moderate_for_single_result(self):
        """Test quality is moderate for single result."""
        results = [
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.85,
                source_text="Test",
                service="test",
                rules_applied=[],
            ),
        ]
        
        agent = RepositoryContextAgent()
        quality = agent._calculate_quality(results)
        
        # Single result reduces count factor
        assert 0.3 <= quality <= 0.7
