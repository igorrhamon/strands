"""
Unit Tests for Non-Learning Verification

Constitution Principle III: Embeddings are generated ONLY after human confirmation.

These tests verify that:
1. Unconfirmed decisions do NOT create embeddings
2. Rejected decisions do NOT create embeddings
3. Only confirmed decisions create embeddings
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from src.models.alert import NormalizedAlert, ValidationStatus
from src.models.cluster import AlertCluster
from src.models.decision import Decision, DecisionState
from src.models.embedding import VectorEmbedding
from src.agents.embedding_agent import EmbeddingAgent, EmbeddingAgentError
from src.agents.report_agent import ReportAgent
from src.tools.vector_store import VectorStore, VectorStoreError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_cluster():
    """Create a sample AlertCluster."""
    alerts = [
        NormalizedAlert(
            timestamp=datetime.utcnow(),
            fingerprint="fp-nonlearn-001",
            service="cart-service",
            severity="warning",
            description="Elevated error rate",
            labels={},
            validation_status=ValidationStatus.VALID,
        ),
    ]
    return AlertCluster.from_alerts(alerts, correlation_score=0.8)


@pytest.fixture
def unconfirmed_decision():
    """Create an unconfirmed Decision."""
    return Decision(
        decision_state=DecisionState.CLOSE,
        confidence=0.85,
        justification="Test decision",
        rules_applied=["rule_1"],
    )


@pytest.fixture
def confirmed_decision():
    """Create a confirmed Decision."""
    decision = Decision(
        decision_state=DecisionState.CLOSE,
        confidence=0.85,
        justification="Test decision",
        rules_applied=["rule_1"],
    )
    decision.confirm("test-user")
    return decision


@pytest.fixture
def rejected_decision():
    """Create a rejected Decision."""
    decision = Decision(
        decision_state=DecisionState.CLOSE,
        confidence=0.85,
        justification="Test decision",
        rules_applied=["rule_1"],
    )
    decision.reject("test-user")
    return decision


# ============================================================================
# EmbeddingAgent Non-Learning Tests
# ============================================================================

class TestEmbeddingAgentNonLearning:
    """Tests that EmbeddingAgent respects confirmation requirement."""
    
    @pytest.mark.asyncio
    async def test_persist_unconfirmed_raises_error(
        self, sample_cluster, unconfirmed_decision
    ):
        """
        Constitution Principle III: Unconfirmed decisions must NOT be embedded.
        """
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.persist_decision.side_effect = VectorStoreError(
            "Constitution Principle III: Only confirmed decisions can be persisted"
        )
        
        agent = EmbeddingAgent(vector_store=mock_vector_store)
        
        with pytest.raises(EmbeddingAgentError) as exc_info:
            await agent.persist_confirmed_decision(
                decision=unconfirmed_decision,
                cluster=sample_cluster,
            )
        
        assert "not confirmed" in str(exc_info.value).lower() or "constitution" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_persist_confirmed_succeeds(
        self, sample_cluster, confirmed_decision
    ):
        """
        Confirmed decisions should be persisted successfully.
        """
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.persist_decision.return_value = "point-123"
        
        agent = EmbeddingAgent(vector_store=mock_vector_store)
        
        point_id = await agent.persist_confirmed_decision(
            decision=confirmed_decision,
            cluster=sample_cluster,
        )
        
        assert point_id == "point-123"
        mock_vector_store.persist_decision.assert_called_once()


# ============================================================================
# VectorStore Non-Learning Tests
# ============================================================================

class TestVectorStoreNonLearning:
    """Tests that VectorStore enforces confirmation requirement."""
    
    def test_persist_unconfirmed_raises_error(
        self, sample_cluster, unconfirmed_decision
    ):
        """
        Constitution Principle III: VectorStore must reject unconfirmed decisions.
        """
        mock_qdrant = Mock()
        mock_embedding_client = Mock()
        mock_embedding_client.embed.return_value = [0.1] * 384
        
        store = VectorStore(
            qdrant_client=mock_qdrant,
            embedding_client=mock_embedding_client,
        )
        
        with pytest.raises(VectorStoreError) as exc_info:
            store.persist_decision(
                decision=unconfirmed_decision,
                cluster=sample_cluster,
            )
        
        assert "not confirmed" in str(exc_info.value).lower()
    
    def test_persist_confirmed_succeeds(
        self, sample_cluster, confirmed_decision
    ):
        """
        VectorStore should accept confirmed decisions.
        """
        mock_qdrant = Mock()
        mock_qdrant.upsert_point.return_value = "point-456"
        
        mock_embedding_client = Mock()
        mock_embedding_client.embed.return_value = [0.1] * 384
        
        store = VectorStore(
            qdrant_client=mock_qdrant,
            embedding_client=mock_embedding_client,
        )
        
        point_id = store.persist_decision(
            decision=confirmed_decision,
            cluster=sample_cluster,
        )
        
        # persist_decision returns a VectorEmbedding object
        assert isinstance(point_id, VectorEmbedding)
        assert point_id.source_decision_id == confirmed_decision.decision_id
        mock_qdrant.upsert_point.assert_called_once()
    
    def test_persist_rejected_raises_error(
        self, sample_cluster, rejected_decision
    ):
        """
        Constitution Principle III: Rejected decisions must NOT be embedded.
        """
        mock_qdrant = Mock()
        mock_embedding_client = Mock()
        mock_embedding_client.embed.return_value = [0.1] * 384
        
        store = VectorStore(
            qdrant_client=mock_qdrant,
            embedding_client=mock_embedding_client,
        )
        
        with pytest.raises(VectorStoreError) as exc_info:
            store.persist_decision(
                decision=rejected_decision,
                cluster=sample_cluster,
            )
        
        # Rejected decisions have is_confirmed = False
        assert "not confirmed" in str(exc_info.value).lower()


# ============================================================================
# ReportAgent Non-Learning Tests
# ============================================================================

class TestReportAgentNonLearning:
    """Tests that ReportAgent respects confirmation workflow."""
    
    @pytest.mark.asyncio
    async def test_handle_rejection_no_embedding(
        self, unconfirmed_decision
    ):
        """
        Rejection should NOT trigger embedding persistence.
        """
        mock_audit_logger = Mock()
        mock_embedding_agent = Mock(spec=EmbeddingAgent)
        
        agent = ReportAgent(
            audit_logger=mock_audit_logger,
            embedding_agent=mock_embedding_agent,
        )
        
        await agent.handle_rejection(
            decision=unconfirmed_decision,
            validator_id="reviewer-001",
        )
        
        # Embedding agent should NOT be called
        mock_embedding_agent.persist_confirmed_decision.assert_not_called()
        
        # Validation should be logged
        mock_audit_logger.log_validation.assert_called_once()
        call_args = mock_audit_logger.log_validation.call_args
        assert call_args.kwargs["approved"] is False
    
    @pytest.mark.asyncio
    async def test_handle_confirmation_triggers_embedding(
        self, sample_cluster, unconfirmed_decision
    ):
        """
        Confirmation should trigger embedding persistence.
        """
        mock_audit_logger = Mock()
        mock_embedding_agent = Mock(spec=EmbeddingAgent)
        mock_embedding_agent.persist_confirmed_decision = AsyncMock(
            return_value="point-789"
        )
        
        agent = ReportAgent(
            audit_logger=mock_audit_logger,
            embedding_agent=mock_embedding_agent,
        )
        
        await agent.handle_confirmation(
            decision=unconfirmed_decision,
            cluster=sample_cluster,
            validator_id="reviewer-001",
        )
        
        # Embedding agent SHOULD be called
        mock_embedding_agent.persist_confirmed_decision.assert_called_once()
        
        # Validation and embedding should be logged
        mock_audit_logger.log_validation.assert_called_once()
        mock_audit_logger.log_embedding_created.assert_called_once()


# ============================================================================
# Decision Model Non-Learning Tests
# ============================================================================

class TestDecisionModelNonLearning:
    """Tests for Decision model confirmation state."""
    
    def test_new_decision_is_not_confirmed(self):
        """New decisions must default to unconfirmed."""
        decision = Decision(
            decision_state=DecisionState.OBSERVE,
            confidence=0.7,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        assert decision.is_confirmed is False
    
    def test_confirm_sets_confirmed(self):
        """confirm() must set is_confirmed to True."""
        decision = Decision(
            decision_state=DecisionState.OBSERVE,
            confidence=0.7,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        decision.confirm("user-1")
        
        assert decision.is_confirmed is True
        assert decision.validated_by == "user-1"
    
    def test_reject_keeps_unconfirmed(self):
        """reject() must keep is_confirmed as False."""
        decision = Decision(
            decision_state=DecisionState.OBSERVE,
            confidence=0.7,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        decision.reject("user-1")
        
        assert decision.is_confirmed is False
