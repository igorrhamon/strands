"""
Unit Tests for Vector Store Tools

Tests:
- QdrantClientWrapper (mocked Qdrant)
- EmbeddingClient (mocked SentenceTransformers)
- VectorStore (integration of both)
- Constitution Principle III enforcement
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from src.models.decision import Decision, DecisionState, HumanValidationStatus
from src.models.embedding import VectorEmbedding, SimilarityResult
from src.tools.qdrant_client import (
    QdrantClientWrapper,
    QdrantConnectionError,
    VECTOR_DIM,
)
from src.tools.embedding_client import (
    EmbeddingClient,
    EmbeddingModelError,
    create_embedding_text,
)
from src.tools.vector_store import VectorStore, VectorStoreError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_qdrant_sdk():
    """Mock QdrantClient SDK."""
    with patch("src.tools.qdrant_client.QdrantSDKClient") as mock:
        client = Mock()
        mock.return_value = client
        
        # Mock get_collections
        collection = Mock()
        collection.name = "alert_decisions"
        client.get_collections.return_value = Mock(collections=[collection])
        
        # Mock get_collection
        client.get_collection.return_value = Mock(points_count=10)
        
        # Mock search results
        hit = Mock()
        hit.id = str(uuid4())
        hit.score = 0.85
        hit.payload = {
            "source_decision_id": str(uuid4()),
            "source_text": "Test alert description",
            "service": "test-service",
            "severity": "warning",
            "rules_applied": ["rule_1"],
        }
        client.search.return_value = [hit]
        
        yield mock, client


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer model."""
    with patch("src.tools.embedding_client.SentenceTransformer") as mock:
        model = Mock()
        # Return 384-dim vector
        model.encode.return_value = Mock(tolist=lambda: [0.1] * VECTOR_DIM)
        mock.return_value = model
        yield mock, model


@pytest.fixture
def sample_decision():
    """Create a sample decision for testing."""
    return Decision(
        decision_state=DecisionState.CLOSE,
        confidence=0.9,
        justification="Test justification for closing alert",
        rules_applied=["rule_severity_check", "rule_service_match"],
        human_validation_status=HumanValidationStatus.PENDING,
    )


@pytest.fixture
def confirmed_decision(sample_decision):
    """Create a confirmed decision for testing."""
    sample_decision.confirm("test-user")
    return sample_decision


# ============================================================================
# QdrantClientWrapper Tests
# ============================================================================

class TestQdrantClientWrapper:
    """Tests for QdrantClientWrapper."""
    
    def test_connect_success(self, mock_qdrant_sdk):
        """Test successful connection to Qdrant."""
        mock_class, mock_client = mock_qdrant_sdk
        
        wrapper = QdrantClientWrapper()
        result = wrapper.connect()
        
        assert result is wrapper  # Returns self for chaining
        mock_class.assert_called_once()
        mock_client.get_collections.assert_called_once()
    
    def test_connect_failure(self, mock_qdrant_sdk):
        """Test connection failure raises QdrantConnectionError."""
        mock_class, mock_client = mock_qdrant_sdk
        mock_client.get_collections.side_effect = Exception("Connection refused")
        
        wrapper = QdrantClientWrapper()
        
        with pytest.raises(QdrantConnectionError) as exc_info:
            wrapper.connect()
        
        assert "Failed to connect" in str(exc_info.value)
    
    def test_ensure_collection_creates_if_missing(self, mock_qdrant_sdk):
        """Test collection is created if it doesn't exist."""
        mock_class, mock_client = mock_qdrant_sdk
        mock_client.get_collections.return_value = Mock(collections=[])
        
        wrapper = QdrantClientWrapper().connect()
        wrapper.ensure_collection()
        
        mock_client.create_collection.assert_called_once()
    
    def test_ensure_collection_skips_if_exists(self, mock_qdrant_sdk):
        """Test collection is not created if it exists."""
        mock_class, mock_client = mock_qdrant_sdk
        
        wrapper = QdrantClientWrapper().connect()
        wrapper.ensure_collection()
        
        mock_client.create_collection.assert_not_called()
    
    def test_upsert_point_validates_dimension(self, mock_qdrant_sdk):
        """Test that upsert validates vector dimension."""
        mock_class, mock_client = mock_qdrant_sdk
        
        wrapper = QdrantClientWrapper().connect()
        
        # Wrong dimension should raise
        with pytest.raises(ValueError) as exc_info:
            wrapper.upsert_point(
                point_id=uuid4(),
                vector=[0.1] * 100,  # Wrong dimension
                payload={},
            )
        
        assert "dimensions" in str(exc_info.value)
    
    def test_search_returns_results(self, mock_qdrant_sdk):
        """Test search returns properly formatted results."""
        mock_class, mock_client = mock_qdrant_sdk
        
        wrapper = QdrantClientWrapper().connect()
        results = wrapper.search(
            query_vector=[0.1] * VECTOR_DIM,
            top_k=5,
            score_threshold=0.75,
        )
        
        assert len(results) == 1
        assert "id" in results[0]
        assert "score" in results[0]
        assert "payload" in results[0]
        assert results[0]["score"] == 0.85


