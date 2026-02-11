import json
import random
import os
import datetime
from pathlib import Path
from typing import Optional, Dict

def generate_mock_data(count: int = 50, output_path: Optional[str] = None):
    """
    Generates a structured dataset for historical replay validation.
    Follows institutional safety rules: high-risk errors must have low confidence.
    """
    # 1. Determinism (Institutional Requirement)
    seed = int(os.getenv("REPLAY_SEED", "42"))
    random.seed(seed)

    # 2. Configuration (Institutional Requirement)
    if output_path is None:
        output_path = os.getenv(
            "REPLAY_OUTPUT_PATH",
            str(Path("tests/institutional_replay_results.json"))
        )
    
    auto_approval_threshold = float(os.getenv("AUTO_APPROVAL_THRESHOLD", "0.85"))
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 3. Category-based Alignment (Realistic Simulation)
    category_alignment = {
        "SLA Breach": 0.92,
        "Database Incident": 0.85,
        "CPU/Resource Spike": 0.90,
        "Network Failure": 0.82,
        "Security Alert": 0.78
    }
    
    risks = ["low", "medium", "high", "critical"]
    decisions = ["restart_pod", "scale_up", "manual_intervention", "ignore", "flush_cache"]
    
    results = []
    for i in range(count):
        category = random.choice(list(category_alignment.keys()))
        risk = "critical" if category == "Security Alert" else random.choice(risks)
        human_decision = random.choice(decisions)
        
        # Simulate realistic behavior based on category
        target_alignment = category_alignment[category]
        is_aligned = random.random() < target_alignment
        
        if is_aligned:
            strands_decision = human_decision
            confidence = random.uniform(0.75, 0.98)
        else:
            strands_decision = random.choice([d for d in decisions if d != human_decision])
            
            # CRITICAL SAFETY RULE: 
            # If it's an error in a high-risk case, confidence MUST be low to trigger review.
            if risk in ["high", "critical"]:
                confidence = random.uniform(0.50, auto_approval_threshold - 0.15)
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
            "latency_ms": round(random.uniform(800, 4500), 2)
        })
    
    # 4. Metadata (Auditability Requirement)
    output_data = {
        "metadata": {
            "generator_version": "1.1",
            "seed": seed,
            "timestamp": datetime.datetime.now().isoformat(),
            "auto_approval_threshold": auto_approval_threshold,
            "category_alignment_targets": category_alignment
        },
        "results": results
    }
        
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"[REPLAY] Generated {count} incidents with seed {seed} at: {output_path}")

if __name__ == "__main__":
    generate_mock_data()
