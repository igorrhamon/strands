import pytest
from unittest.mock import MagicMock, patch
from src.agents.decision_engine import DecisionEngine
from src.models.cluster import AlertCluster
from src.models.decision import DecisionState
from src.rules.decision_rules import RuleResult
from src.rules.decision_rules import RuleEngine

@pytest.fixture
def mock_cluster():
    cluster = MagicMock(spec=AlertCluster)
    cluster.cluster_id = "test-cluster-id"
    cluster.primary_service = "auth-service"
    cluster.primary_severity = "critical"
    cluster.alert_count = 5
    cluster.correlation_score = 0.9
    alert = MagicMock()
    alert.description = "Multiple failed login attempts"
    cluster.alerts = [alert]
    return cluster

@pytest.mark.asyncio
async def test_decision_engine_redirects_to_semantica_on_low_confidence(mock_cluster):
    # Setup RuleEngine to return low confidence
    mock_rule_engine = MagicMock(spec=RuleEngine)
    mock_rule_engine.evaluate.return_value = (
        RuleResult(decision_state=DecisionState.OBSERVE, confidence=0.30, rule_id="low_conf_rule", justification="Low confidence"),
        ["low_conf_rule"]
    )

    engine = DecisionEngine(rule_engine=mock_rule_engine, llm_fallback_threshold=0.60)

    # Mock SemanticRecoveryService to succeed
    with patch.object(engine._semantic_recovery, 'recover') as mock_recover:
        mock_recover.return_value = RuleResult(
            decision_state=DecisionState.ESCALATE,
            confidence=0.90,
            rule_id="semantica_recovery",
            justification="Recovered via Semantica"
        )

        decision = await engine.decide(mock_cluster, {}, [])

        assert decision.decision_state == DecisionState.ESCALATE
        assert decision.confidence == 0.90
        assert decision.llm_contribution is False # Should be False because it was semantic recovery
        mock_recover.assert_called_once()

@pytest.mark.asyncio
async def test_decision_engine_falls_back_to_llm_if_semantica_fails(mock_cluster):
    # Setup RuleEngine to return low confidence
    mock_rule_engine = MagicMock(spec=RuleEngine)
    mock_rule_engine.evaluate.return_value = (
        RuleResult(decision_state=DecisionState.OBSERVE, confidence=0.30, rule_id="low_conf_rule", justification="Low confidence"),
        ["low_conf_rule"]
    )

    engine = DecisionEngine(rule_engine=mock_rule_engine, llm_fallback_threshold=0.60)

    # Mock SemanticRecoveryService to fail (return None)
    with patch.object(engine._semantic_recovery, 'recover', return_value=None):
        # Mock LLM fallback
        with patch.object(engine, '_invoke_llm_fallback') as mock_llm:
            mock_llm.return_value = RuleResult(
                decision_state=DecisionState.MANUAL_REVIEW,
                confidence=0.70,
                rule_id="llm_fallback",
                justification="LLM fallback"
            )

            decision = await engine.decide(mock_cluster, {}, [])

            assert decision.decision_state == DecisionState.MANUAL_REVIEW
            assert decision.llm_contribution is True
            mock_llm.assert_called_once()