# ============================================================================
# EmbeddingClient Tests
# ============================================================================

class TestEmbeddingClient:
    """Tests for EmbeddingClient."""
    
    def test_embed_single_text(self, mock_sentence_transformer):
        """Test embedding a single text."""
        # Reset singleton for testing
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        client = EmbeddingClient()
        result = client.embed("Test alert message")
        
        assert len(result) == VECTOR_DIM
        assert all(isinstance(v, float) for v in result)
    
    def test_embed_empty_text_raises(self, mock_sentence_transformer):
        """Test that empty text raises ValueError."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        client = EmbeddingClient()
        
        with pytest.raises(ValueError) as exc_info:
            client.embed("")
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_embed_batch(self, mock_sentence_transformer):
        """Test batch embedding."""
        mock_class, mock_model = mock_sentence_transformer
        # Return array of vectors
        mock_model.encode.return_value = [
            Mock(tolist=lambda: [0.1] * VECTOR_DIM),
            Mock(tolist=lambda: [0.2] * VECTOR_DIM),
        ]
        
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        client = EmbeddingClient()
        results = client.embed_batch(["Text 1", "Text 2"])
        
        assert len(results) == 2
    
    def test_vector_dimension_property(self, mock_sentence_transformer):
        """Test vector_dimension property returns correct value."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        client = EmbeddingClient()
        assert client.vector_dimension == VECTOR_DIM


class TestCreateEmbeddingText:
    """Tests for create_embedding_text helper."""
    
    def test_format_with_all_fields(self):
        """Test that all fields are included in formatted text."""
        result = create_embedding_text(
            alert_description="High CPU usage detected",
            service="checkout-service",
            severity="critical",
            decision_summary="Close due to auto-recovery",
            rules_applied=["rule_1", "rule_2"],
        )
        
        assert "High CPU usage" in result
        assert "checkout-service" in result
        assert "critical" in result
        assert "Close due to auto-recovery" in result
        assert "rule_1, rule_2" in result
    
    def test_format_with_empty_rules(self):
        """Test formatting with no rules applied."""
        result = create_embedding_text(
            alert_description="Alert",
            service="service",
            severity="warning",
            decision_summary="Decision",
            rules_applied=[],
        )
        
        assert "Rules: none" in result


# ============================================================================
# VectorStore Tests
# ============================================================================

