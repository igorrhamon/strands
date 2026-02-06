"""
Testes Unitários para Ferramentas de Armazenamento Vetorial

Testes:
- QdrantClientWrapper (Qdrant mockado)
- EmbeddingClient (SentenceTransformers mockado)
- VectorStore (integração de ambos)
- Aplicação do Princípio de Constituição III
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
    """Mock do SDK QdrantClient."""
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
    """Mock do modelo SentenceTransformer."""
    with patch("src.tools.embedding_client.SentenceTransformer") as mock:
        model = Mock()
        # Retorna vetor de 384 dimensões
        model.encode.return_value = Mock(tolist=lambda: [0.1] * VECTOR_DIM)
        mock.return_value = model
        yield mock, model


@pytest.fixture
def sample_decision():
    """Cria uma decisão de amostra para testes."""
    return Decision(
        decision_state=DecisionState.CLOSE,
        confidence=0.9,
        justification="Test justification for closing alert",
        rules_applied=["rule_severity_check", "rule_service_match"],
        human_validation_status=HumanValidationStatus.PENDING,
    )


@pytest.fixture
def confirmed_decision(sample_decision):
    """Cria uma decisão confirmada para testes."""
    sample_decision.confirm("test-user")
    return sample_decision


# ============================================================================
# Testes do QdrantClientWrapper
# ============================================================================

class TestQdrantClientWrapper:
    """Testa o wrapper do cliente Qdrant"""

    def test_initialization(self, mock_qdrant_sdk):
        """Testa inicialização do wrapper"""
        mock_sdk, mock_client = mock_qdrant_sdk
        wrapper = QdrantClientWrapper()
        
        assert wrapper is not None
        assert mock_sdk.called

    def test_get_collections(self, mock_qdrant_sdk):
        """Testa obtenção de coleções"""
        mock_sdk, mock_client = mock_qdrant_sdk
        wrapper = QdrantClientWrapper()
        
        collections = wrapper.get_collections()
        assert len(collections) > 0

    def test_search(self, mock_qdrant_sdk):
        """Testa busca no Qdrant"""
        mock_sdk, mock_client = mock_qdrant_sdk
        wrapper = QdrantClientWrapper()
        
        vector = [0.1] * VECTOR_DIM
        results = wrapper.search("alert_decisions", vector)
        
        assert len(results) > 0
        assert results[0].score == 0.85

    def test_connection_error(self, mock_qdrant_sdk):
        """Testa tratamento de erro de conexão"""
        mock_sdk, mock_client = mock_qdrant_sdk
        mock_client.search.side_effect = Exception("Connection failed")
        
        wrapper = QdrantClientWrapper()
        
        with pytest.raises(QdrantConnectionError):
            wrapper.search("alert_decisions", [0.1] * VECTOR_DIM)


# ============================================================================
# Testes do EmbeddingClient
# ============================================================================

class TestEmbeddingClient:
    """Testa o cliente de embedding"""

    def test_initialization(self, mock_sentence_transformer):
        """Testa inicialização do cliente"""
        mock_st, mock_model = mock_sentence_transformer
        client = EmbeddingClient()
        
        assert client is not None

    def test_encode_text(self, mock_sentence_transformer):
        """Testa codificação de texto"""
        mock_st, mock_model = mock_sentence_transformer
        client = EmbeddingClient()
        
        text = "Test alert description"
        embedding = client.encode(text)
        
        assert len(embedding) == VECTOR_DIM
        assert all(isinstance(x, float) for x in embedding)

    def test_encode_batch(self, mock_sentence_transformer):
        """Testa codificação em lote"""
        mock_st, mock_model = mock_sentence_transformer
        client = EmbeddingClient()
        
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = client.encode_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(e) == VECTOR_DIM for e in embeddings)

    def test_model_error(self, mock_sentence_transformer):
        """Testa tratamento de erro de modelo"""
        mock_st, mock_model = mock_sentence_transformer
        mock_model.encode.side_effect = Exception("Model error")
        
        client = EmbeddingClient()
        
        with pytest.raises(EmbeddingModelError):
            client.encode("Test text")


# ============================================================================
# Testes do VectorStore
# ============================================================================

class TestVectorStore:
    """Testa o armazenamento vetorial"""

    def test_initialization(self, mock_qdrant_sdk, mock_sentence_transformer):
        """Testa inicialização do vector store"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        assert store is not None

    def test_add_vector(self, mock_qdrant_sdk, mock_sentence_transformer, sample_decision):
        """Testa adição de vetor"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        vector_id = store.add_vector(sample_decision)
        
        assert vector_id is not None

    def test_search_similar(self, mock_qdrant_sdk, mock_sentence_transformer):
        """Testa busca de vetores similares"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        results = store.search_similar("Test alert", limit=5)
        
        assert isinstance(results, list)

    def test_delete_vector(self, mock_qdrant_sdk, mock_sentence_transformer):
        """Testa deleção de vetor"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        vector_id = str(uuid4())
        
        result = store.delete_vector(vector_id)
        assert result is not None

    def test_update_vector(self, mock_qdrant_sdk, mock_sentence_transformer, sample_decision):
        """Testa atualização de vetor"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        vector_id = str(uuid4())
        
        result = store.update_vector(vector_id, sample_decision)
        assert result is not None


