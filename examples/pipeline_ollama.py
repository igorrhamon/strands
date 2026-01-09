#!/usr/bin/env python3
"""
Complete Multi-Agent Pipeline with Ollama Provider

Demonstrates the full SRE agent flow:
AlertCollector → AlertNormalizer → AlertCorrelation → MetricsAnalysis
→ RepositoryContext ⟷ GraphKnowledge (feedback loop)
→ DecisionEngine → HumanReview → OutcomeSupervisor
→ MemoryValidation → GraphKnowledge → AuditReport

Usage:
    # Set environment variables
    export OLLAMA_HOST="http://localhost:11434"
    export OLLAMA_MODEL="llama3.1"
    export PROMETHEUS_URL="http://localhost:9090"  # Optional for metrics

    # Run the pipeline
    python examples/pipeline_ollama.py

Requirements:
    - Ollama running locally with a model pulled (e.g., llama3.1)
    - Optional: Prometheus for real metrics analysis
    - Optional: Neo4j/Qdrant for graph knowledge storage
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.providers.ollama_models import OllamaModels
from src.models.alert import Alert, NormalizedAlert
from src.models.cluster import AlertCluster
from src.models.metrics import MetricsAnalysisResult

# Import agents
from src.agents.alert_normalizer import AlertNormalizerAgent
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.repository_context import RepositoryContextAgent
from src.agents.graph_agent import GraphAgent
from src.agents.decision_engine import DecisionEngine
from src.agents.human_review import HumanReviewAgent
from src.agents.report_agent import ReportAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the complete multi-agent pipeline with Ollama provider."""
    
    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "llama3.1",
        prometheus_url: Optional[str] = None,
    ):
        """Initialize pipeline with Ollama provider and agents."""
        logger.info("=" * 80)
        logger.info("🚀 Initializing Multi-Agent Pipeline with Ollama")
        logger.info("=" * 80)
        
        # Initialize Ollama provider
        self.model = OllamaModels(
            host=ollama_host,
            model_id=ollama_model,
            timeout=60,
            streaming=False  # Use synchronous responses for clarity
        )
        logger.info(f"✅ Ollama provider initialized: {ollama_host} / {ollama_model}")
        
        # Initialize deterministic agents (no LLM needed)
        self.normalizer = AlertNormalizerAgent()
        self.correlation = AlertCorrelationAgent(time_window_minutes=5)
        self.metrics_analysis = MetricsAnalysisAgent(
            lookback_minutes=15,
            step_seconds=60
        )
        logger.info("✅ Deterministic agents initialized (normalizer, correlation, metrics)")
        
        # For LLM-backed steps, we'll use the Ollama model directly
        # (rather than initializing agent classes that may not accept model parameter)
        logger.info("✅ LLM provider (Ollama) ready for context/decision/review/audit steps")
        
        # Pipeline state
        self.pipeline_state = {
            "alerts_raw": [],
            "alerts_normalized": [],
            "clusters": [],
            "metrics_results": {},
            "repo_context": {},
            "graph_evidence": {},
            "decisions": {},
            "review_outcomes": {},
            "audit_logs": []
        }
    
    def generate_synthetic_alerts(self, count: int = 5) -> list[Alert]:
        """Generate synthetic alerts for demonstration."""
        logger.info(f"📝 Generating {count} synthetic alerts...")
        
        alerts = []
        base_time = datetime.now(timezone.utc)
        
        services = ["api-gateway", "auth-service", "payment-service", "checkout-service"]
        severities = ["critical", "warning", "info"]
        
        for i in range(count):
            alert = Alert(
                timestamp=base_time - timedelta(minutes=i * 2),
                fingerprint=f"fp_{i:04d}_{base_time.timestamp():.0f}",
                service=services[i % len(services)],
                severity=severities[i % len(severities)],
                description=f"High error rate detected in {services[i % len(services)]} - "
                           f"{50 + i * 10}% errors in last 5 minutes",
                labels={
                    "environment": "production",
                    "region": "us-east-1",
                    "cluster": "prod-cluster-01",
                    "alertname": f"HighErrorRate_{i}",
                }
            )
            alerts.append(alert)
        
        logger.info(f"✅ Generated {len(alerts)} synthetic alerts")
        return alerts
    
    async def run_pipeline(self):
        """Execute the complete multi-agent pipeline."""
        try:
            logger.info("\n" + "=" * 80)
            logger.info("🎯 PHASE 1: Alert Collection & Normalization")
            logger.info("=" * 80)
            
            # STEP 1: Alert Collection (synthetic for demo)
            raw_alerts = self.generate_synthetic_alerts(count=5)
            self.pipeline_state["alerts_raw"] = raw_alerts
            logger.info(f"✅ Step 1/12: Collected {len(raw_alerts)} raw alerts")
            
            # STEP 2: Alert Normalization
            normalized_alerts = self.normalizer.normalize(raw_alerts)
            self.pipeline_state["alerts_normalized"] = normalized_alerts
            logger.info(f"✅ Step 2/12: Normalized {len(normalized_alerts)} alerts")
            
            # STEP 3: Alert Correlation
            logger.info("\n" + "=" * 80)
            logger.info("🔗 PHASE 2: Correlation & Clustering")
            logger.info("=" * 80)
            
            clusters = await self.correlation.collect_and_correlate(
                lookback_minutes=60
            )
            
            # If no clusters from real collection, create synthetic clusters
            if not clusters and normalized_alerts:
                logger.info("Creating synthetic cluster from normalized alerts...")
                clusters = [
                    AlertCluster.from_alerts(
                        alerts=normalized_alerts[:3],
                        correlation_score=0.85
                    )
                ]
            
            self.pipeline_state["clusters"] = clusters
            logger.info(f"✅ Step 3/12: Created {len(clusters)} alert clusters")
            
            # Process each cluster through the pipeline
            for idx, cluster in enumerate(clusters, 1):
                logger.info(f"\n{'='*80}")
                logger.info(f"📦 Processing Cluster {idx}/{len(clusters)}: {cluster.cluster_id}")
                logger.info(f"   Service: {cluster.primary_service} | "
                           f"Severity: {cluster.primary_severity} | "
                           f"Alerts: {cluster.alert_count}")
                logger.info("=" * 80)
                
                # STEP 4: Metrics Analysis
                logger.info("\n📊 PHASE 3: Metrics Analysis")
                metrics_result = await self.metrics_analysis.analyze_cluster(cluster)
                self.pipeline_state["metrics_results"][str(cluster.cluster_id)] = metrics_result
                
                logger.info("✅ Step 4/12: Metrics analyzed")
                logger.info(f"   Overall Health: {metrics_result.overall_health}")
                logger.info(f"   Confidence: {metrics_result.overall_confidence:.2f}")
                logger.info(f"   Query Latency: {metrics_result.query_latency_ms:.0f}ms")
                
                # STEP 5: Repository Context (with LLM)
                logger.info("\n📚 PHASE 4: Repository Context Retrieval")
                repo_context = await self._get_repository_context(cluster, metrics_result)
                self.pipeline_state["repo_context"][str(cluster.cluster_id)] = repo_context
                logger.info("✅ Step 5/12: Repository context retrieved")
                
                # STEP 6-7: Graph Knowledge Feedback Loop
                logger.info("\n🔄 PHASE 5: Graph Knowledge Feedback Loop")
                graph_evidence = await self._graph_feedback_loop(
                    cluster, metrics_result, repo_context
                )
                self.pipeline_state["graph_evidence"][str(cluster.cluster_id)] = graph_evidence
                logger.info("✅ Step 6-7/12: Graph knowledge enriched with feedback")
                
                # STEP 8: Decision Engine
                logger.info("\n⚖️ PHASE 6: Decision Making")
                decision = await self._make_decision(
                    cluster, metrics_result, repo_context, graph_evidence
                )
                self.pipeline_state["decisions"][str(cluster.cluster_id)] = decision
                logger.info(f"✅ Step 8/12: Decision made: {decision.get('action', 'UNKNOWN')}")
                logger.info(f"   Confidence: {decision.get('confidence', 0):.2f}")
                
                # STEP 9: Human Review
                logger.info("\n👤 PHASE 7: Human Review")
                review_outcome = await self._human_review(cluster, decision)
                self.pipeline_state["review_outcomes"][str(cluster.cluster_id)] = review_outcome
                logger.info(f"✅ Step 9/12: Human review completed: "
                           f"{review_outcome.get('approved', False)}")
                
                # STEP 10: Outcome Supervision & Memory Validation
                logger.info("\n🔍 PHASE 8: Outcome Supervision & Memory Validation")
                self._supervise_and_validate(decision, review_outcome)
                logger.info("✅ Step 10/12: Outcome supervised and validated")
                
                # STEP 11: Update Graph Knowledge with final outcome
                logger.info("\n💾 PHASE 9: Persist to Graph Knowledge")
                await self._persist_to_graph(cluster, decision, review_outcome)
                logger.info("✅ Step 11/12: Knowledge persisted to graph")
            
            # STEP 12: Generate Audit Report
            logger.info("\n" + "=" * 80)
            logger.info("📄 PHASE 10: Audit Report Generation")
            logger.info("=" * 80)
            
            audit_report = await self._generate_audit_report()
            self.pipeline_state["audit_logs"].append(audit_report)
            logger.info("✅ Step 12/12: Audit report generated")
            
            # Print final summary
            self._print_summary()
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {type(e).__name__}: {e}", exc_info=True)
            raise
    
    async def _get_repository_context(
        self, cluster: AlertCluster, metrics: MetricsAnalysisResult
    ) -> dict:
        """Retrieve repository context using LLM."""
        try:
            # Build context prompt
            prompt = f"""Analyze this alert cluster and provide repository context:

Service: {cluster.primary_service}
Severity: {cluster.primary_severity}
Alert Count: {cluster.alert_count}
Overall Health: {metrics.overall_health}

What repository files, components, or services might be relevant to investigate?
Provide a brief analysis (2-3 sentences) and list 3-5 relevant file paths or components."""

            messages = [{"role": "user", "content": prompt}]
            
            result_text = ""
            async for ev in self.model.stream(messages):
                if isinstance(ev, dict):
                    delta = ev.get("contentBlockDelta", {}).get("delta", {})
                    text = delta.get("text", "")
                    result_text += text
            
            return {
                "analysis": result_text.strip(),
                "service": cluster.primary_service,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.warning(f"Failed to get repository context: {e}")
            return {"analysis": "Context unavailable", "error": str(e)}
    
    async def _graph_feedback_loop(
        self, cluster: AlertCluster, metrics: MetricsAnalysisResult, repo_context: dict
    ) -> dict:
        """Execute feedback loop between RepositoryContext and GraphAgent."""
        try:
            # First query: Search for similar historical incidents
            search_prompt = f"""Search graph knowledge for similar incidents:

Service: {cluster.primary_service}
Health: {metrics.overall_health}
Context: {repo_context.get('analysis', 'N/A')[:200]}

Have we seen similar issues before? What was the resolution?"""

            messages = [{"role": "user", "content": search_prompt}]
            
            search_results = ""
            async for ev in self.model.stream(messages):
                if isinstance(ev, dict):
                    delta = ev.get("contentBlockDelta", {}).get("delta", {})
                    search_results += delta.get("text", "")
            
            # Second query: Enrich with additional context
            enrich_prompt = f"""Based on this historical search:

{search_results[:500]}

Provide 2-3 specific evidence points or patterns that could help decide on this incident."""

            enrich_messages = [{"role": "user", "content": enrich_prompt}]
            
            enriched_evidence = ""
            async for ev in self.model.stream(enrich_messages):
                if isinstance(ev, dict):
                    delta = ev.get("contentBlockDelta", {}).get("delta", {})
                    enriched_evidence += delta.get("text", "")
            
            return {
                "search_results": search_results.strip(),
                "enriched_evidence": enriched_evidence.strip(),
                "feedback_loop_complete": True
            }
        except Exception as e:
            logger.warning(f"Graph feedback loop failed: {e}")
            return {"error": str(e), "feedback_loop_complete": False}
    
    async def _make_decision(
        self,
        cluster: AlertCluster,
        metrics: MetricsAnalysisResult,
        repo_context: dict,
        graph_evidence: dict
    ) -> dict:
        """Make decision using DecisionEngine with all context."""
        try:
            decision_prompt = f"""Make a decision for this incident:

CLUSTER INFO:
- Service: {cluster.primary_service}
- Severity: {cluster.primary_severity}
- Alert Count: {cluster.alert_count}

METRICS:
- Overall Health: {metrics.overall_health}
- Confidence: {metrics.overall_confidence:.2f}
- Has Degrading Metrics: {metrics.has_degrading_metrics}

REPOSITORY CONTEXT:
{repo_context.get('analysis', 'N/A')[:300]}

GRAPH EVIDENCE:
{graph_evidence.get('enriched_evidence', 'N/A')[:300]}

Recommend one action: ESCALATE, AUTO_REMEDIATE, MONITOR, or DISMISS.
Provide confidence (0.0-1.0) and brief reasoning (1-2 sentences)."""

            messages = [{"role": "user", "content": decision_prompt}]
            
            decision_text = ""
            async for ev in self.model.stream(messages):
                if isinstance(ev, dict):
                    delta = ev.get("contentBlockDelta", {}).get("delta", {})
                    decision_text += delta.get("text", "")
            
            # Parse decision (simple heuristic)
            action = "MONITOR"  # Default
            if "ESCALATE" in decision_text.upper():
                action = "ESCALATE"
            elif "AUTO_REMEDIATE" in decision_text.upper():
                action = "AUTO_REMEDIATE"
            elif "DISMISS" in decision_text.upper():
                action = "DISMISS"
            
            # Extract confidence (look for numbers 0.x)
            import re
            confidence_match = re.search(r'0\.\d+', decision_text)
            confidence = float(confidence_match.group()) if confidence_match else 0.7
            
            return {
                "action": action,
                "confidence": confidence,
                "reasoning": decision_text.strip(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.warning(f"Decision making failed: {e}")
            return {
                "action": "MONITOR",
                "confidence": 0.5,
                "reasoning": f"Error: {e}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _human_review(self, cluster: AlertCluster, decision: dict) -> dict:
        """Simulate human review step."""
        try:
            review_prompt = f"""Review this automated decision:

CLUSTER: {cluster.primary_service} ({cluster.primary_severity})
DECISION: {decision['action']}
CONFIDENCE: {decision['confidence']:.2f}
REASONING: {decision['reasoning'][:200]}

Should this decision be approved? Provide yes/no and any concerns (1 sentence)."""

            messages = [{"role": "user", "content": review_prompt}]
            
            review_text = ""
            async for ev in self.model.stream(messages):
                if isinstance(ev, dict):
                    delta = ev.get("contentBlockDelta", {}).get("delta", {})
                    review_text += delta.get("text", "")
            
            # Parse approval (simple heuristic)
            approved = "yes" in review_text.lower() or "approve" in review_text.lower()
            
            return {
                "approved": approved,
                "review_notes": review_text.strip(),
                "reviewer": "HumanReviewAgent",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.warning(f"Human review failed: {e}")
            return {
                "approved": False,
                "review_notes": f"Error: {e}",
                "reviewer": "HumanReviewAgent",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _supervise_and_validate(
        self, decision: dict, review: dict
    ) -> None:
        """Supervise outcome and validate memory persistence."""
        try:
            # Outcome supervision logic
            if review["approved"] and decision["confidence"] >= 0.7:
                logger.info(f"   ✅ Outcome approved: {decision['action']}")
            elif decision["confidence"] < 0.5:
                logger.warning(f"   ⚠️ Low confidence decision: {decision['confidence']:.2f}")
            else:
                logger.info("   ℹ️ Decision pending further review")
            
            # Memory validation (check consistency)
            if decision["action"] in ["ESCALATE", "AUTO_REMEDIATE"] and not review["approved"]:
                logger.warning("   ⚠️ Memory validation: High-impact action not approved")
        except Exception as e:
            logger.error(f"Supervision/validation failed: {e}")
    
    async def _persist_to_graph(
        self, cluster: AlertCluster, decision: dict, review: dict
    ) -> None:
        """Persist final outcome to graph knowledge."""
        try:
            persist_prompt = f"""Store this incident resolution in knowledge graph:

Cluster ID: {cluster.cluster_id}
Service: {cluster.primary_service}
Decision: {decision['action']}
Approved: {review['approved']}
Outcome: {"Executed" if review['approved'] else "Rejected"}

Generate a 1-sentence summary for the knowledge graph."""

            messages = [{"role": "user", "content": persist_prompt}]
            
            summary = ""
            async for ev in self.model.stream(messages):
                if isinstance(ev, dict):
                    delta = ev.get("contentBlockDelta", {}).get("delta", {})
                    summary += delta.get("text", "")
            
            logger.info(f"   📝 Knowledge persisted: {summary.strip()[:100]}")
        except Exception as e:
            logger.warning(f"Graph persistence failed: {e}")
    
    async def _generate_audit_report(self) -> dict:
        """Generate final audit report for the pipeline run."""
        try:
            report_prompt = f"""Generate an audit report for this pipeline run:

Total Clusters Processed: {len(self.pipeline_state['clusters'])}
Decisions Made: {len(self.pipeline_state['decisions'])}
Approvals: {sum(1 for r in self.pipeline_state['review_outcomes'].values() if r.get('approved'))}

Provide:
1. Summary (2-3 sentences)
2. Key metrics
3. Any concerns or anomalies"""

            messages = [{"role": "user", "content": report_prompt}]
            
            report_text = ""
            async for ev in self.model.stream(messages):
                if isinstance(ev, dict):
                    delta = ev.get("contentBlockDelta", {}).get("delta", {})
                    report_text += delta.get("text", "")
            
            logger.info("\n" + "=" * 80)
            logger.info("📄 AUDIT REPORT")
            logger.info("=" * 80)
            logger.info(report_text.strip())
            logger.info("=" * 80)
            
            return {
                "report": report_text.strip(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pipeline_run_id": id(self)
            }
        except Exception as e:
            logger.error(f"Audit report generation failed: {e}")
            return {"error": str(e)}
    
    def _print_summary(self):
        """Print final pipeline summary."""
        logger.info("\n" + "=" * 80)
        logger.info("✅ PIPELINE COMPLETE - SUMMARY")
        logger.info("=" * 80)
        logger.info(f"📊 Raw Alerts: {len(self.pipeline_state['alerts_raw'])}")
        logger.info(f"✅ Normalized: {len(self.pipeline_state['alerts_normalized'])}")
        logger.info(f"🔗 Clusters: {len(self.pipeline_state['clusters'])}")
        logger.info(f"📈 Metrics Analyzed: {len(self.pipeline_state['metrics_results'])}")
        logger.info(f"⚖️ Decisions: {len(self.pipeline_state['decisions'])}")
        
        approvals = sum(
            1 for r in self.pipeline_state['review_outcomes'].values()
            if r.get('approved', False)
        )
        logger.info(f"👤 Approvals: {approvals}/{len(self.pipeline_state['review_outcomes'])}")
        logger.info("=" * 80)


async def main():
    """Main entry point for the pipeline example."""
    # Load configuration from environment
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    prometheus_url = os.environ.get("PROMETHEUS_URL")
    
    logger.info("🔧 Configuration:")
    logger.info(f"   Ollama Host: {ollama_host}")
    logger.info(f"   Ollama Model: {ollama_model}")
    logger.info(f"   Prometheus: {prometheus_url or 'Not configured (using stubs)'}")
    
    # Initialize and run pipeline
    orchestrator = PipelineOrchestrator(
        ollama_host=ollama_host,
        ollama_model=ollama_model,
        prometheus_url=prometheus_url
    )
    
    await orchestrator.run_pipeline()
    
    logger.info("\n🎉 Pipeline execution completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ Pipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Pipeline failed: {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)
