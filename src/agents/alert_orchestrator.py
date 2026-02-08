"""
Alert Orchestrator - Main Workflow Coordinator

Coordinates the full alert processing pipeline:
1. Alert Collection & Correlation
2. Metric Analysis
3. Decision Generation (with Semantic Recovery)
4. Report & Audit
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from src.models.alert import Alert
from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend
from src.models.decision import Decision, SemanticEvidence
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.decision_engine import DecisionEngine
from src.agents.report_agent import ReportAgent
from src.utils.audit_logger import AuditLogger
from src.utils.error_handling import TimeoutError as ExternalTimeoutError

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Raised when orchestrator fails."""
    pass


class OrchestratorConfig:
    """Configuration for the orchestrator."""
    
    def __init__(
        self,
        timeout_seconds: float = 30.0,
        enable_metrics: bool = True,
        enable_semantic: bool = True,
        enable_llm_fallback: bool = True,
        auto_persist: bool = True,
    ):
        self.timeout_seconds = timeout_seconds
        self.enable_metrics = enable_metrics
        self.enable_semantic = enable_semantic
        self.enable_llm_fallback = enable_llm_fallback
        self.auto_persist = auto_persist


class AlertOrchestrator:
    """
    Main orchestrator for the alert decision pipeline.
    
    Pipeline: AlertCorrelation → MetricsAnalysis → DecisionEngine (SemanticRecovery) → Report
    """
    
    AGENT_NAME = "AlertOrchestrator"
    VERSION = "1.0.0"
    
    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        correlation_agent: Optional[AlertCorrelationAgent] = None,
        metrics_agent: Optional[MetricsAnalysisAgent] = None,
        decision_engine: Optional[DecisionEngine] = None,
        report_agent: Optional[ReportAgent] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self._config = config or OrchestratorConfig()
        self._correlation = correlation_agent or AlertCorrelationAgent()
        self._metrics = metrics_agent or MetricsAnalysisAgent()
        self._decision = decision_engine or DecisionEngine(
            llm_enabled=self._config.enable_llm_fallback
        )
        self._report = report_agent or ReportAgent()
        self._audit = audit_logger or AuditLogger()
        
        logger.info(f"[{self.AGENT_NAME}] Initialized with config: {vars(self._config)}")
    
    async def process_alerts(
        self,
        alerts: list[Alert],
        time_window_minutes: int = 5,
    ) -> list[dict]:
        """Process a batch of alerts through the full pipeline."""
        logger.info(f"[{self.AGENT_NAME}] Processing {len(alerts)} alerts")
        
        start_time = datetime.now(timezone.utc)
        
        try:
            clusters = await self._run_with_timeout(
                self._correlation.correlate(
                    alerts=alerts,
                    time_window_minutes=time_window_minutes,
                ),
                "correlation",
            )
            
            reports = []
            for cluster in clusters:
                try:
                    report = await self._process_cluster(cluster)
                    reports.append(report)
                except Exception as e:
                    logger.error(f"[{self.AGENT_NAME}] Cluster {cluster.cluster_id} failed: {error}")
                    reports.append(self._create_error_report(cluster, e))
            
            return reports
        
        except (asyncio.TimeoutError, ExternalTimeoutError):
            raise OrchestratorError(f"Pipeline timeout after {self._config.timeout_seconds}s")
    
    async def _process_cluster(self, cluster: AlertCluster) -> dict:
        """Process a single cluster through the decision pipeline."""
        trends: dict[str, MetricTrend] = {}
        if self._config.enable_metrics:
            try:
                trends = await self._run_with_timeout(
                    self._metrics.analyze_cluster(cluster=cluster),
                    "metrics",
                )
            except Exception as e:
                logger.warning(f"[{self.AGENT_NAME}] Metrics analysis failed: {e}")
        
        # Semantic context is now handled INSIDE DecisionEngine via SemanticRecoveryService
        semantic_evidence: list[SemanticEvidence] = []
        
        decision = await self._run_with_timeout(
            self._decision.decide(
                cluster=cluster,
                trends=trends,
                semantic_evidence=semantic_evidence,
            ),
            "decision",
        )
        
        report = await self._report.generate_report(
            decision=decision,
            cluster=cluster,
            trends=trends,
        )
        
        if self._config.auto_persist:
            self._report.persist_decision(
                decision=decision,
                cluster=cluster,
            )
        
        return report
    
    async def _run_with_timeout(self, coro, step_name: str):
        try:
            return await asyncio.wait_for(coro, timeout=self._config.timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(f"[{self.AGENT_NAME}] Step '{step_name}' timed out")
            raise
    
    def _create_error_report(self, cluster: AlertCluster, error: Exception) -> dict:
        return {
            "report_type": "error",
            "cluster_id": cluster.cluster_id,
            "error": str(error),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "service": cluster.primary_service,
                "severity": cluster.primary_severity,
                "alert_count": cluster.alert_count,
                "status": "failed",
            },
        }
    
    async def confirm_decision(self, decision: Decision, cluster: AlertCluster, validator_id: str) -> None:
        await self._report.handle_confirmation(decision=decision, cluster=cluster, validator_id=validator_id)
    
    async def reject_decision(self, decision: Decision, validator_id: str) -> None:
        await self._report.handle_rejection(decision=decision, validator_id=validator_id)

ORCHESTRATOR_TOOL = {
    "name": "process_alerts",
    "description": "Process alerts through the full decision pipeline",
    "parameters": {
        "type": "object",
        "properties": {
            "time_window_minutes": {
                "type": "integer",
                "description": "Time window for alert correlation",
                "default": 5,
            },
        },
        "required": [],
    },
}
