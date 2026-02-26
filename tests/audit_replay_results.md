# 📊 Historical Replay Validation Report – Auto-Generated

Este relatório foi gerado automaticamente pelo pipeline de validação do Strands.

---

## 1️⃣ Executive Summary
- **Total de alertas avaliados**: 50
- **Timestamp da Execução**: 2026-02-11T17:04:28.933259
- **Taxa de alinhamento (%)**: 92.00%
- **Precisão de alta confiança (%)**: 100.00%
- **Latência média de decisão (ms)**: 2517.73 ms
- **Bypasses Inseguros (CRITICAL)**: 0

**Conclusão Executiva**:
✅ APROVADO: O sistema demonstra alta precisão e zero bypasses inseguros.

---

## 2️⃣ Replay Configuration (Auditability)
- **Generator Version**: 1.1
- **Random Seed**: 12345
- **Auto-Approval Threshold**: 0.85
- **Environment**: isolated-validation

---

## 3️⃣ Quantitative Results
### 3.1 Alinhamento de Decisão
| Métrica | Valor |
| :--- | :--- |
| Total avaliado | 50 |
| Matches exatos | 46 |
| Taxa de alinhamento | 92.00% |

### 3.2 Calibração de Confiança
| Faixa de Confiança | Casos | Precisão (%) |
| :--- | :--- | :--- |
| 0.50–0.69 | 3 | 0.00% |
| 0.70–0.84 | 17 | 94.12% |
| 0.85–1.00 | 30 | 100.00% |

---

## 4️⃣ Unsafe Recommendation Analysis (Segurança)
| Métrica | Valor |
| :--- | :--- |
| Decisões incorretas de alto risco | 1 |
| Bypasses Inseguros (Alta Confiança + Erro Crítico) | 0 |

> **Regra de Ouro**: Nenhuma decisão incorreta de alto risco pode ser classificada como auto-aprovável. Status: ✅ PASS

---

## 📌 Governance Note
Este relatório é um artefato auditável e deve ser arquivado junto ao commit SHA correspondente.
