#!/usr/bin/env python3
"""
Example demonstrating the full Grafana Alert Analysis Agent workflow:
- Fetch alerts via MCP
- Cluster alerts using AlertCorrelator
- Generate recommendations via RecommendationEngine
- Display structured output
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.grafana_alert_analysis.agent import GrafanaAlertAgent
from src.agents.grafana_alert_analysis.schemas import AgentInput
from src.agents.grafana_alert_analysis.tools.grafana_mcp import list_alert_rules


def main() -> None:
    """Run the agent with full correlation and recommendation workflow."""
    start = os.environ.get("GRAFANA_FROM", "now-6h")
    end = os.environ.get("GRAFANA_TO", "now")
    environment = os.environ.get("ENVIRONMENT", "local")

    print("=" * 80)
    print("GRAFANA ALERT ANALYSIS AGENT - FULL WORKFLOW")
    print("=" * 80)
    print(f"Time Range: {start} → {end}")
    print(f"Environment: {environment}\n")

    # Step 1: Run the agent (includes correlation + recommendations)
    print("📊 Running agent analysis...")
    agent = GrafanaAlertAgent()
    output = agent.run(
        AgentInput(
            start=start,
            end=end,
            environment=environment,
            filters=None,
            dashboard_url=None,
        )
    )

    print(f"✓ Agent completed: {output.summary}\n")

    # Step 2: Display recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if not output.recommendations:
        print("ℹ️  No recommendations generated (no alerts found or all alerts filtered).\n")
    else:
        for i, rec in enumerate(output.recommendations, 1):
            print(f"\n{i}. Cluster: {rec.cluster_id[:12]}...")
            print(f"   Severity: {rec.severity}")
            print(f"   Services: {', '.join(rec.services) if rec.services else 'N/A'}")
            print(f"   Action: {rec.recommended_action}")
            print(f"   Hypothesis: {rec.root_cause_hypothesis}")
            print(f"   Confidence: {rec.confidence:.1%}")

    # Step 3: Raw alert rules for comparison
    print("\n" + "=" * 80)
    print("RAW ALERT RULES (for reference)")
    print("=" * 80)
    
    rules = list_alert_rules()
    print(f"Total rules fetched: {len(rules)}")
    
    if rules:
        firing = [r for r in rules if isinstance(r, dict) and str(r.get("state", "")).lower() == "firing"]
        normal = [r for r in rules if isinstance(r, dict) and str(r.get("state", "")).lower() == "normal"]
        pending = [r for r in rules if isinstance(r, dict) and str(r.get("state", "")).lower() == "pending"]
        
        print(f"  - Firing: {len(firing)}")
        print(f"  - Normal: {len(normal)}")
        print(f"  - Pending: {len(pending)}")
        print(f"  - Other: {len(rules) - len(firing) - len(normal) - len(pending)}")
    
    # Step 4: Export full output as JSON
    print("\n" + "=" * 80)
    print("JSON OUTPUT (for processing)")
    print("=" * 80)
    
    json_output = {
        "summary": output.summary,
        "recommendations": [r.model_dump() for r in output.recommendations],
        "time_range": {"start": start, "end": end},
        "environment": environment,
        "raw_rules_count": len(rules),
    }
    
    print(json.dumps(json_output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
