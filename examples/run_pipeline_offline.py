"""Example: Running the complete alert decision pipeline with synthetic data"""
import logging
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency for examples
    def load_dotenv(*args, **kwargs):
        return None

from src.models.alert import Alert
from src.agents.alert_normalizer import AlertNormalizerAgent
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.decision_engine import DecisionEngine
from src.agents.human_review import HumanReviewAgent
from src.rules.decision_rules import RuleEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_synthetic_alerts():
    """Generate synthetic alerts for testing"""
    now = datetime.now(timezone.utc)
    
    return [
        # Cluster 1: Critical database alerts
        Alert(
            timestamp=now,
            fingerprint="db-cpu-spike-001",
            service="postgres-primary",
            severity="critical",
            description="Database CPU usage exceeded 95% for 5 minutes",
            labels={"cluster": "prod", "region": "us-east-1", "type": "database"}
        ),
        Alert(
            timestamp=now,
            fingerprint="db-mem-high-001",
            service="postgres-primary",
            severity="critical",
            description="Database memory usage at 90%",
            labels={"cluster": "prod", "region": "us-east-1", "type": "database"}
        ),
        
        # Cluster 2: API service degradation
        Alert(
            timestamp=now,
            fingerprint="api-latency-002",
            service="api-gateway",
            severity="warning",
            description="API response time increased to 2.5s (threshold: 1s)",
            labels={"cluster": "prod", "region": "us-west-2", "type": "api"}
        ),
        Alert(
            timestamp=now,
            fingerprint="api-errors-002",
            service="api-gateway",
            severity="warning",
            description="Error rate increased to 5% (threshold: 1%)",
            labels={"cluster": "prod", "region": "us-west-2", "type": "api"}
        ),
        
        # Single low-severity alert (should be ignored/observed)
        Alert(
            timestamp=now,
            fingerprint="disk-space-003",
            service="logging-server",
            severity="info",
            description="Disk usage at 60%",
            labels={"cluster": "staging", "region": "eu-west-1", "type": "storage"}
        ),
    ]


def main():
    """Run the alert decision pipeline with synthetic data"""
    load_dotenv()
    
    logger.info("Initializing pipeline components (offline mode)...")
    
    # Initialize agents (no external dependencies)
    alert_normalizer = AlertNormalizerAgent()
    alert_correlation = AlertCorrelationAgent(time_window_minutes=15)
    metrics_analysis = MetricsAnalysisAgent(prometheus_client=None)  # Offline mode
    
    # Initialize decision engine with rule engine
    rule_engine = RuleEngine()
    decision_engine = DecisionEngine(rule_engine=rule_engine)
    
    # Initialize human review agent
    human_review = HumanReviewAgent()
    
    logger.info("Starting pipeline execution (offline mode with synthetic data)...")
    
    try:
        # Step 1: Generate synthetic alerts
        logger.info("Step 1: Generating synthetic alerts...")
        raw_alerts = generate_synthetic_alerts()
        logger.info(f"Generated {len(raw_alerts)} synthetic alerts")
        
        if not raw_alerts:
            logger.info("No alerts generated")
            return
        
        # Step 2: Normalize alerts
        logger.info(f"Step 2: Normalizing {len(raw_alerts)} alerts...")
        normalized_alerts = alert_normalizer.normalize(raw_alerts)
        logger.info(f"Normalized {len(normalized_alerts)} alerts")
        
        if not normalized_alerts:
            logger.warning("All alerts failed normalization")
            return
        
        # Step 3: Correlate into clusters
        logger.info(f"Step 3: Correlating {len(normalized_alerts)} alerts...")
        clusters = alert_correlation.correlate(normalized_alerts, time_window_minutes=15)
        logger.info(f"Formed {len(clusters)} alert clusters")
        
        if not clusters:
            logger.info("No alert clusters formed")
            return
        
        # Step 4-6: Process each cluster
        decisions = []
        for i, cluster in enumerate(clusters, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing Cluster {i}/{len(clusters)}")
            logger.info(f"{'='*60}")
            logger.info(f"  Cluster ID: {cluster.cluster_id}")
            logger.info(f"  Service: {cluster.primary_service}")
            logger.info(f"  Severity: {cluster.primary_severity}")
            logger.info(f"  Alert Count: {cluster.alert_count}")
            logger.info(f"  Correlation Score: {cluster.correlation_score:.2f}")
            
            try:
                # Step 4: Skip metrics analysis in offline mode (no Prometheus)
                logger.info("  Step 4: Skipping metrics analysis (offline mode)")
                
                # Step 5: Make decision (sync mode - rules only, no LLM)
                logger.info("  Step 5: Making decision...")
                decision = decision_engine.decide_sync(
                    cluster=cluster,
                    trends={},
                    semantic_evidence=[]
                )
                
                logger.info(f"  Decision: {decision.decision_state.value}")
                logger.info(f"    Confidence: {decision.confidence:.2f}")
                logger.info(f"    Rules Applied: {', '.join(decision.rules_applied)}")
                logger.info(f"    Justification: {decision.justification}")
                logger.info(f"    LLM Used: {decision.llm_contribution}")
                
                # Step 6: Human review if required
                if decision.decision_state.value == "MANUAL_REVIEW":
                    logger.info("  Step 6: Human review required")
                    review_id = human_review.request_review(decision)
                    logger.info(f"    Review ID: {review_id}")
                
                decisions.append(decision)
                
            except Exception as e:
                logger.error(f"Failed to process cluster {cluster.cluster_id}: {e}", exc_info=True)
                continue
        
        # Display final results
        logger.info(f"\n{'='*60}")
        logger.info(f"Pipeline Results: {len(decisions)} decisions made")
        logger.info(f"{'='*60}\n")
        
        # Summary by decision state
        from collections import Counter
        decision_counts = Counter(d.decision_state.value for d in decisions)
        for state, count in decision_counts.items():
            logger.info(f"  {state}: {count} decisions")
        
        # Check for pending reviews
        pending_reviews = human_review.get_pending_reviews()
        if pending_reviews:
            logger.info(f"\n{len(pending_reviews)} decisions pending human review:")
            for review in pending_reviews:
                logger.info(f"  - Review ID: {review['review_id']}")
                logger.info(f"    Decision: {review['decision_state']} (confidence: {review['confidence']})")
        
        logger.info("\n" + "="*60)
        logger.info("Pipeline execution complete (offline mode)")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
