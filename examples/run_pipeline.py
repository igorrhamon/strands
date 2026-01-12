"""Example: Running the complete alert decision pipeline"""
import logging
import os
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency for examples
    def load_dotenv(*args, **kwargs) -> bool:
        return False

from src.tools.grafana_client import GrafanaMCPClient

from src.tools.prometheus_queries import PrometheusClient
from src.agents.alert_collector import AlertCollectorAgent
from src.agents.alert_normalizer import AlertNormalizerAgent
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.repository_context import RepositoryContextAgent
from src.agents.decision_engine import DecisionEngine
from src.agents.human_review import HumanReviewAgent
from src.agents.orchestrator import AlertOrchestratorAgent
from src.rules.policy_engine import PolicyEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run the alert decision pipeline"""
    load_dotenv()
    
    logger.info("Initializing pipeline components...")
    
    # Initialize clients
    grafana_client = GrafanaMCPClient()
    prometheus_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    prometheus_client = PrometheusClient(base_url=prometheus_url)
    
    # Initialize agents
    alert_collector = AlertCollectorAgent(grafana_client, prometheus_client=prometheus_client)
    alert_normalizer = AlertNormalizerAgent()
    alert_correlation = AlertCorrelationAgent(time_window_minutes=15)
    metrics_analysis = MetricsAnalysisAgent(prometheus_client)
    repository_context = RepositoryContextAgent(top_k=5, score_threshold=0.75)
    
    # Initialize decision engine
    decision_engine = DecisionEngine()
    
    # Initialize human review agent
    human_review = HumanReviewAgent()
    
    # Create orchestrator
    orchestrator = AlertOrchestratorAgent(
        alert_collector=alert_collector,
        alert_normalizer=alert_normalizer,
        alert_correlation=alert_correlation,
        metrics_analysis=metrics_analysis,
        decision_engine=decision_engine,
        human_review=human_review
    )
    
    logger.info("Starting pipeline execution...")
    
    try:
        # Run pipeline
        decisions = orchestrator.run_pipeline()
        
        # Display results
        logger.info(f"\n{'='*60}")
        logger.info(f"Pipeline Results: {len(decisions)} decisions made")
        logger.info(f"{'='*60}\n")
        
        for decision in decisions:
            logger.info(f"Decision ID: {decision.decision_id}")
            logger.info(f"  State: {decision.decision_state.value}")
            logger.info(f"  Confidence: {decision.confidence:.2f}")
            logger.info(f"  LLM Used: {decision.llm_contribution}")
            logger.info(f"  Rules Applied: {', '.join(decision.rules_applied)}")
            logger.info(f"  Justification: {decision.justification}")
            logger.info("")
        
        # Check for pending reviews
        pending_reviews = human_review.get_pending_reviews()
        if pending_reviews:
            logger.info(f"\n{len(pending_reviews)} decisions pending human review:")
            for review in pending_reviews:
                logger.info(f"  - Review ID: {review['review_id']}")
                logger.info(f"    Decision: {review['decision_state']} (confidence: {review['confidence']})")
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        grafana_client.close()
        prometheus_client.close()
        repository_context.close()
        logger.info("Pipeline execution complete")


if __name__ == "__main__":
    main()
