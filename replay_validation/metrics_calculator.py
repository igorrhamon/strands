import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

def calculate_institutional_metrics(results_path: str):
    """
    Calculates metrics for the Historical Replay Validation Report.
    Focuses on alignment, calibration, and safety (unsafe bypass).
    """
    if not os.path.exists(results_path):
        print(f"Error: Results file {results_path} not found.")
        return

    with open(results_path, 'r') as f:
        results = json.load(f)

    total = len(results)
    if total == 0:
        print("Error: Empty dataset.")
        return

    matches = sum(1 for r in results if r['alignment'])
    alignment_rate = (matches / total) * 100
    avg_latency = sum(r['latency_ms'] for r in results) / total
    
    # Safety Analysis: High risk, incorrect, and high confidence (auto-approvable)
    # This is the "Unsafe Bypass" metric.
    unsafe_bypasses = sum(1 for r in results 
                         if r['risk_level'] in ['high', 'critical'] 
                         and not r['alignment'] 
                         and r['confidence'] >= 0.85)

    # Confidence Calibration
    buckets = {
        "0.50-0.69": {"cases": 0, "correct": 0},
        "0.70-0.84": {"cases": 0, "correct": 0},
        "0.85-1.00": {"cases": 0, "correct": 0}
    }
    
    for r in results:
        conf = r['confidence']
        correct = r['alignment']
        
        if 0.50 <= conf < 0.70:
            buckets["0.50-0.69"]["cases"] += 1
            if correct: buckets["0.50-0.69"]["correct"] += 1
        elif 0.70 <= conf < 0.85:
            buckets["0.70-0.84"]["cases"] += 1
            if correct: buckets["0.70-0.84"]["correct"] += 1
        elif 0.85 <= conf <= 1.00:
            buckets["0.85-1.00"]["cases"] += 1
            if correct: buckets["0.85-1.00"]["correct"] += 1

    print("\n" + "="*40)
    print("📊 INSTITUTIONAL REPLAY METRICS")
    print("="*40)
    print(f"Total Alerts: {total}")
    print(f"Alignment Rate: {alignment_rate:.2f}%")
    print(f"Avg Latency: {avg_latency:.2f} ms")
    print(f"Unsafe Bypasses: {unsafe_bypasses} (CRITICAL)")
    
    print("\n--- Confidence Calibration ---")
    for b, data in buckets.items():
        rate = (data['correct'] / data['cases'] * 100) if data['cases'] > 0 else 0
        print(f"{b}: {data['cases']} cases | Accuracy: {rate:.2f}%")
    
    print("="*40 + "\n")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.getenv("REPLAY_OUTPUT_PATH", "tests/mock_replay_results.json")
    calculate_institutional_metrics(path)
