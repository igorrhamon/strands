# 📊 Historical Replay Validation Report – Official Template

Este documento define a estrutura formal para a Fase de Validação de Replay Histórico do Strands.

**Objetivo**: Avaliar quantitativamente o alinhamento, segurança e performance contra alertas históricos antes de qualquer piloto controlado.

---

## 1️⃣ Executive Summary
- **Total de alertas avaliados**: 
- **Período coberto**: 
- **Categorias de alertas incluídas**: 
- **Taxa de alinhamento (%)**: 
- **Precisão de alta confiança (%)**: 
- **Taxa de override humano simulada (%)**: 
- **Latência média de decisão (ms)**: 

**Conclusão Executiva**:
*(Ex: "O Strands demonstra 82% de alinhamento com decisões humanas históricas, com zero recomendações autônomas inseguras.")*

---

## 2️⃣ Dataset Definition
### 2.1 Critérios de Seleção
- Apenas incidentes encerrados.
- Decisão humana documentada disponível.
- Runbook ou rastro de remediação registrado.

### 2.2 Distribuição
| Categoria | Contagem |
| :--- | :--- |
| SLA Breach | |
| Database Incident | |
| CPU/Resource Spike | |
| Network Failure | |
| Security Alert | |

---

## 3️⃣ Replay Configuration
- **confidence_model_version**: 
- **weight_matrix_version**: 
- **embedding_model_version**: 
- **runbook_index_version**: 
- **algorithm_name**: 
- **environment**: (isolated / containerized)

*Todos os replays devem ser determinísticos e reprodutíveis.*

---

## 4️⃣ Quantitative Results
### 4.1 Alinhamento de Decisão
**Definição**: Alinhamento = % de casos onde `decision_type` do Strands == decisão humana histórica.

| Métrica | Valor |
| :--- | :--- |
| Total avaliado | |
| Matches exatos | |
| Divergências | |
| Taxa de alinhamento | |

**Análise de Divergência**:
- Falsos positivos: 
- Falsos negativos: 
- Over-escalations: 
- Under-escalations: 

### 4.2 Calibração de Confiança
| Faixa de Confiança | Casos | Correção (%) |
| :--- | :--- | :--- |
| 0.50–0.69 | | |
| 0.70–0.84 | | |
| 0.85–1.00 | | |

**Meta**: Maior confiança → maior taxa de acerto.

---

## 5️⃣ Failure Case Deep Dive
Para cada divergência significativa:
- **Case ID**: 
- **Tipo de Alerta**: 
- **Decisão Histórica**: 
- **Decisão Strands**: 
- **Score de Confiança**: 
- **Causa Raiz da Divergência**: 
- **Ajuste de Peso Necessário?** (S/N)
- **Gap de Runbook Identificado?** (S/N)

---

## 6️⃣ Final Committee Recommendation
- [ ] Prosseguir para piloto limitado (shadow mode)
- [ ] Requer calibração adicional
- [ ] Expandir dataset e re-executar validação
- [ ] Rejeitar versão atual do modelo

---

## 📌 Governance Note
Este relatório deve ser arquivado junto com:
- Snapshot do dataset de replay.
- Identificadores de versão do modelo.
- Versão da matriz de pesos.
- Commit SHA utilizado.
