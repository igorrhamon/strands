"""Alert Orchestrator Agent - coordinates the decision pipeline"""
from typing import List, Optional
import logging
from datetime import datetime, timezone, timedelta

from src.models.alert import Alert, NormalizedAlert
from src.models.cluster import AlertCluster
from src.models.metrics import MetricsAnalysisResult
from src.models.decision import Decision, DecisionState, DecisionTrace
from src.agents.alert_collector import AlertCollectorAgent
from src.agents.alert_normalizer import AlertNormalizerAgent
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.decision_engine import DecisionEngine
import asyncio
from src.agents.human_review import HumanReviewAgent
from src.config.settings import config
from src.state.incident_state_machine import IncidentStateMachine, IncidentState
from src.state.incident_registry import IncidentRegistry, IncidentSnapshot
from src.state.similarity_index import SimilarityIndex
from src.rules.runbook_resolver import RunbookResolver


logger = logging.getLogger(__name__)


class AlertOrchestratorAgent:
    """
    Orchestrator agent that coordinates the decision pipeline.
    
    Execution DAG:
    1. AlertCollectorAgent
    2. AlertNormalizerAgent
    3. AlertCorrelationAgent
    4. MetricsAnalysisAgent (parallel for each cluster)
    5. DecisionEngineAgent
    6. HumanReviewAgent (if required)
    
    Enforces deterministic execution and timeout policies.
    """
    
    def __init__(
        self,
        alert_collector: AlertCollectorAgent,
        alert_normalizer: AlertNormalizerAgent,
        alert_correlation: AlertCorrelationAgent,
        metrics_analysis: MetricsAnalysisAgent,
        decision_engine: DecisionEngine,
        human_review: HumanReviewAgent
    ):
        self.alert_collector = alert_collector
        self.alert_normalizer = alert_normalizer
        self.alert_correlation = alert_correlation
        self.metrics_analysis = metrics_analysis
        self.decision_engine = decision_engine
        self.human_review = human_review
        self.agent_name = "AlertOrchestratorAgent"
        self.state_machine = IncidentStateMachine()
        self.incident_registry = IncidentRegistry()
        self.similarity_index = SimilarityIndex()
        self.runbook_resolver = RunbookResolver()
    
    def run_pipeline(self) -> (List[Decision], List[DecisionTrace]):
        """Execute the complete decision pipeline
        
        Returns:
            Tuple of (List of Decision objects, List of DecisionTrace objects)
        """
        logger.info("=== Starting Alert Decision Pipeline ===")
        start_time = datetime.now(timezone.utc)
        
        try:
            # Step 1: Collect alerts
            logger.info("Step 1: Collecting alerts...")
            raw_alerts = self.alert_collector.collect_active_alerts()
            
            if not raw_alerts:
                logger.info("No active alerts found")
                return []
            
            # Step 2: Normalize alerts
            logger.info(f"Step 2: Normalizing {len(raw_alerts)} alerts...")
            normalized_alerts = self.alert_normalizer.normalize(raw_alerts)
            
            if not normalized_alerts:
                logger.warning("All alerts failed normalization")
                return []
            
            # Step 3: Correlate into clusters
            logger.info(f"Step 3: Correlating {len(normalized_alerts)} alerts...")
            clusters = self.alert_correlation.correlate(normalized_alerts)
            
            if not clusters:
                logger.info("No alert clusters formed")
                return []
            
            logger.info(f"Formed {len(clusters)} alert clusters")
            
            # Step 4-6: Process each cluster
            decisions = []
            traces = []
            for cluster in clusters:
                try:
                    decision, trace = self._process_cluster(cluster)
                    if decision:
                        decisions.append(decision)
                        traces.append(trace)
                except Exception as e:
                    logger.error(f"Failed to process cluster {cluster.cluster_id}: {e}", exc_info=True)
                    continue
            
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"=== Pipeline Complete: {len(decisions)} decisions in {elapsed:.2f}s ==="
            )
            
            return decisions, traces
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            return []
    
    def _process_cluster(self, cluster: AlertCluster) -> (Optional[Decision], Optional[DecisionTrace]):
        """Process a single alert cluster through the pipeline
        
        Args:
            cluster: Alert cluster to process
            
        Returns:
            Tuple of (Decision, DecisionTrace)
        """
        cluster_id = str(cluster.cluster_id)
        logger.info(f"Processing cluster {cluster_id}")
        
        # Transition to INVESTIGATING
        self.state_machine.transition_to(cluster_id, IncidentState.INVESTIGATING)

        # Step 4: Analyze metrics
        logger.info("  Step 4: Analyzing metrics...")
        # metrics_analysis.analyze_cluster_sync is currently wired to return MetricsAnalysisResult
        metrics_result = self.metrics_analysis.analyze_cluster_sync(cluster)
        
        # Step 4.1: Run Swarm Analysis (Simulation for now)
        swarm_results = []

        # Step 4.2: Historical Context
        similar_incidents = []
        try:
            query_text = f"Service: {cluster.primary_service}. Alerts: {cluster.alert_count}. Severity: {cluster.primary_severity}"
            similar_incidents = self.similarity_index.find_similar(query_text)
        except Exception as e:
            logger.warning(f"Failed to fetch similar incidents: {e}")

        # Step 5: Make decision
        logger.info("  Step 5: Making decision...")
        # Extract trends from metrics result for decision engine
        trends = metrics_result.trends if metrics_result else {}

        # Build context for decision engine
        slo_burn_rate = 0.0
        if metrics_result and hasattr(metrics_result, "trends") and "slo_burn_rate" in metrics_result.trends:
             slo_burn_rate = metrics_result.trends["slo_burn_rate"]
        elif hasattr(metrics_result, "quantitative_metrics") and "slo_burn_rate" in metrics_result.quantitative_metrics:
             slo_burn_rate = metrics_result.quantitative_metrics["slo_burn_rate"]

        decision_context = {
            "similar_incidents": similar_incidents,
            "slo_burn_rate": slo_burn_rate
        }

        # If the decision engine has LLM enabled, run the async path so LLM fallback can be used.
        trace = None
        if getattr(self.decision_engine, "_llm_enabled", False):
            try:
                # Step 5: Make decision
                # decision_engine.decide is async
                decision, trace = asyncio.run(
                    self.decision_engine.decide(
                        cluster=cluster,
                        trends=trends,
                        semantic_evidence=[],
                        swarm_results=swarm_results,
                        context=decision_context
                    )
                )
            except Exception as e:
                logger.warning(f"Async decision failed, falling back to sync: {e}")
                decision, trace = self.decision_engine.decide_sync(
                    cluster=cluster,
                    trends=trends,
                    semantic_evidence=[],
                    context=decision_context
                )
        else:
            decision, trace = self.decision_engine.decide_sync(
                cluster=cluster,
                trends=trends,
                semantic_evidence=[],
                context=decision_context
            )
        
        # Step 5.1: Runbook Selection
        runbook = self.runbook_resolver.rank_and_select(
            self.runbook_resolver.match_runbooks(decision.justification, cluster.primary_service, decision.confidence),
            {}
        )
        if runbook:
            logger.info(f"  Selected Runbook: {runbook.name} ({runbook.id})")
            decision.metadata["selected_runbook_id"] = runbook.id
            decision.metadata["selected_runbook_name"] = runbook.name

        # Step 5.2: Registry Snapshot
        try:
            snapshot = IncidentSnapshot(
                incident_id=cluster_id,
                service=cluster.primary_service,
                severity=cluster.primary_severity,
                description=cluster.alerts[0].description if cluster.alerts else "",
                metrics={k: float(v.current_value) for k, v in trends.items() if hasattr(v, 'current_value') and v.current_value is not None},
                findings=[decision.justification],
                decision_state=decision.decision_state.value,
                confidence=decision.confidence
            )
            self.incident_registry.register_snapshot(snapshot)
            self.similarity_index.add_snapshot(snapshot)
        except Exception as e:
            logger.warning(f"Failed to record incident snapshot: {e}")

        # Step 6: Human review if required
        if decision.decision_state == DecisionState.MANUAL_REVIEW:
            logger.info("  Step 6: Human review required")
            review_id = self.human_review.request_review(decision)
            logger.info(f"  Review requested: {review_id}")
            
            # In production, this would wait for async human feedback
            # For now, we just log and return the decision
        elif decision.decision_state == DecisionState.CLOSE:
            self.state_machine.transition_to(cluster_id, IncidentState.CLOSED)
        elif decision.decision_state == DecisionState.ESCALATE:
            self.state_machine.transition_to(cluster_id, IncidentState.MITIGATING)

        # Log Decision State with proper type check
        state_val = getattr(decision.decision_state, 'value', str(decision.decision_state))
        
        logger.info(
            f"  Decision: {state_val} "
            f" (State: {self.state_machine.get_state(cluster_id)})"
            f" (confidence: {decision.confidence:.2f})"
        )
        
        return decision, trace
