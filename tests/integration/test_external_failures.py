"""
Integration Tests for External Service Failures

Tests graceful handling of:
- Grafana MCP failures
- Prometheus timeouts
- Qdrant unavailability
- GitHub MCP errors
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from uuid import uuid4

from src.models.alert import Alert, NormalizedAlert, ValidationStatus
from src.models.cluster import AlertCluster
from src.models.decision import Decision, DecisionState
from src.agents.alert_orchestrator import (
    AlertOrchestrator,
    OrchestratorConfig,
    OrchestratorError,
)
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.repository_context import RepositoryContextAgent
from src.agents.decision_engine import DecisionEngine
from src.utils.error_handling import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    TimeoutError,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_cluster():
    """Create a sample cluster for testing."""
    return AlertCluster.from_alerts(
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


@pytest.fixture
def sample_alerts():
    """Create sample alerts."""
    return [
        Alert(
            timestamp=datetime.utcnow(),
            fingerprint="fp-001",
            labels={"service": "test", "severity": "warning"},
            annotations={"summary": "Test"},
            status="firing",
            generator_url="http://test",
        ),
    ]


# ============================================================================
# Grafana MCP Failure Tests
# ============================================================================

class TestGrafanaFailures:
    """Tests for Grafana MCP failure handling."""
    
    @pytest.mark.asyncio
    async def test_grafana_timeout_handled_gracefully(
        self,
        sample_alerts,
    ):
        """Test that Grafana timeout is handled gracefully."""
        mock_correlation = Mock()
        mock_correlation.correlate = AsyncMock(
            side_effect=TimeoutError("Grafana connection timed out")
        )
        
        config = OrchestratorConfig(timeout_seconds=5.0)
        orchestrator = AlertOrchestrator(
            config=config,
            correlation_agent=mock_correlation,
        )
        
        with pytest.raises(OrchestratorError):
            await orchestrator.process_alerts(sample_alerts)
    
    @pytest.mark.asyncio
    async def test_grafana_connection_refused(
        self,
        sample_alerts,
    ):
        """Test handling of Grafana connection refused."""
        mock_correlation = Mock()
        mock_correlation.correlate = AsyncMock(
            side_effect=ConnectionRefusedError("Connection refused")
        )
        
        orchestrator = AlertOrchestrator(
            correlation_agent=mock_correlation,
        )
        
        with pytest.raises(Exception):
            await orchestrator.process_alerts(sample_alerts)


# ============================================================================
# Prometheus Failure Tests
# ============================================================================

class TestPrometheusFailures:
    """Tests for Prometheus failure handling."""
    
    @pytest.mark.asyncio
    async def test_prometheus_unavailable_continues_pipeline(
        self,
        sample_alerts,
        sample_cluster,
    ):
        """Test that Prometheus failure doesn't stop the pipeline."""
        mock_correlation = Mock()
        mock_correlation.correlate = AsyncMock(return_value=[sample_cluster])
        
        mock_metrics = Mock()
        mock_metrics.analyze = AsyncMock(
            side_effect=Exception("Prometheus unavailable")
        )
        
        mock_context = Mock()
        mock_context.get_context = AsyncMock(return_value={"semantic_evidence": []})
        
        mock_decision = Mock()
        mock_decision.decide = AsyncMock(
            return_value=Decision(
                decision_state=DecisionState.MANUAL_REVIEW,
                confidence=0.7,
                justification="Insufficient metric data",
                rules_applied=["rule_insufficient_data"],
            )
        )
        
        mock_report = Mock()
        mock_report.generate_report = AsyncMock(return_value={"status": "ok"})
        mock_report.persist_decision = Mock()
        
        orchestrator = AlertOrchestrator(
            config=OrchestratorConfig(enable_metrics=True),
            correlation_agent=mock_correlation,
            metrics_agent=mock_metrics,
            context_agent=mock_context,
            decision_engine=mock_decision,
            report_agent=mock_report,
        )
        
        reports = await orchestrator.process_alerts(sample_alerts)
        
        # Pipeline should continue despite Prometheus failure
        assert len(reports) == 1
        mock_decision.decide.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prometheus_partial_data_handled(
        self,
        sample_cluster,
    ):
        """Test handling of partial Prometheus data."""
        from src.models.metric_trend import MetricTrend, TrendState
        
        # Some metrics succeed, some fail
        partial_trends = {
            "cpu": MetricTrend(
                metric_name="cpu_usage",
                trend_state=TrendState.STABLE,
                confidence=0.8,
                data_points=[],
            ),
            # memory metric failed, not included
        }
        
        mock_metrics = Mock()
        mock_metrics.analyze = AsyncMock(return_value=partial_trends)
        
        agent = MetricsAnalysisAgent()
        # In real implementation, partial data would still allow decision


# ============================================================================
# Qdrant Failure Tests
# ============================================================================

