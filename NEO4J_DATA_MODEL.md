# 🗄️ Modelo de Dados Neo4j - Strands Adaptive System

## Visão Geral

Este documento descreve o modelo de dados do grafo utilizado pelo Strands para persistência de conhecimento, execução e aprendizado adaptativo. O modelo foi desenhado para suportar **atualizações incrementais atômicas**, **rastreabilidade completa** e **análise de tendências**.

---

## 🏷️ Nós (Nodes)

### `Playbook`
Representa um procedimento de remediação versionado.

| Propriedade | Tipo | Descrição | Atualização |
|-------------|------|-----------|-------------|
| `playbook_id` | String (UUID) | Identificador único | Imutável |
| `status` | Enum | DRAFT, ACTIVE, ARCHIVED | Transacional |
| `pattern_type` | String | Tipo de padrão (ex: LOG_METRIC) | Imutável |
| `service_name` | String | Serviço alvo | Imutável |
| `total_executions` | Integer | Contador total de execuções | **Incremental** |
| `success_count` | Integer | Contador de sucessos | **Incremental** |
| `failure_count` | Integer | Contador de falhas | **Incremental** |
| `success_rate` | Float (0-1) | Taxa de sucesso (success/total) | **Recalculado** |
| `avg_duration` | Float | Média móvel de duração (s) | **Welford** |
| `m2_duration` | Float | Soma dos quadrados das diferenças | **Welford** |
| `last_executed_at` | DateTime | Timestamp da última execução | Transacional |

### `PlaybookExecution`
Representa uma instância de execução de um playbook.

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| `execution_id` | String (UUID) | Identificador único |
| `timestamp` | DateTime | Início da execução |
| `duration` | Float | Duração total em segundos |
| `success` | Boolean | Resultado da execução |
| `feedback` | String | Notas opcionais de feedback |

### `Pattern`
Representa um padrão de incidente detectado.

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| `pattern_id` | String | Hash do padrão |
| `type` | String | Tipo de correlação |

---

## 🔗 Relacionamentos (Relationships)

### `(:PlaybookExecution)-[:EXECUTED_BY]->(:Playbook)`
Vincula uma execução ao playbook utilizado.
- **Cardinalidade:** N:1

### `(:Playbook)-[:REMEDIES]->(:Pattern)`
Indica que um playbook resolve um tipo específico de padrão.
- **Cardinalidade:** N:M

### `(:Playbook)-[:TARGETS]->(:Service)`
Indica o serviço alvo do playbook.
- **Cardinalidade:** N:1

---

## 🧮 Algoritmos de Atualização

### 1. Média e Variância Incremental (Welford's Algorithm)
Para evitar recomputação custosa e garantir precisão numérica, utilizamos o algoritmo de Welford para atualizar `avg_duration` e `m2_duration` a cada nova execução.

**Fórmulas:**
```python
delta = new_duration - old_mean
new_mean = old_mean + delta / new_total_count
new_m2 = old_m2 + delta * (new_duration - new_mean)
```

**Desvio Padrão (Derivado):**
```python
std_dev = sqrt(m2 / (total_count - 1))
```

### 2. Score Adaptativo
Utilizado para rankear playbooks durante a recomendação.

**Fórmula:**
```python
Score = CorrelationConfidence * SuccessRate * log(1 + TotalExecutions)
```
- **CorrelationConfidence:** Força da correlação detectada (0-1)
- **SuccessRate:** Histórico de eficácia (0-1)
- **log(1 + TotalExecutions):** Boost logarítmico para volume (recompensa experiência)

---

## 🔒 Controle de Concorrência

Todas as atualizações de estatísticas (`update_execution`) são executadas como **transações atômicas** no Neo4j. Isso garante que, mesmo com múltiplas execuções simultâneas, os contadores e médias sejam atualizados corretamente sem condições de corrida (race conditions).

---

## 📊 Índices de Performance

- `(:Playbook(playbook_id))` - UNIQUE CONSTRAINT
- `(:PlaybookExecution(execution_id))` - UNIQUE CONSTRAINT
- `(:Playbook(status))` - INDEX
- `(:PlaybookExecution(timestamp))` - INDEX (para queries de janela temporal)
