import asyncio
import logging
from uuid import uuid4
from datetime import datetime, timezone

from src.models.alert import NormalizedAlert, AlertSource, ValidationStatus
from src.agents.swarm.orchestrator import SwarmOrchestrator
from src.agents.analysis.metrics_analysis import MetricsAnalysisAgent
from src.agents.analysis.repository_context import RepositoryContextAgent
from src.agents.analysis.correlator import CorrelatorAgent
from src.agents.analysis.embedding_agent import EmbeddingAgent
from src.agents.analysis.graph_agent import GraphAgent

from src.agents.governance.decision_engine import DecisionEngine
from src.agents.governance.recommender import RecommenderAgent
from src.agents.governance.human_review import HumanReviewAgent
from src.models.decision import DecisionValidation
from src.graph.neo4j_repo import Neo4jRepository

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("demo")

async def main():
    logger.info("Starting Distributed Diagnostic Architecture Demo")
    
    # 1. Setup Infra (Mocked for demo usually, but we have some real components)
    
    # Mocking Repo to avoid needing Neo4j live for this script script unless env var set
    class MockRepo:
        def save_decision_candidate(self, _c): 
            logger.info("Use Neo4jRepository for real persistence.")
            return str(uuid4())
        def record_decision_outcome(self, _v): 
            logger.info("Recorded decision outcome.")
            
    repo = MockRepo()
    
    # Initialize Analysis Agents
    agents = [
        MetricsAnalysisAgent(),
        RepositoryContextAgent(),
        CorrelatorAgent(),
        EmbeddingAgent(repo), # type: ignore
        GraphAgent(repo) # type: ignore
    ]

    # Orchestrator uses mock agents internally for now (Phase 4 impl)
    orchestrator = SwarmOrchestrator(agents)
    decision_engine = DecisionEngine()
    recommender = RecommenderAgent()

    # human_review = HumanReviewAgent(repo) # type: ignore - mock repo 
    # Actually HumanReviewAgent expects Neo4jRepository, but Python duck typing works if methods match
    human_review = HumanReviewAgent(repo) # type: ignore

    # 2. Ingest Alert (Simulated)
    alert = NormalizedAlert(
        fingerprint="demo-alert-001",
        service="checkout-service",
        description="High latency in checkout service (99th percentile > 2s)",
        severity="critical",
        source=AlertSource.GRAFANA,
        timestamp=datetime.now(timezone.utc),
        validation_status=ValidationStatus.VALID
    )
    logger.info(f"Alert Ingested: {alert.fingerprint}")

    # 3. Swarm Analysis
    logger.info("Initializing Swarm...")
    results = await orchestrator.run_swarm(alert)
    logger.info(f"Swarm finished with {len(results)} results")
    for r in results:
        logger.info(f" - [{r.agent_id}] {r.hypothesis} ({r.confidence})")

    # 4. Decision Consolidation
    candidate = await decision_engine.consolidate(alert, results)
    logger.info(f"Decision Candidate Proposed: {candidate.primary_hypothesis}")
    logger.info(f"Risk: {candidate.risk_assessment}, Automation: {candidate.automation_level}")

    # 5. Recommendation
    candidate = await recommender.refine_recommendation(candidate)
    logger.info(f"Refined Recommendation: {candidate.summary}")

    # 6. Human Review
    logger.info("Requesting Human Review...")
    # Simulate operator input
    validation = DecisionValidation(
        validation_id="val-demo-1",
        decision_id=candidate.decision_id,
        validated_by="demo-operator",
        is_approved=True,
        feedback="Proceed with auto-remediation",
        validated_at=datetime.now(timezone.utc)
    )
    
    final_decision = await human_review.process_review(candidate, validation)
    logger.info(f"Final Status: {final_decision.status}")

if __name__ == "__main__":
    asyncio.run(main())
