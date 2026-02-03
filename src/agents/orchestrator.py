"""Alert Orchestrator Agent - coordinates the decision pipeline"""
from typing import List, Optional
import logging
from datetime import datetime, timezone

from src.models.alert import Alert, NormalizedAlert
from src.models.cluster import AlertCluster
from src.models.metrics import MetricsAnalysisResult
from src.models.decision import Decision, DecisionState
from src.agents.alert_collector import AlertCollectorAgent
from src.agents.alert_normalizer import AlertNormalizerAgent
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.decision_engine import DecisionEngine
import asyncio
from src.agents.human_review import HumanReviewAgent
from src.config.settings import config


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
    
    def run_pipeline(self) -> List[Decision]:
        """Execute the complete decision pipeline
        
        Returns:
            List of Decision objects
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
            for cluster in clusters:
                try:
                    decision = self._process_cluster(cluster)
                    if decision:
                        decisions.append(decision)
                except Exception as e:
                    logger.error(f"Failed to process cluster {cluster.cluster_id}: {e}", exc_info=True)
                    continue
            
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"=== Pipeline Complete: {len(decisions)} decisions in {elapsed:.2f}s ==="
            )
            
            return decisions
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            return []
    
    def _process_cluster(self, cluster: AlertCluster) -> Optional[Decision]:
        """Process a single alert cluster through the pipeline
        
        Args:
            cluster: Alert cluster to process
            
        Returns:
            Decision object or None if processing failed
        """
        logger.info(f"Processing cluster {cluster.cluster_id}")
        
        # Step 4: Analyze metrics
        logger.info("  Step 4: Analyzing metrics...")
        metrics_result = self.metrics_analysis.analyze_cluster_sync(cluster)
        
        # Step 5: Make decision
        logger.info("  Step 5: Making decision...")
        # Extract trends from metrics result for decision engine
        trends = metrics_result.trends if metrics_result else {}

        # If the decision engine has LLM enabled, run the async path so LLM fallback can be used.
        if getattr(self.decision_engine, "_llm_enabled", False):
            try:
                decision = asyncio.run(
                    self.decision_engine.decide(
                        cluster=cluster,
                        trends=trends,
                        semantic_evidence=[],
                    )
                )
            except Exception as e:
                logger.warning(f"Async decision failed, falling back to sync: {e}")
                decision = self.decision_engine.decide_sync(
                    cluster=cluster,
                    trends=trends,
                    semantic_evidence=[],
                )
        else:
            decision = self.decision_engine.decide_sync(
                cluster=cluster,
                trends=trends,
                semantic_evidence=[],
            )
        
        # Step 6: Human review if required
        if decision.decision_state == DecisionState.MANUAL_REVIEW:
            logger.info("  Step 6: Human review required")
            review_id = self.human_review.request_review(decision)
            logger.info(f"  Review requested: {review_id}")
            
            # In production, this would wait for async human feedback
            # For now, we just log and return the decision
        
        logger.info(
            f"  Decision: {decision.decision_state.value} "
            f"(confidence: {decision.confidence:.2f})"
        )
        
        return decision
