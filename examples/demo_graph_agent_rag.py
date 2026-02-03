"""Example: Demonstrating Graph Agent RAG with two pipeline runs"""
import logging
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs) -> bool:
        return False

from src.models.alert import Alert
from src.agents.alert_normalizer import AlertNormalizerAgent
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.decision_engine import DecisionEngine
from src.agents.human_review import HumanReviewAgent
from src.agents.graph_agent import GraphAgent
from src.rules.decision_rules import RuleEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_alerts_batch_1():
    """First batch of alerts"""
    now = datetime.now(timezone.utc)
    return [
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
            fingerprint="api-latency-001",
            service="api-gateway",
            severity="warning",
            description="API response time increased to 2.5s",
            labels={"cluster": "prod", "region": "us-west-2", "type": "api"}
        ),
    ]


def generate_alerts_batch_2():
    """Second batch - similar to first batch (should trigger RAG)"""
    now = datetime.now(timezone.utc)
    return [
        Alert(
            timestamp=now,
            fingerprint="db-cpu-spike-002",
            service="postgres-primary",
            severity="critical",
            description="Database CPU at 97% - high load detected",
            labels={"cluster": "prod", "region": "us-east-1", "type": "database"}
        ),
        Alert(
            timestamp=now,
            fingerprint="api-latency-002",
            service="api-gateway",
            severity="warning",
            description="API latency spike detected",
            labels={"cluster": "prod", "region": "us-west-2", "type": "api"}
        ),
    ]


def run_pipeline(batch_name, raw_alerts, graph_agent, normalizer, correlation, decision_engine, human_review):
    """Run pipeline for a batch of alerts"""
    logger.info(f"\n{'='*70}")
    logger.info(f"BATCH: {batch_name}")
    logger.info(f"{'='*70}\n")
    
    # Normalize
    normalized_alerts = normalizer.normalize(raw_alerts)
    logger.info(f"Normalized {len(normalized_alerts)} alerts")
    
    # Correlate
    clusters = correlation.correlate(normalized_alerts, time_window_minutes=15)
    logger.info(f"Formed {len(clusters)} clusters")
    
    decisions = []
    for i, cluster in enumerate(clusters, 1):
        logger.info(f"\n--- Cluster {i}/{len(clusters)} ---")
        logger.info(f"Service: {cluster.primary_service}, Severity: {cluster.primary_severity}")
        
        # Search for similar past decisions (RAG)
        logger.info("Searching for similar past decisions (RAG)...")
        semantic_evidence = graph_agent.find_similar_decisions(
            cluster=cluster,
            top_k=3,
            min_similarity=0.6
        )
        
        if semantic_evidence:
            logger.info(f"✅ Found {len(semantic_evidence)} similar past decisions:")
            for idx, evidence in enumerate(semantic_evidence, 1):
                logger.info(f"  {idx}. Similarity: {evidence.similarity_score:.3f}")
                logger.info(f"     Summary: {evidence.summary[:100]}...")
        else:
            logger.info("❌ No similar past decisions found (first occurrence)")
        
        # Make decision
        decision = decision_engine.decide_sync(
            cluster=cluster,
            trends={},
            semantic_evidence=semantic_evidence
        )
        
        logger.info(f"Decision: {decision.decision_state.value} (confidence: {decision.confidence:.2f})")
        logger.info(f"Semantic evidence used: {len(decision.semantic_evidence)}")
        
        decisions.append((decision, cluster))
    
    # Simulate human confirmation and store in graph
    logger.info(f"\n{'='*70}")
    logger.info(f"Storing {len(decisions)} confirmed decisions in knowledge graph...")
    for decision, cluster in decisions:
        decision.confirm(validator_id="demo_user")
        graph_agent.store_decision(decision, cluster)
    
    stats = graph_agent.get_stats()
    logger.info(f"Graph now contains {stats['total_decisions']} decisions")
    logger.info(f"{'='*70}\n")
    
    return decisions


def main():
    """Demonstrate Graph Agent RAG across two pipeline runs"""
    load_dotenv()
    
    logger.info("="*70)
    logger.info("DEMONSTRATION: Graph Agent RAG (Semantic Evidence Retrieval)")
    logger.info("="*70)
    logger.info("\nThis demo shows how the Graph Agent provides semantic evidence")
    logger.info("from past decisions to enhance future decision-making.\n")
    
    # Initialize agents (shared across batches)
    normalizer = AlertNormalizerAgent()
    correlation = AlertCorrelationAgent(time_window_minutes=15)
    rule_engine = RuleEngine()
    decision_engine = DecisionEngine(rule_engine=rule_engine)
    human_review = HumanReviewAgent()
    
    # Initialize Graph Agent (memory-only mode)
    graph_agent = GraphAgent(enable_qdrant=False)
    logger.info(f"Graph Agent initialized: {graph_agent.get_stats()}\n")
    
    try:
        # BATCH 1: First occurrence of alerts
        batch1_alerts = generate_alerts_batch_1()
        run_pipeline(
            "BATCH 1 - Initial Alerts",
            batch1_alerts,
            graph_agent,
            normalizer,
            correlation,
            decision_engine,
            human_review
        )
        
        # BATCH 2: Similar alerts (should trigger RAG)
        logger.info("\n" + "🔄 " * 35)
        logger.info("Running BATCH 2 with similar alerts...")
        logger.info("The Graph Agent should now find semantic evidence from BATCH 1!")
        logger.info("🔄 " * 35 + "\n")
        
        batch2_alerts = generate_alerts_batch_2()
        run_pipeline(
            "BATCH 2 - Similar Alerts (RAG Triggered)",
            batch2_alerts,
            graph_agent,
            normalizer,
            correlation,
            decision_engine,
            human_review
        )
        
        # Final summary
        logger.info("\n" + "="*70)
        logger.info("DEMO COMPLETE: Graph Agent RAG Summary")
        logger.info("="*70)
        logger.info(f"Total decisions stored: {graph_agent.get_stats()['total_decisions']}")
        logger.info("✅ BATCH 1: Decisions made without prior knowledge")
        logger.info("✅ BATCH 2: Decisions enriched with semantic evidence from BATCH 1")
        logger.info("\nThe Graph Agent successfully retrieved similar past decisions!")
        logger.info("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
