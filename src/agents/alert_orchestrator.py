"""
Alert Orchestrator - Main Workflow Coordinator

Coordinates the full alert processing pipeline:
1. Alert Collection & Correlation
2. Metric Analysis
3. Semantic Context Retrieval
4. Decision Generation
5. Report & Audit

This is the main entry point for the multi-agent system.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from src.models.alert import Alert, NormalizedAlert
from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend
from src.models.decision import Decision, SemanticEvidence
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.repository_context import RepositoryContextAgent
from src.agents.decision_engine import DecisionEngine
from src.agents.report_agent import ReportAgent
from src.utils.audit_logger import AuditLogger

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
    
    Pipeline: AlertCorrelation → MetricsAnalysis → RepositoryContext → DecisionEngine → Report
    
    Constitution Principles:
    - I: Human-in-the-Loop (decisions require confirmation)
    - II: Determinismo (rules before LLM)
    - III: Controle de Aprendizado (embeddings after confirmation only)
    - IV: Rastreabilidade (full audit trail)
    """
    
    AGENT_NAME = "AlertOrchestrator"
    VERSION = "1.0.0"
    
    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        correlation_agent: Optional[AlertCorrelationAgent] = None,
        metrics_agent: Optional[MetricsAnalysisAgent] = None,
        context_agent: Optional[RepositoryContextAgent] = None,
        decision_engine: Optional[DecisionEngine] = None,
        report_agent: Optional[ReportAgent] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize orchestrator with all agents.
        
        Args:
            config: Orchestrator configuration.
            correlation_agent: Agent for alert clustering.
            metrics_agent: Agent for trend analysis.
            context_agent: Agent for semantic context.
            decision_engine: Engine for generating decisions.
            report_agent: Agent for reports and persistence.
            audit_logger: Logger for audit trail.
        """
        self._config = config or OrchestratorConfig()
        self._correlation = correlation_agent or AlertCorrelationAgent()
        self._metrics = metrics_agent or MetricsAnalysisAgent()
        self._context = context_agent or RepositoryContextAgent()
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
        """
        Process a batch of alerts through the full pipeline.
        
        Args:
            alerts: Raw alerts to process.
            time_window_minutes: Time window for correlation.
        
        Returns:
            List of report dicts for each cluster.
        """
        logger.info(
            f"[{self.AGENT_NAME}] Processing {len(alerts)} alerts "
            f"(timeout: {self._config.timeout_seconds}s)"
        )
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Step 1: Correlate alerts into clusters
            clusters = await self._run_with_timeout(
                self._correlation.correlate(
                    alerts=alerts,
                    time_window_minutes=time_window_minutes,
                ),
                "correlation",
            )
            
            logger.info(
                f"[{self.AGENT_NAME}] Correlated into {len(clusters)} clusters"
            )
            
            # Step 2: Process each cluster
            reports = []
            for cluster in clusters:
                try:
                    report = await self._process_cluster(cluster)
                    reports.append(report)
                except Exception as e:
                    logger.error(
                        f"[{self.AGENT_NAME}] Cluster {cluster.cluster_id} failed: {e}"
                    )
                    reports.append(self._create_error_report(cluster, e))
            
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"[{self.AGENT_NAME}] Completed in {elapsed:.2f}s: "
                f"{len(reports)} reports generated"
            )
            
            return reports
        
        except asyncio.TimeoutError:
            raise OrchestratorError(
                f"Pipeline timeout after {self._config.timeout_seconds}s"
            )
    
    async def _process_cluster(self, cluster: AlertCluster) -> dict:
        """
        Process a single cluster through the decision pipeline.
        
        Args:
            cluster: Alert cluster to process.
        
        Returns:
            Report dict.
        """
        logger.info(
            f"[{self.AGENT_NAME}] Processing cluster {cluster.cluster_id}"
        )
        
        # Step 2a: Analyze metrics (if enabled)
        trends: dict[str, MetricTrend] = {}
        if self._config.enable_metrics:
            try:
                trends = await self._run_with_timeout(
                    self._metrics.analyze_cluster(cluster=cluster),
                    "metrics",
                )
            except Exception as e:
                logger.warning(
                    f"[{self.AGENT_NAME}] Metrics analysis failed: {e}"
                )
        
        # Step 2b: Get semantic context (if enabled)
        semantic_evidence: list[SemanticEvidence] = []
        if self._config.enable_semantic:
            try:
                context = await self._run_with_timeout(
                    self._context.get_context(
                        cluster=cluster,
                        # top_k=5,
                        # min_score=0.75,
                    ),
                    "semantic",
                )
                semantic_evidence = context.get("semantic_evidence", [])
            except Exception as e:
                logger.warning(
                    f"[{self.AGENT_NAME}] Semantic context failed: {e}"
                )
        
        # Step 2c: Generate decision
        decision = await self._run_with_timeout(
            self._decision.decide(
                cluster=cluster,
                trends=trends,
                semantic_evidence=semantic_evidence,
            ),
            "decision",
        )
        
        # Step 2d: Generate report
        report = await self._report.generate_report(
            decision=decision,
            cluster=cluster,
            trends=trends,
        )
        
        # Step 2e: Persist decision (if auto_persist)
        if self._config.auto_persist:
            self._report.persist_decision(
                decision=decision,
                cluster=cluster,
            )
        
        return report
    
    async def _run_with_timeout(
        self,
        coro,
        step_name: str,
    ):
        """
        Run a coroutine with the configured timeout.
        
        Args:
            coro: Coroutine to run.
            step_name: Name for logging.
        
        Returns:
            Result of the coroutine.
        """
        try:
            return await asyncio.wait_for(
                coro,
                timeout=self._config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"[{self.AGENT_NAME}] Step '{step_name}' timed out "
                f"after {self._config.timeout_seconds}s"
            )
            raise
    
    def _create_error_report(
        self,
        cluster: AlertCluster,
        error: Exception,
    ) -> dict:
        """
        Create an error report for a failed cluster.
        
        Args:
            cluster: Cluster that failed.
            error: Exception that occurred.
        
        Returns:
            Error report dict.
        """
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
    
    async def confirm_decision(
        self,
        decision: Decision,
        cluster: AlertCluster,
        validator_id: str,
    ) -> None:
        """
        Confirm a decision and persist embedding.
        
        Constitution Principle III: Embedding persistence only after confirmation.
        
        Args:
            decision: Decision to confirm.
            cluster: Associated cluster.
            validator_id: ID of human validator.
        """
        await self._report.handle_confirmation(
            decision=decision,
            cluster=cluster,
            validator_id=validator_id,
        )
        
        logger.info(
            f"[{self.AGENT_NAME}] Decision {decision.decision_id} confirmed "
            f"by {validator_id}"
        )
    
    async def reject_decision(
        self,
        decision: Decision,
        validator_id: str,
    ) -> None:
        """
        Reject a decision (no embedding persistence).
        
        Args:
            decision: Decision to reject.
            validator_id: ID of human validator.
        """
        await self._report.handle_rejection(
            decision=decision,
            validator_id=validator_id,
        )
        
        logger.info(
            f"[{self.AGENT_NAME}] Decision {decision.decision_id} rejected "
            f"by {validator_id}"
        )


# Strands agent tool definition
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
