import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.services.semantic_recovery_service import SemanticRecoveryService
from src.models.cluster import AlertCluster
from src.models.decision import DecisionState
from src.rules.decision_rules import RuleResult

@pytest.fixture
def mock_cluster():
    cluster = MagicMock(spec=AlertCluster)
    cluster.cluster_id = "test-cluster-id"
    cluster.primary_service = "auth-service"
    alert = MagicMock()
    alert.description = "Multiple failed login attempts"
    cluster.alerts = [alert]
    return cluster

@pytest.mark.asyncio
async def test_recover_high_confidence_skips(mock_cluster):
    service = SemanticRecoveryService(threshold=0.60)
    result = await service.recover(mock_cluster, 0.80)
    assert result is None

@pytest.mark.asyncio
async def test_recover_low_confidence_calls_semantica(mock_cluster):
    service = SemanticRecoveryService(threshold=0.60)

    with patch.object(service.ner_extractor, 'extract', return_value=['auth-service']):
        with patch.object(service, '_get_github_context', new_callable=AsyncMock) as mock_github:
            mock_github.return_value = {"full_name": "igorrhamon/auth-service"}
            with patch.object(service, '_query_knowledge_graph', return_value={
                "state": DecisionState.OBSERVE,
                "confidence": 0.85
            }):
                result = await service.recover(mock_cluster, 0.40)

                assert result is not None
                assert result.decision_state == DecisionState.OBSERVE
                assert "igorrhamon/auth-service" in result.justification

@pytest.mark.asyncio
async def test_recover_cache_mechanism(mock_cluster):
    service = SemanticRecoveryService(threshold=0.60)

    with patch.object(service.ner_extractor, 'extract', return_value=[]):
        with patch.object(service, '_get_github_context', new_callable=AsyncMock) as mock_github:
            mock_github.return_value = {}
            with patch.object(service, '_query_knowledge_graph', return_value={
                "state": DecisionState.CLOSE,
                "confidence": 0.95
            }) as mock_query:
                # First call
                await service.recover(mock_cluster, 0.40)
                assert mock_query.call_count == 1

                # Second call (cache hit)
                await service.recover(mock_cluster, 0.40)
                assert mock_query.call_count == 1

@pytest.mark.asyncio
async def test_recover_malformed_graph_return(mock_cluster):
    service = SemanticRecoveryService(threshold=0.60)

    with patch.object(service.ner_extractor, 'extract', return_value=[]):
        with patch.object(service, '_query_knowledge_graph', return_value={
            "state": "INVALID_STATE",
            "confidence": "not-a-float"
        }):
            result = await service.recover(mock_cluster, 0.40)
            assert result is None
