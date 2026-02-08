import pytest
from unittest.mock import MagicMock, patch
from src.services.semantic_recovery_service import SemanticRecoveryService
from src.models.cluster import AlertCluster
from src.models.decision import DecisionState
from src.rules.decision_rules import RuleResult
from datetime import datetime

@pytest.fixture
def mock_cluster():
    cluster = MagicMock(spec=AlertCluster)
    cluster.cluster_id = "test-cluster-id"
    cluster.primary_service = "payment-gateway"
    alert = MagicMock()
    alert.description = "High latency in payment processing"
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
    
    # Mocking Semantica components
    with patch.object(service.ner_extractor, 'extract', return_value=[{"text": "payment-gateway", "label": "SERVICE"}]):
        with patch.object(service, '_query_knowledge_graph', return_value={
            "state": DecisionState.OBSERVE,
            "confidence": 0.85
        }):
            result = await service.recover(mock_cluster, 0.40)
            
            assert result is not None
            assert result.decision_state == DecisionState.OBSERVE
            assert result.confidence == 0.85
            assert "semantica_recovery" in result.rule_id

@pytest.mark.asyncio
async def test_recover_cache_mechanism(mock_cluster):
    service = SemanticRecoveryService(threshold=0.60)
    
    with patch.object(service.ner_extractor, 'extract', return_value=[]) as mock_extract:
        with patch.object(service, '_query_knowledge_graph', return_value={
            "state": DecisionState.CLOSE,
            "confidence": 0.95
        }) as mock_query:
            # First call - should hit the "graph"
            res1 = await service.recover(mock_cluster, 0.40)
            assert res1.confidence == 0.95
            assert mock_query.call_count == 1
            
            # Second call - should hit the cache
            res2 = await service.recover(mock_cluster, 0.40)
            assert res2.confidence == 0.95
            assert mock_query.call_count == 1 # Still 1

@pytest.mark.asyncio
async def test_recover_empty_graph_return(mock_cluster):
    service = SemanticRecoveryService(threshold=0.60)
    
    with patch.object(service.ner_extractor, 'extract', return_value=[]):
        with patch.object(service, '_query_knowledge_graph', return_value=None):
            result = await service.recover(mock_cluster, 0.40)
            assert result is None

@pytest.mark.asyncio
async def test_recover_malformed_graph_return(mock_cluster):
    service = SemanticRecoveryService(threshold=0.60)
    
    with patch.object(service.ner_extractor, 'extract', return_value=[]):
        # Simulate malformed return that might cause an exception
        with patch.object(service, '_query_knowledge_graph', side_effect=ValueError("Malformed graph data")):
            result = await service.recover(mock_cluster, 0.40)
            assert result is None