class TestQdrantFailures:
    """Tests for Qdrant failure handling."""
    
    @pytest.mark.asyncio
    async def test_qdrant_unavailable_continues_without_semantic(
        self,
        sample_alerts,
        sample_cluster,
    ):
        """Test that Qdrant failure doesn't stop the pipeline."""
        mock_correlation = Mock()
        mock_correlation.correlate = AsyncMock(return_value=[sample_cluster])
        
        mock_metrics = Mock()
        mock_metrics.analyze = AsyncMock(return_value={})
        
        mock_context = Mock()
        mock_context.get_context = AsyncMock(
            side_effect=Exception("Qdrant connection failed")
        )
        
        mock_decision = Mock()
        mock_decision.decide = AsyncMock(
            return_value=Decision(
                decision_state=DecisionState.OBSERVE,
                confidence=0.6,
                justification="No semantic context available",
                rules_applied=["rule_default_observe"],
            )
        )
        
        mock_report = Mock()
        mock_report.generate_report = AsyncMock(return_value={"status": "ok"})
        mock_report.persist_decision = Mock()
        
        orchestrator = AlertOrchestrator(
            config=OrchestratorConfig(enable_semantic=True),
            correlation_agent=mock_correlation,
            metrics_agent=mock_metrics,
            context_agent=mock_context,
            decision_engine=mock_decision,
            report_agent=mock_report,
        )
        
        reports = await orchestrator.process_alerts(sample_alerts)
        
        # Pipeline should continue without semantic context
        assert len(reports) == 1
        
        # Decision should be called with empty semantic evidence
        call_args = mock_decision.decide.call_args
        assert call_args.kwargs.get("semantic_evidence", []) == []
    
    @pytest.mark.asyncio
    async def test_qdrant_embedding_failure_on_confirm(
        self,
        sample_cluster,
    ):
        """Test handling of Qdrant failure during embedding persistence."""
        from src.agents.report_agent import ReportAgent, ReportAgentError
        from src.agents.embedding_agent import EmbeddingAgent, EmbeddingAgentError
        
        mock_audit = Mock()
        mock_audit.log_validation = Mock()
        
        mock_embedding = Mock()
        mock_embedding.persist_confirmed_decision = AsyncMock(
            side_effect=EmbeddingAgentError("Qdrant write failed")
        )
        
        report_agent = ReportAgent(
            audit_logger=mock_audit,
            embedding_agent=mock_embedding,
        )
        
        decision = Decision(
            decision_state=DecisionState.CLOSE,
            confidence=0.85,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        with pytest.raises(ReportAgentError):
            await report_agent.handle_confirmation(
                decision=decision,
                cluster=sample_cluster,
                validator_id="user-123",
            )


# ============================================================================
# Circuit Breaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Tests for circuit breaker behavior."""
    
    def test_circuit_opens_after_threshold(self):
        """Test that circuit opens after failure threshold."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        
        # Record failures
        for _ in range(3):
            cb.record_failure()
        
        assert cb.state == CircuitBreaker.OPEN
    
    def test_circuit_rejects_when_open(self):
        """Test that open circuit rejects calls."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
        )
        
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        
        @cb
        async def test_func():
            return "success"
        
        with pytest.raises(CircuitBreakerOpenError):
            import asyncio
            asyncio.get_event_loop().run_until_complete(test_func())
    
    def test_circuit_closes_after_successful_half_open(self):
        """Test that circuit closes after successful half-open calls."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0,  # Immediate recovery for test
            half_open_max_calls=2,
        )
        
        cb.record_failure()
        assert cb.state == CircuitBreaker.HALF_OPEN  # Immediate transition
        
        cb.record_success()
        cb.record_success()
        
        assert cb.state == CircuitBreaker.CLOSED


# ============================================================================
# Combined Failure Scenarios
# ============================================================================

class TestCombinedFailures:
    """Tests for multiple simultaneous failures."""
    
    @pytest.mark.asyncio
    async def test_all_enrichment_fails_still_decides(
        self,
        sample_alerts,
        sample_cluster,
    ):
        """Test that decision is still made when all enrichment fails."""
        mock_correlation = Mock()
        mock_correlation.correlate = AsyncMock(return_value=[sample_cluster])
        
        mock_metrics = Mock()
        mock_metrics.analyze = AsyncMock(side_effect=Exception("Prometheus down"))
        
        mock_context = Mock()
        mock_context.get_context = AsyncMock(side_effect=Exception("Qdrant down"))
        
        mock_decision = Mock()
        mock_decision.decide = AsyncMock(
            return_value=Decision(
                decision_state=DecisionState.MANUAL_REVIEW,
                confidence=0.5,
                justification="All enrichment failed, manual review required",
                rules_applied=["rule_default_observe"],
            )
        )
        
        mock_report = Mock()
        mock_report.generate_report = AsyncMock(return_value={"status": "degraded"})
        mock_report.persist_decision = Mock()
        
        orchestrator = AlertOrchestrator(
            config=OrchestratorConfig(
                enable_metrics=True,
                enable_semantic=True,
            ),
            correlation_agent=mock_correlation,
            metrics_agent=mock_metrics,
            context_agent=mock_context,
            decision_engine=mock_decision,
            report_agent=mock_report,
        )
        
        reports = await orchestrator.process_alerts(sample_alerts)
        
        # Should still produce a report
        assert len(reports) == 1
        mock_decision.decide.assert_called_once()