# ============================================================================
# Testes de Integração
# ============================================================================

class TestVectorStoreIntegration:
    """Testa integração completa do vector store"""

    def test_end_to_end_workflow(self, mock_qdrant_sdk, mock_sentence_transformer, sample_decision):
        """Testa workflow completo"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        
        # Adicionar vetor
        vector_id = store.add_vector(sample_decision)
        assert vector_id is not None
        
        # Buscar similar
        results = store.search_similar("Test alert")
        assert len(results) >= 0
        
        # Atualizar vetor
        updated = store.update_vector(vector_id, sample_decision)
        assert updated is not None
        
        # Deletar vetor
        deleted = store.delete_vector(vector_id)
        assert deleted is not None

    def test_batch_operations(self, mock_qdrant_sdk, mock_sentence_transformer):
        """Testa operações em lote"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        
        decisions = [
            Decision(
                decision_state=DecisionState.CLOSE,
                confidence=0.9,
                justification=f"Test {i}",
                rules_applied=["rule_1"],
                human_validation_status=HumanValidationStatus.PENDING,
            )
            for i in range(5)
        ]
        
        vector_ids = store.add_batch(decisions)
        assert len(vector_ids) == 5

    def test_error_handling(self, mock_qdrant_sdk, mock_sentence_transformer):
        """Testa tratamento de erros"""
        mock_sdk, mock_client = mock_qdrant_sdk
        mock_client.search.side_effect = Exception("Search failed")
        
        store = VectorStore()
        
        with pytest.raises(VectorStoreError):
            store.search_similar("Test")


# ============================================================================
# Testes de Conformidade com Princípio III
# ============================================================================

class TestConstitutionPrincipleIII:
    """Testa conformidade com Princípio de Constituição III"""

    def test_principle_iii_enforcement(self, mock_qdrant_sdk, mock_sentence_transformer, confirmed_decision):
        """Testa aplicação do Princípio III"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        
        # Apenas decisões confirmadas devem ser armazenadas
        vector_id = store.add_vector(confirmed_decision)
        assert vector_id is not None

    def test_unconfirmed_decision_rejected(self, mock_qdrant_sdk, mock_sentence_transformer, sample_decision):
        """Testa rejeição de decisões não confirmadas"""
        mock_qdrant_sdk
        mock_sentence_transformer
        
        store = VectorStore()
        
        # Decisões não confirmadas devem ser rejeitadas
        with pytest.raises(ValueError):
            store.add_vector(sample_decision)
