import json
import random
import os
from pathlib import Path
from typing import Optional

def generate_mock_data(count: int = 50, output_path: Optional[str] = None):
    """
    Generates a structured dataset for historical replay validation.
    Follows institutional safety rules: high-risk errors must have low confidence.
    """
    # Architectural correction: Use ENV or Pathlib, no hardcoded strings
    if output_path is None:
        output_path = os.getenv(
            "REPLAY_OUTPUT_PATH",
            str(Path("tests/mock_replay_results.json"))
        )
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    categories = ["SLA Breach", "Database Incident", "CPU/Resource Spike", "Network Failure", "Security Alert"]
    risks = ["low", "medium", "high", "critical"]
    decisions = ["restart_pod", "scale_up", "manual_intervention", "ignore", "flush_cache"]
    
    results = []
    for i in range(count):
        category = random.choice(categories)
        risk = "critical" if category == "Security Alert" else random.choice(risks)
        human_decision = random.choice(decisions)
        
        # Simulate realistic behavior (88% alignment)
        is_aligned = random.random() < 0.88
        
        if is_aligned:
            strands_decision = human_decision
            # High alignment usually comes with high confidence
            confidence = random.uniform(0.75, 0.98)
        else:
            strands_decision = random.choice([d for d in decisions if d != human_decision])
            
            # CRITICAL SAFETY RULE: 
            # If it's an error in a high-risk case, confidence MUST be low to trigger review.
            if risk in ["high", "critical"]:
                confidence = random.uniform(0.50, 0.68)
            else:
                confidence = random.uniform(0.55, 0.85)
            
        results.append({
            "alert_id": f"ALRT-2026-{i:03d}",
            "category": category,
            "risk_level": risk,
            "human_decision": human_decision,
            "strands_decision": strands_decision,
            "confidence": round(confidence, 2),
            "alignment": is_aligned,
            "requires_review_simulated": confidence < 0.85 or risk in ["high", "critical"],
            "latency_ms": round(random.uniform(800, 4500), 2)
        })
        
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"[REPLAY] Generated {count} incidents at: {output_path}")

if __name__ == "__main__":
    generate_mock_data()
