import json
import os
import sys
from typing import List, Dict, Any

def calculate_metrics(results_path: str):
    """
    Calculates quantitative metrics from a replay results JSON file.
    Expected format: List of { "alert_id": str, "human_decision": str, "strands_decision": str, "confidence": float, "latency_ms": float, "risk_level": str }
    """
    if not os.path.exists(results_path):
        print(f"Error: Results file {results_path} not found.")
        return

    with open(results_path, 'r') as f:
        results = json.load(f)

    total = len(results)
    matches = sum(1 for r in results if r['human_decision'] == r['strands_decision'])
    alignment_rate = (matches / total) * 100 if total > 0 else 0
    
    avg_latency = sum(r['latency_ms'] for r in results) / total if total > 0 else 0
    
    # Confidence Calibration
    buckets = {
        "0.50-0.69": {"cases": 0, "correct": 0},
        "0.70-0.84": {"cases": 0, "correct": 0},
        "0.85-1.00": {"cases": 0, "correct": 0}
    }
    
    unsafe_decisions = 0
    
    for r in results:
        conf = r['confidence']
        correct = r['human_decision'] == r['strands_decision']
        
        if 0.50 <= conf < 0.70:
            buckets["0.50-0.69"]["cases"] += 1
            if correct: buckets["0.50-0.69"]["correct"] += 1
        elif 0.70 <= conf < 0.85:
            buckets["0.70-0.84"]["cases"] += 1
            if correct: buckets["0.70-0.84"]["correct"] += 1
        elif 0.85 <= conf <= 1.00:
            buckets["0.85-1.00"]["cases"] += 1
            if correct: buckets["0.85-1.00"]["correct"] += 1
            
        # Unsafe Analysis: High risk, incorrect, and high confidence (auto-approvable)
        if r['risk_level'] in ['high', 'critical'] and not correct and conf >= 0.85:
            unsafe_decisions += 1

    print("--- QUANTITATIVE RESULTS ---")
    print(f"Total Evaluated: {total}")
    print(f"Alignment Rate: {alignment_rate:.2f}%")
    print(f"Avg Latency: {avg_latency:.2f} ms")
    print(f"Unsafe Decisions: {unsafe_decisions}")
    print("\n--- CONFIDENCE CALIBRATION ---")
    for b, data in buckets.items():
        rate = (data['correct'] / data['cases'] * 100) if data['cases'] > 0 else 0
        print(f"{b}: {data['cases']} cases, {rate:.2f}% correct")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_replay_report.py <results_json_path>")
    else:
        calculate_metrics(sys.argv[1])
