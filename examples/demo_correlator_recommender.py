#!/usr/bin/env python3
"""
Interactive example: demonstrate AlertCorrelator and RecommendationEngine
with sample alert data.

This example shows:
1. How alerts are clustered by fingerprint, service+alertname
2. How recommendations are generated based on cluster patterns
3. The complete data flow through correlator → recommender
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.grafana_alert_analysis.correlator import AlertCorrelator
from src.agents.grafana_alert_analysis.recommender import RecommendationEngine


# Sample alert data (simulating Grafana alert format)
SAMPLE_ALERTS = [
    {
        "fingerprint": "abc123",
        "labels": {
            "alertname": "HighErrorRate",
            "service": "api-gateway",
            "severity": "critical",
        },
        "state": "firing",
    },
    {
        "fingerprint": "abc123",  # Same fingerprint → same cluster
        "labels": {
            "alertname": "HighErrorRate",
            "service": "api-gateway",
            "severity": "critical",
        },
        "state": "firing",
    },
    {
        "fingerprint": "def456",
        "labels": {
            "alertname": "HighMemoryUsage",
            "service": "database",
            "severity": "warning",
        },
        "state": "firing",
    },
    {
        "fingerprint": "ghi789",
        "labels": {
            "alertname": "SlowResponse",
            "service": "api-gateway",  # Same service as cluster 1
            "severity": "low",
        },
        "state": "firing",
    },
    {
        "fingerprint": "jkl012",
        "labels": {
            "alertname": "SlowResponse",
            "service": "api-gateway",
            "severity": "low",
        },
        "state": "firing",
    },
    # Add more low-severity duplicates to trigger CLOSE recommendation
    *[
        {
            "fingerprint": f"low{i}",
            "labels": {
                "alertname": "MinorLatencySpike",
                "service": "cdn",
                "severity": "low",
            },
            "state": "firing",
        }
        for i in range(6)
    ],
]


def main() -> None:
    """Run the correlation and recommendation pipeline on sample data."""
    print("=" * 80)
    print("ALERT CORRELATION & RECOMMENDATION DEMO")
    print("=" * 80)
    print(f"Input: {len(SAMPLE_ALERTS)} sample alerts\n")

    # Step 1: Correlate alerts into clusters
    print("📊 Step 1: Clustering alerts...")
    correlator = AlertCorrelator()
    clusters = correlator.cluster(SAMPLE_ALERTS)
    print(f"✓ Created {len(clusters)} clusters\n")

    # Step 2: Generate recommendations
    print("🤖 Step 2: Generating recommendations...")
    recommender = RecommendationEngine()
    recommendations = recommender.recommend(clusters)
    print(f"✓ Generated {len(recommendations)} recommendations\n")

    # Step 3: Display results
    print("=" * 80)
    print("CLUSTERS")
    print("=" * 80)
    for i, cluster in enumerate(clusters, 1):
        print(f"\n{i}. Cluster ID: {cluster['cluster_id'][:16]}...")
        print(f"   Service: {cluster.get('service', 'N/A')}")
        print(f"   Alert Name: {cluster.get('alertname', 'N/A')}")
        print(f"   Severity: {cluster.get('severity', 'N/A')}")
        print(f"   Alert Count: {cluster.get('count', 0)}")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. Cluster: {rec.cluster_id[:16]}...")
        print(f"   Services: {', '.join(rec.services)}")
        print(f"   Severity: {rec.severity}")
        print(f"   ⚡ Action: {rec.recommended_action}")
        print(f"   💡 Hypothesis: {rec.root_cause_hypothesis}")
        print(f"   🎯 Confidence: {rec.confidence:.1%}")

    # Step 4: Export as JSON
    print("\n" + "=" * 80)
    print("JSON EXPORT")
    print("=" * 80)
    output = {
        "clusters": clusters,
        "recommendations": [r.model_dump() for r in recommendations],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))

    # Step 5: Interpretation guide
    print("\n" + "=" * 80)
    print("INTERPRETATION GUIDE")
    print("=" * 80)
    print("""
Correlation Logic:
- Alerts with identical 'fingerprint' → same cluster
- Alerts with same service + alertname → same cluster

Recommendation Rules:
- HIGH count (>5) + LOW severity → CLOSE (likely noise)
- CRITICAL severity → ESCALATE (needs immediate attention)
- Other patterns → OBSERVE (requires investigation)

Next Steps:
1. Review ESCALATE recommendations immediately
2. Investigate OBSERVE patterns for root causes
3. Consider silencing/adjusting CLOSE candidates
    """)


if __name__ == "__main__":
    main()
