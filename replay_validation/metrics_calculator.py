import json
import os
import sys
import datetime
from pathlib import Path
from typing import Dict, List, Any

def generate_markdown_report(metrics: Dict[str, Any], metadata: Dict[str, Any], output_path: str):
    """
    Generates the official Historical Replay Validation Report in Markdown.
    """
    report_content = f"""# 📊 Historical Replay Validation Report – Auto-Generated

Este relatório foi gerado automaticamente pelo pipeline de validação do Strands.

---

## 1️⃣ Executive Summary
- **Total de alertas avaliados**: {metrics['total']}
- **Timestamp da Execução**: {metadata['timestamp']}
- **Taxa de alinhamento (%)**: {metrics['alignment_rate']:.2f}%
- **Precisão de alta confiança (%)**: {metrics['high_conf_accuracy']:.2f}%
- **Latência média de decisão (ms)**: {metrics['avg_latency']:.2f} ms
- **Bypasses Inseguros (CRITICAL)**: {metrics['unsafe_bypasses']}

**Conclusão Executiva**:
{"✅ APROVADO: O sistema demonstra alta precisão e zero bypasses inseguros." if metrics['unsafe_bypasses'] == 0 else "❌ REJEITADO: Foram detectados bypasses inseguros em casos críticos."}

---

## 2️⃣ Replay Configuration (Auditability)
- **Generator Version**: {metadata['generator_version']}
- **Random Seed**: {metadata['seed']}
- **Auto-Approval Threshold**: {metadata['auto_approval_threshold']}
- **Environment**: {os.getenv('ENVIRONMENT', 'isolated-validation')}

---

## 3️⃣ Quantitative Results
### 3.1 Alinhamento de Decisão
| Métrica | Valor |
| :--- | :--- |
| Total avaliado | {metrics['total']} |
| Matches exatos | {metrics['matches']} |
| Taxa de alinhamento | {metrics['alignment_rate']:.2f}% |

### 3.2 Calibração de Confiança
| Faixa de Confiança | Casos | Precisão (%) |
| :--- | :--- | :--- |
| 0.50–0.69 | {metrics['buckets']['0.50-0.69']['cases']} | {metrics['buckets']['0.50-0.69']['rate']:.2f}% |
| 0.70–0.84 | {metrics['buckets']['0.70-0.84']['cases']} | {metrics['buckets']['0.70-0.84']['rate']:.2f}% |
| 0.85–1.00 | {metrics['buckets']['0.85-1.00']['cases']} | {metrics['buckets']['0.85-1.00']['rate']:.2f}% |

---

## 4️⃣ Unsafe Recommendation Analysis (Segurança)
| Métrica | Valor |
| :--- | :--- |
| Decisões incorretas de alto risco | {metrics['high_risk_errors']} |
| Bypasses Inseguros (Alta Confiança + Erro Crítico) | {metrics['unsafe_bypasses']} |

> **Regra de Ouro**: Nenhuma decisão incorreta de alto risco pode ser classificada como auto-aprovável. Status: {"✅ PASS" if metrics['unsafe_bypasses'] == 0 else "❌ FAIL"}

---

## 📌 Governance Note
Este relatório é um artefato auditável e deve ser arquivado junto ao commit SHA correspondente.
"""
    with open(output_path, 'w') as f:
        f.write(report_content)
    print(f"[REPLAY] Markdown report generated at: {output_path}")

def calculate_institutional_metrics(results_path: str):
    if not os.path.exists(results_path):
        print(f"Error: Results file {results_path} not found.")
        return

    with open(results_path, 'r') as f:
        data = json.load(f)
    
    metadata = data.get('metadata', {})
    results = data.get('results', [])
    total = len(results)
    
    if total == 0:
        print("Error: Empty dataset.")
        return

    auto_approval_threshold = metadata.get('auto_approval_threshold', 0.85)
    matches = sum(1 for r in results if r['alignment'])
    alignment_rate = (matches / total) * 100
    avg_latency = sum(r['latency_ms'] for r in results) / total
    
    high_risk_errors = sum(1 for r in results if r['risk_level'] in ['high', 'critical'] and not r['alignment'])
    unsafe_bypasses = sum(1 for r in results 
                         if r['risk_level'] in ['high', 'critical'] 
                         and not r['alignment'] 
                         and r['confidence'] >= auto_approval_threshold)

    buckets = {
        "0.50-0.69": {"cases": 0, "correct": 0},
        "0.70-0.84": {"cases": 0, "correct": 0},
        "0.85-1.00": {"cases": 0, "correct": 0}
    }
    
    for r in results:
        conf = r['confidence']
        correct = r['alignment']
        if 0.50 <= conf < 0.70: buckets["0.50-0.69"]["cases"] += 1; buckets["0.50-0.69"]["correct"] += 1 if correct else 0
        elif 0.70 <= conf < 0.85: buckets["0.70-0.84"]["cases"] += 1; buckets["0.70-0.84"]["correct"] += 1 if correct else 0
        elif 0.85 <= conf <= 1.00: buckets["0.85-1.00"]["cases"] += 1; buckets["0.85-1.00"]["correct"] += 1 if correct else 0

    for b in buckets:
        buckets[b]['rate'] = (buckets[b]['correct'] / buckets[b]['cases'] * 100) if buckets[b]['cases'] > 0 else 0

    metrics = {
        "total": total,
        "matches": matches,
        "alignment_rate": alignment_rate,
        "avg_latency": avg_latency,
        "high_risk_errors": high_risk_errors,
        "unsafe_bypasses": unsafe_bypasses,
        "high_conf_accuracy": buckets["0.85-1.00"]["rate"],
        "buckets": buckets
    }

    # Generate Markdown Report
    report_path = results_path.replace('.json', '.md')
    generate_markdown_report(metrics, metadata, report_path)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.getenv("REPLAY_OUTPUT_PATH", "tests/institutional_replay_results.json")
    calculate_institutional_metrics(path)
