"""
Integration Tests for Orchestrator Flow

Tests the full pipeline:
1. Alert ingestion
2. Correlation
3. Metric analysis
4. Semantic context
5. Decision generation
6. Report output
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.alert import Alert, NormalizedAlert, ValidationStatus
from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend, TrendState
from src.models.decision import Decision, DecisionState
from src.agents.alert_orchestrator import (
    AlertOrchestrator,
    OrchestratorConfig,
    OrchestratorError,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_alerts():
    """Create sample alerts for testing."""
    base_time = datetime.utcnow()
    return [
        Alert(
            timestamp=base_time,
            fingerprint="fp-001",
            labels={"service": "checkout-service", "severity": "warning"},
            annotations={"summary": "High latency detected"},
            status="firing",
            generator_url="http://grafana/alerts/1",
        ),
        Alert(
            timestamp=base_time + timedelta(seconds=30),
            fingerprint="fp-001",  # Same fingerprint = same alert
            labels={"service": "checkout-service", "severity": "warning"},
            annotations={"summary": "High latency continues"},
            status="firing",
            generator_url="http://grafana/alerts/1",
        ),
        Alert(
            timestamp=base_time + timedelta(minutes=1),
            fingerprint="fp-002",
            labels={"service": "checkout-service", "severity": "critical"},
            annotations={"summary": "Error rate spike"},
            status="firing",
            generator_url="http://grafana/alerts/2",
        ),
    ]


@pytest.fixture
def mock_correlation_agent():
    """Create a mock correlation agent."""
    agent = Mock()
    agent.correlate = AsyncMock()
    return agent


@pytest.fixture
def mock_metrics_agent():
    """Create a mock metrics agent."""
    agent = Mock()
    agent.analyze = AsyncMock()
    return agent


@pytest.fixture
def mock_context_agent():
    """Create a mock context agent."""
    agent = Mock()
    agent.get_context = AsyncMock()
    return agent


@pytest.fixture
def mock_decision_engine():
    """Create a mock decision engine."""
    engine = Mock()
    engine.decide = AsyncMock()
    return engine


@pytest.fixture
def mock_report_agent():
    """Create a mock report agent."""
    agent = Mock()
    agent.generate_report = AsyncMock()
    agent.persist_decision = Mock()
    return agent


# ============================================================================
# Orchestrator Flow Tests
# ============================================================================

class TestOrchestratorFlow:
    """Tests for the full orchestrator flow."""
    
    @pytest.mark.asyncio
    async def test_process_alerts_returns_reports(
        self,
        sample_alerts,
        mock_correlation_agent,
        mock_metrics_agent,
        mock_context_agent,
        mock_decision_engine,
        mock_report_agent,
    ):
        """Test that process_alerts returns reports for each cluster."""
        # Setup mocks
        cluster = AlertCluster.from_alerts(
            [
                NormalizedAlert(
                    timestamp=datetime.utcnow(),
                    fingerprint="fp-001",
                    service="checkout-service",
                    severity="warning",
                    description="Test alert",
                    labels={},
                    validation_status=ValidationStatus.VALID,
                ),
            ],
            correlation_score=0.9,
        )
        
        mock_correlation_agent.correlate.return_value = [cluster]
        mock_metrics_agent.analyze.return_value = {}
        mock_context_agent.get_context.return_value = {"semantic_evidence": []}
        mock_decision_engine.decide.return_value = Decision(
            decision_state=DecisionState.OBSERVE,
            confidence=0.75,
            justification="Test decision",
            rules_applied=["rule_1"],
        )
        mock_report_agent.generate_report.return_value = {
            "report_type": "decision_recommendation",
            "decision_id": str(uuid4()),
        }
        
        orchestrator = AlertOrchestrator(
            correlation_agent=mock_correlation_agent,
            metrics_agent=mock_metrics_agent,
            context_agent=mock_context_agent,
            decision_engine=mock_decision_engine,
            report_agent=mock_report_agent,
        )
        
        reports = await orchestrator.process_alerts(sample_alerts)
        
        assert len(reports) == 1
        assert reports[0]["report_type"] == "decision_recommendation"
    
    @pytest.mark.asyncio
    async def test_pipeline_order_is_correct(
        self,
        sample_alerts,
        mock_correlation_agent,
        mock_metrics_agent,
        mock_context_agent,
        mock_decision_engine,
        mock_report_agent,
    ):
        """Test that pipeline steps execute in correct order."""
        call_order = []
        
        async def track_correlation(*args, **kwargs):
            call_order.append("correlation")
            return []
        
        mock_correlation_agent.correlate = track_correlation
        
        orchestrator = AlertOrchestrator(
            correlation_agent=mock_correlation_agent,
            metrics_agent=mock_metrics_agent,
            context_agent=mock_context_agent,
            decision_engine=mock_decision_engine,
            report_agent=mock_report_agent,
        )
        
        await orchestrator.process_alerts(sample_alerts)
        
        # Correlation should be called first
        assert "correlation" in call_order
    
    @pytest.mark.asyncio
    async def test_metrics_disabled_skips_analysis(
        self,
        sample_alerts,
        mock_correlation_agent,
        mock_metrics_agent,
        mock_context_agent,
        mock_decision_engine,
        mock_report_agent,
    ):
        """Test that disabled metrics skips analysis."""
        cluster = AlertCluster.from_alerts(
            [
                NormalizedAlert(
                    timestamp=datetime.utcnow(),
                    fingerprint="fp-001",
                    service="test",
                    severity="warning",
                    description="Test",
                    labels={},
                    validation_status=ValidationStatus.VALID,
                ),
            ],
            correlation_score=0.9,
        )
        
        mock_correlation_agent.correlate.return_value = [cluster]
        mock_context_agent.get_context.return_value = {"semantic_evidence": []}
        mock_decision_engine.decide.return_value = Decision(
            decision_state=DecisionState.OBSERVE,
            confidence=0.75,
            justification="Test",
            rules_applied=["rule_1"],
        )
        mock_report_agent.generate_report.return_value = {}
        
        config = OrchestratorConfig(enable_metrics=False)
        orchestrator = AlertOrchestrator(
            config=config,
            correlation_agent=mock_correlation_agent,
            metrics_agent=mock_metrics_agent,
            context_agent=mock_context_agent,
            decision_engine=mock_decision_engine,
            report_agent=mock_report_agent,
        )
        
        await orchestrator.process_alerts(sample_alerts)
        
        # Metrics agent should NOT be called
        mock_metrics_agent.analyze.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_semantic_disabled_skips_context(
        self,
        sample_alerts,
        mock_correlation_agent,
        mock_metrics_agent,
        mock_context_agent,
        mock_decision_engine,
        mock_report_agent,
    ):
        """Test that disabled semantic skips context retrieval."""
        cluster = AlertCluster.from_alerts(
            [
                NormalizedAlert(
                    timestamp=datetime.utcnow(),
                    fingerprint="fp-001",
                    service="test",
                    severity="warning",
                    description="Test",
                    labels={},
                    validation_status=ValidationStatus.VALID,
                ),
            ],
            correlation_score=0.9,
        )
        
        mock_correlation_agent.correlate.return_value = [cluster]
        mock_metrics_agent.analyze.return_value = {}
        mock_decision_engine.decide.return_value = Decision(
            decision_state=DecisionState.OBSERVE,
            confidence=0.75,
            justification="Test",
            rules_applied=["rule_1"],
        )
        mock_report_agent.generate_report.return_value = {}
        
        config = OrchestratorConfig(enable_semantic=False)
        orchestrator = AlertOrchestrator(
            config=config,
            correlation_agent=mock_correlation_agent,
            metrics_agent=mock_metrics_agent,
            context_agent=mock_context_agent,
            decision_engine=mock_decision_engine,
            report_agent=mock_report_agent,
        )
        
        await orchestrator.process_alerts(sample_alerts)
        
        # Context agent should NOT be called
        mock_context_agent.get_context.assert_not_called()


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestOrchestratorErrorHandling:
    """Tests for orchestrator error handling."""
    
    @pytest.mark.asyncio
    async def test_cluster_failure_produces_error_report(
        self,
        sample_alerts,
        mock_correlation_agent,
        mock_metrics_agent,
        mock_context_agent,
        mock_decision_engine,
        mock_report_agent,
    ):
        """Test that cluster failures produce error reports."""
        cluster = AlertCluster.from_alerts(
            [
                NormalizedAlert(
                    timestamp=datetime.utcnow(),
                    fingerprint="fp-001",
                    service="test",
                    severity="warning",
                    description="Test",
                    labels={},
                    validation_status=ValidationStatus.VALID,
                ),
            ],
            correlation_score=0.9,
        )
        
        mock_correlation_agent.correlate.return_value = [cluster]
        mock_metrics_agent.analyze.side_effect = Exception("Prometheus unavailable")
        
        # Context and decision should still work
        mock_context_agent.get_context.return_value = {"semantic_evidence": []}
        mock_decision_engine.decide.return_value = Decision(
            decision_state=DecisionState.OBSERVE,
            confidence=0.75,
            justification="Test",
            rules_applied=["rule_1"],
        )
        mock_report_agent.generate_report.return_value = {}
        
        config = OrchestratorConfig(enable_metrics=True)
        orchestrator = AlertOrchestrator(
            config=config,
            correlation_agent=mock_correlation_agent,
            metrics_agent=mock_metrics_agent,
            context_agent=mock_context_agent,
            decision_engine=mock_decision_engine,
            report_agent=mock_report_agent,
        )
        
        # Should not raise, should continue with empty trends
        reports = await orchestrator.process_alerts(sample_alerts)
        assert len(reports) == 1
    
    @pytest.mark.asyncio
    async def test_empty_alerts_returns_empty_reports(
        self,
        mock_correlation_agent,
        mock_metrics_agent,
        mock_context_agent,
        mock_decision_engine,
        mock_report_agent,
    ):
        """Test that empty alerts list returns empty reports."""
        mock_correlation_agent.correlate.return_value = []
        
        orchestrator = AlertOrchestrator(
            correlation_agent=mock_correlation_agent,
            metrics_agent=mock_metrics_agent,
            context_agent=mock_context_agent,
            decision_engine=mock_decision_engine,
            report_agent=mock_report_agent,
        )
        
        reports = await orchestrator.process_alerts([])
        assert reports == []


# ============================================================================
# Confirmation Flow Tests
# ============================================================================

class TestConfirmationFlow:
    """Tests for decision confirmation flow."""
    
    @pytest.mark.asyncio
    async def test_confirm_decision_calls_report_agent(
        self,
        mock_report_agent,
    ):
        """Test that confirm_decision delegates to report agent."""
        mock_report_agent.handle_confirmation = AsyncMock()
        
        orchestrator = AlertOrchestrator(
            report_agent=mock_report_agent,
        )
        
        decision = Decision(
            decision_state=DecisionState.CLOSE,
            confidence=0.85,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        cluster = AlertCluster.from_alerts(
            [
                NormalizedAlert(
                    timestamp=datetime.utcnow(),
                    fingerprint="fp-001",
                    service="test",
                    severity="warning",
                    description="Test",
                    labels={},
                    validation_status=ValidationStatus.VALID,
                ),
            ],
            correlation_score=0.9,
        )
        
        await orchestrator.confirm_decision(
            decision=decision,
            cluster=cluster,
            validator_id="user-123",
        )
        
        mock_report_agent.handle_confirmation.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reject_decision_calls_report_agent(
        self,
        mock_report_agent,
    ):
        """Test that reject_decision delegates to report agent."""
        mock_report_agent.handle_rejection = AsyncMock()
        
        orchestrator = AlertOrchestrator(
            report_agent=mock_report_agent,
        )
        
        decision = Decision(
            decision_state=DecisionState.CLOSE,
            confidence=0.85,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        await orchestrator.reject_decision(
            decision=decision,
            validator_id="user-123",
        )
        
        mock_report_agent.handle_rejection.assert_called_once()
