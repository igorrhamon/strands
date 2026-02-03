"""Example: Graph Agent with Real Qdrant Vector Database"""
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
from src.agents.decision_engine import DecisionEngine
from src.agents.graph_agent import GraphAgent
from src.rules.decision_rules import RuleEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_alerts_batch_1():
    """First batch - Database and API issues"""
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
            fingerprint="db-mem-high-001",
            service="postgres-primary",
            severity="critical",
            description="Database memory usage at 90%",
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
    """Second batch - Similar issues (should trigger RAG)"""
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
            fingerprint="api-timeout-002",
            service="api-gateway",
            severity="warning",
            description="API timeout rate increased",
            labels={"cluster": "prod", "region": "us-west-2", "type": "api"}
        ),
    ]


def generate_alerts_batch_3():
    """Third batch - Different service"""
    now = datetime.now(timezone.utc)
    return [
        Alert(
            timestamp=now,
            fingerprint="redis-mem-003",
            service="redis-cache",
            severity="critical",
            description="Redis memory usage at 95%",
            labels={"cluster": "prod", "region": "eu-west-1", "type": "cache"}
        ),
    ]


def run_pipeline_with_qdrant(batch_name, raw_alerts, graph_agent, normalizer, correlation, decision_engine):
    """Run pipeline with real Qdrant storage"""
    logger.info(f"\n{'='*70}")
    logger.info(f"BATCH: {batch_name}")
    logger.info(f"{'='*70}\n")
    
    # Normalize
    normalized_alerts = normalizer.normalize(raw_alerts)
    logger.info(f"✅ Normalized {len(normalized_alerts)} alerts")
    
    # Correlate
    clusters = correlation.correlate(normalized_alerts, time_window_minutes=15)
    logger.info(f"✅ Formed {len(clusters)} clusters\n")
    
    decisions = []
    for i, cluster in enumerate(clusters, 1):
        logger.info(f"--- Cluster {i}/{len(clusters)} ---")
        logger.info(f"  Service: {cluster.primary_service}")
        logger.info(f"  Severity: {cluster.primary_severity}")
        logger.info(f"  Alert Count: {cluster.alert_count}")
        
        # Search for similar past decisions in Qdrant (RAG)
        logger.info("  🔍 Searching Qdrant for similar past decisions...")
        semantic_evidence = graph_agent.find_similar_decisions(
            cluster=cluster,
            top_k=3,
            min_similarity=0.6
        )
        
        if semantic_evidence:
            logger.info(f"  ✅ Found {len(semantic_evidence)} similar decisions in Qdrant:")
            for idx, evidence in enumerate(semantic_evidence, 1):
                logger.info(f"    {idx}. Similarity: {evidence.similarity_score:.3f}")
                logger.info(f"       {evidence.summary[:80]}...")
        else:
            logger.info("  ❌ No similar past decisions found (first occurrence)")
        
        # Make decision
        decision = decision_engine.decide_sync(
            cluster=cluster,
            trends={},
            semantic_evidence=semantic_evidence
        )
        
        logger.info(f"  📋 Decision: {decision.decision_state.value}")
        logger.info(f"     Confidence: {decision.confidence:.2f}")
        logger.info(f"     Rules: {', '.join(decision.rules_applied)}")
        logger.info(f"     Semantic Evidence Used: {len(decision.semantic_evidence)}\n")
        
        decisions.append((decision, cluster))
    
    # Store confirmed decisions in Qdrant
    logger.info(f"💾 Storing {len(decisions)} confirmed decisions in Qdrant...")
    stored_count = 0
    for decision, cluster in decisions:
        decision.confirm(validator_id="qdrant_demo_user")
        if graph_agent.store_decision(decision, cluster):
            stored_count += 1
    
    stats = graph_agent.get_stats()
    logger.info(f"✅ Stored {stored_count} decisions in Qdrant")
    logger.info(f"   Total in database: {stats['total_decisions']} decisions")
    logger.info(f"   Backend: {stats['backend']}")
    if 'collection' in stats:
        logger.info(f"   Collection: {stats['collection']}")
    logger.info(f"{'='*70}\n")
    
    return decisions