class TestVectorStore:
    """Tests for VectorStore high-level operations."""
    
    def test_persist_unconfirmed_decision_raises(
        self, 
        mock_qdrant_sdk, 
        mock_sentence_transformer, 
        sample_decision
    ):
        """
        Constitution Principle III: Unconfirmed decisions MUST NOT be persisted.
        """
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        store = VectorStore().connect()
        
        with pytest.raises(VectorStoreError) as exc_info:
            store.persist_decision(
                decision=sample_decision,  # PENDING status
                alert_description="Test alert",
                human_validator="test-user",
            )
        
        assert "unconfirmed" in str(exc_info.value).lower()
        assert "Constitution" in str(exc_info.value)
    
    def test_persist_confirmed_decision_success(
        self,
        mock_qdrant_sdk,
        mock_sentence_transformer,
        confirmed_decision,
    ):
        """Test that confirmed decisions are persisted successfully."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        mock_class, mock_client = mock_qdrant_sdk
        
        store = VectorStore().connect()
        result = store.persist_decision(
            decision=confirmed_decision,
            alert_description="Test alert for confirmed decision",
            human_validator="test-user",
        )
        
        assert isinstance(result, VectorEmbedding)
        assert result.source_decision_id == confirmed_decision.decision_id
        assert result.human_validator == "test-user"
        mock_client.upsert.assert_called_once()
    
    def test_search_similar_returns_results(
        self,
        mock_qdrant_sdk,
        mock_sentence_transformer,
    ):
        """Test that search returns SimilarityResult objects."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        store = VectorStore().connect()
        results = store.search_similar("Test query for similar alerts")
        
        assert len(results) >= 1
        assert all(isinstance(r, SimilarityResult) for r in results)
        assert results[0].similarity_score == 0.85
    
    def test_search_without_connect_raises(self, mock_qdrant_sdk, mock_sentence_transformer):
        """Test that operations without connect() raise error."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        store = VectorStore()  # Not connected
        
        with pytest.raises(VectorStoreError) as exc_info:
            store.search_similar("Query")
        
        assert "not connected" in str(exc_info.value).lower()
    
    def test_count_embeddings(self, mock_qdrant_sdk, mock_sentence_transformer):
        """Test counting embeddings in store."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        store = VectorStore().connect()
        count = store.count_embeddings()
        
        assert count == 10  # Mocked value


# ============================================================================
# Constitution Principle III Specific Tests
# ============================================================================

class TestConstitutionPrincipleIII:
    """
    Dedicated tests for Constitution Principle III:
    "Embeddings são gerados APENAS após confirmação humana"
    """
    
    def test_pending_decision_not_embedded(
        self,
        mock_qdrant_sdk,
        mock_sentence_transformer,
        sample_decision,
    ):
        """PENDING decisions must not generate embeddings."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        mock_class, mock_client = mock_qdrant_sdk
        
        store = VectorStore().connect()
        
        with pytest.raises(VectorStoreError):
            store.persist_decision(
                decision=sample_decision,
                alert_description="Test",
                human_validator="user",
            )
        
        # Verify upsert was NOT called
        mock_client.upsert.assert_not_called()
    
    def test_rejected_decision_not_embedded(
        self,
        mock_qdrant_sdk,
        mock_sentence_transformer,
        sample_decision,
    ):
        """REJECTED decisions must not generate embeddings."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        sample_decision.reject("test-user")
        mock_class, mock_client = mock_qdrant_sdk
        
        store = VectorStore().connect()
        
        with pytest.raises(VectorStoreError):
            store.persist_decision(
                decision=sample_decision,
                alert_description="Test",
                human_validator="user",
            )
        
        mock_client.upsert.assert_not_called()
    
    def test_confirmed_decision_embedded(
        self,
        mock_qdrant_sdk,
        mock_sentence_transformer,
        confirmed_decision,
    ):
        """CONFIRMED decisions MUST generate embeddings."""
        EmbeddingClient._instance = None
        EmbeddingClient._model = None
        
        mock_class, mock_client = mock_qdrant_sdk
        
        store = VectorStore().connect()
        result = store.persist_decision(
            decision=confirmed_decision,
            alert_description="Test confirmed",
            human_validator="test-user",
        )
        
        assert result is not None
        mock_client.upsert.assert_called_once()
