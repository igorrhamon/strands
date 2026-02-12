import json
import random

def generate_mock_data(count=50):
    categories = ["SLA Breach", "Database Incident", "CPU/Resource Spike", "Network Failure", "Security Alert"]
    risks = ["low", "medium", "high", "critical"]
    decisions = ["restart_pod", "scale_up", "manual_intervention", "ignore", "flush_cache"]
    
    results = []
    for i in range(count):
        category = random.choice(categories)
        risk = "critical" if category == "Security Alert" else random.choice(risks)
        
        # Simulate Strands behavior
        # Higher risk cases tend to have lower confidence or require manual intervention
        human_decision = random.choice(decisions)
        
        # 85% alignment simulation
        if random.random() < 0.85:
            strands_decision = human_decision
            # Correct decisions tend to have higher confidence
            confidence = random.uniform(0.75, 0.98)
        else:
            strands_decision = random.choice(decisions)
            # Incorrect decisions often have lower confidence (system is unsure)
            confidence = random.uniform(0.55, 0.88)
            
        results.append({
            "alert_id": f"ALRT-{2026}-{i:03d}",
            "category": category,
            "risk_level": risk,
            "human_decision": human_decision,
            "strands_decision": strands_decision,
            "confidence": round(confidence, 2),
            "latency_ms": random.uniform(800, 4500)
        })
        
    with open('/home/ubuntu/strands/tests/mock_replay_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Generated {count} mock incidents in /home/ubuntu/strands/tests/mock_replay_results.json")

if __name__ == "__main__":
    generate_mock_data()