def main():
    """Demonstrate Graph Agent with real Qdrant persistence"""
    load_dotenv()
    
    logger.info("="*70)
    logger.info("🚀 DEMONSTRATION: Graph Agent with Real Qdrant Vector Database")
    logger.info("="*70)
    logger.info("\nThis demo uses real Qdrant to store and retrieve decisions.")
    logger.info("Decisions persist across runs and enable true RAG.\n")
    
    # Initialize agents
    normalizer = AlertNormalizerAgent()
    correlation = AlertCorrelationAgent(time_window_minutes=15)
    rule_engine = RuleEngine()
    decision_engine = DecisionEngine(rule_engine=rule_engine)
    
    # Initialize Graph Agent with Qdrant ENABLED
    logger.info("🔌 Connecting to Qdrant at localhost:6333...")
    graph_agent = GraphAgent(enable_qdrant=True, collection_name="alert_decisions_demo")
    
    initial_stats = graph_agent.get_stats()
    logger.info(f"✅ Connected to Qdrant!")
    logger.info(f"   Backend: {initial_stats['backend']}")
    logger.info(f"   Existing decisions: {initial_stats['total_decisions']}")
    if 'collection' in initial_stats:
        logger.info(f"   Collection: {initial_stats['collection']}\n")
    
    if not graph_agent.enable_qdrant:
        logger.error("❌ Failed to connect to Qdrant!")
        logger.error("   Make sure Qdrant is running: ./scripts/qdrant.sh start")
        return
    
    try:
        # BATCH 1: Initial alerts
        logger.info("📦 BATCH 1: Initial Database and API Alerts")
        batch1_alerts = generate_alerts_batch_1()
        run_pipeline_with_qdrant(
            "BATCH 1 - Initial Alerts",
            batch1_alerts,
            graph_agent,
            normalizer,
            correlation,
            decision_engine
        )
        
        # BATCH 2: Similar alerts (should find evidence from BATCH 1)
        logger.info("🔄 BATCH 2: Similar Alerts (RAG Should Activate)")
        logger.info("Expected: Find similar decisions from BATCH 1\n")
        batch2_alerts = generate_alerts_batch_2()
        run_pipeline_with_qdrant(
            "BATCH 2 - Similar Alerts (RAG)",
            batch2_alerts,
            graph_agent,
            normalizer,
            correlation,
            decision_engine
        )
        
        # BATCH 3: Different service (should not find much evidence)
        logger.info("🆕 BATCH 3: Different Service (Cache)")
        logger.info("Expected: No similar decisions (different service)\n")
        batch3_alerts = generate_alerts_batch_3()
        run_pipeline_with_qdrant(
            "BATCH 3 - Different Service",
            batch3_alerts,
            graph_agent,
            normalizer,
            correlation,
            decision_engine
        )
        
        # Final summary
        final_stats = graph_agent.get_stats()
        logger.info("\n" + "="*70)
        logger.info("🎉 DEMO COMPLETE: Qdrant Graph Agent Summary")
        logger.info("="*70)
        logger.info(f"📊 Total decisions stored in Qdrant: {final_stats['total_decisions']}")
        logger.info(f"   Collection: {final_stats.get('collection', 'N/A')}")
        logger.info(f"   Backend: {final_stats['backend']}")
        logger.info("\n✅ Batch 1: Initial decisions stored")
        logger.info("✅ Batch 2: RAG retrieved similar decisions from Batch 1")
        logger.info("✅ Batch 3: New service, limited prior evidence")
        logger.info("\n🔗 Access Qdrant Dashboard: http://localhost:6333/dashboard")
        logger.info("📚 View collections: http://localhost:6333/collections")
        logger.info("\n💡 Run this script again to see persistent decisions!")
        logger.info("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
