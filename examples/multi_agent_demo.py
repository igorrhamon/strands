#!/usr/bin/env python3
"""
Multi-Agent Demo - Strands Agents SDK with GitHub Models

Demonstrates the "Agent as Tool" pattern with a Supervisor agent coordinating
specialized agents (Analyst, Judge, Reporter) to process security alerts.

This example can run in two modes:

1. WITHOUT LLM (deterministic rules only):
   python examples/multi_agent_demo.py rules

2. WITH GitHub Models (requires GITHUB_TOKEN):
   python examples/multi_agent_demo.py github

Usage:
    python examples/multi_agent_demo.py [rules|github]
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add repo root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models.alert import Alert

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_alerts() -> list[dict]:
    """Create sample alerts for demonstration."""
    now = datetime.now(timezone.utc)
    
    return [
        {
            "timestamp": now.isoformat(),
            "fingerprint": "alert-001",
            "service": "checkout-service",
            "severity": "critical",
            "description": "CPU usage exceeds 90% for 5+ minutes",
            "labels": {
                "region": "us-east-1",
            },
        },
        {
            "timestamp": now.isoformat(),
            "fingerprint": "alert-002",
            "service": "checkout-service",
            "severity": "critical",
            "description": "Memory usage exceeds 85% for 5+ minutes",
            "labels": {
                "region": "us-east-1",
            },
        },
        {
            "timestamp": (now - timedelta(minutes=2)).isoformat(),
            "fingerprint": "alert-003",
            "service": "payment-service",
            "severity": "warning",
            "description": "Error rate exceeds 5% for 3+ minutes",
            "labels": {
                "region": "us-east-1",
            },
        },
    ]


def format_report(report: dict) -> str:
    """Format report for console output."""
    output = []
    output.append("\n" + "=" * 80)
    output.append("ALERT DECISION REPORT")
    output.append("=" * 80)
    
    if report.get("status") != "success":
        output.append(f"\n❌ Error: {report.get('error', 'Unknown error')}")
        return "\n".join(output)
    
    summary = report.get("summary", {})
    output.append(f"\n📊 Summary:")
    output.append(f"   Total Clusters: {summary.get('total_clusters', 0)}")
    output.append(f"   ⚠️  Escalate:     {summary.get('escalate', 0)}")
    output.append(f"   🔍 Observe:      {summary.get('observe', 0)}")
    output.append(f"   ✋ Manual Review: {summary.get('manual_review', 0)}")
    
    if summary.get("next_steps"):
        output.append(f"\n📋 Next Steps:")
        for step in summary["next_steps"]:
            output.append(f"   - {step}")
    
    cluster_reports = report.get("cluster_reports", [])
    if cluster_reports:
        output.append(f"\n📌 Cluster Details:")
        for cluster in cluster_reports:
            output.append(f"\n   Cluster: {cluster.get('cluster_id', 'unknown')}")
            output.append(f"   Service: {cluster.get('service', 'unknown')}")
            output.append(f"   Severity: {cluster.get('severity', 'unknown')}")
            output.append(f"   Alerts: {cluster.get('alert_count', 0)}")
            
            rec = cluster.get("recommendation", {})
            output.append(f"   📌 Recommendation: {rec.get('action', 'UNKNOWN')}")
            output.append(f"      Confidence: {rec.get('confidence', 0):.0%}")
            output.append(f"      Reasoning: {rec.get('reasoning', 'N/A')}")
            
            details = cluster.get("details", {})
            output.append(f"   Details:")
            output.append(f"      Metric Trends: {details.get('metric_trends', 0)}")
            output.append(f"      Semantic Matches: {details.get('semantic_matches', 0)}")
    
    output.append("\n" + "=" * 80)
    return "\n".join(output)


def run_with_rules_only():
    """Run demo using deterministic rules only (no LLM)."""
    logger.info("Starting Multi-Agent Demo (RULES MODE - No LLM)")
    
    # Create sample alerts
    alerts = create_sample_alerts()
    logger.info(f"Created {len(alerts)} sample alerts")
    
    # Step 1: Run analyst agent
    logger.info("Step 1: Running Analyst Agent (correlation + enrichment)...")
    from src.agents.multi_agent.tools import analyst_agent, judge_agent, reporter_agent
    
    alerts_json = json.dumps(alerts)
    analysis = analyst_agent(alerts_json)
    analysis_dict = json.loads(analysis)
    
    print("\n" + "=" * 80)
    print("ANALYST RESULTS")
    print("=" * 80)
    print(json.dumps(analysis_dict, indent=2)[:800] + "\n...")
    
    # Step 2: Run judge agent
    logger.info("Step 2: Running Judge Agent (decision generation)...")
    decisions = judge_agent(analysis)
    decisions_dict = json.loads(decisions)
    
    print("\n" + "=" * 80)
    print("JUDGE RESULTS")
    print("=" * 80)
    print(json.dumps(decisions_dict, indent=2)[:800] + "\n...")
    
    # Step 3: Run reporter agent
    logger.info("Step 3: Running Reporter Agent (report generation)...")
    report = reporter_agent(decisions)
    report_dict = json.loads(report)
    
    # Display final report
    print(format_report(report_dict))
    
    logger.info("Demo complete!")


def run_with_github_models():
    """Run demo using GitHub Models for intelligent routing."""
    logger.info("Starting Multi-Agent Demo (GITHUB MODELS MODE)")
    
    # Check for GITHUB_TOKEN
    import os
    if not os.environ.get("GITHUB_TOKEN"):
        logger.error("❌ GITHUB_TOKEN environment variable not set")
        logger.error("   Set it with: export GITHUB_TOKEN='your-github-token'")
        sys.exit(1)
    
    from src.agents.multi_agent.supervisor import SupervisorAgent
    
    # Initialize supervisor with GitHub Models
    logger.info("Initializing Supervisor with GitHub Models...")
    try:
        supervisor = SupervisorAgent(model="github")
    except Exception as e:
        logger.error(f"❌ Failed to initialize with GitHub Models: {e}")
        logger.error("   Ensure GITHUB_TOKEN is set and has 'models:use' scope")
        sys.exit(1)
    
    # Create sample alerts
    alerts = create_sample_alerts()
    logger.info(f"Created {len(alerts)} sample alerts")
    
    # Process through multi-agent pipeline
    logger.info("Routing to supervisor for intelligent processing...")
    report = supervisor.process_alerts(alerts)
    
    # Display report
    print(format_report(report))
    
    logger.info("Demo complete!")


def main():
    """Main entry point."""
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "rules"
    
    if mode == "github":
        run_with_github_models()
    elif mode == "rules":
        run_with_rules_only()
    else:
        print("Usage: python examples/multi_agent_demo.py [rules|github]")
        print()
        print("  rules   - Run with deterministic rules only (no LLM)")
        print("  github  - Run with GitHub Models for intelligent routing")
        sys.exit(1)


if __name__ == "__main__":
    main()
