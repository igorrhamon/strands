# 🧠 Motor de Aprendizado Autônomo - Strands

## Visão Geral

O **Motor de Aprendizado Autônomo** permite que o Strands crie, aprenda e evolua suas próprias ações de remediação ao longo do tempo, transformando-o de um "executor de scripts" para um "aprendiz inteligente".

### Problema Resolvido

**Antes:** Sistema com 5 playbooks hardcoded. Quando um novo tipo de incidente ocorria, o sistema não sabia como responder.

**Depois:** Sistema que:
1. Reutiliza playbooks conhecidos (rápido, seguro)
2. Gera novos playbooks via LLM (criativo, adaptável)
3. Aprende com aprovação humana (confiável, evolutivo)

---

## 🔄 Arquitetura do Sistema

### Fluxo de Recomendação (Híbrido)

```
Alerta
  ↓
CorrelatorAgent (detecta padrão)
  ↓
RecommenderAgentWithLearning
  ├─ 1️⃣ Buscar no Neo4j (Playbooks ACTIVE)
  │   ├─ Encontrou? → Usar imediatamente
  │   └─ Não encontrou? → Ir para 2️⃣
  │
  ├─ 2️⃣ Gerar via LLM (PlaybookGeneratorAgent)
  │   ├─ Sucesso? → Armazenar como PENDING_REVIEW
  │   └─ Falha? → Ir para 3️⃣
  │
  └─ 3️⃣ Fallback (Ações sugeridas do Correlator)
      └─ Retornar com status FALLBACK
  ↓
Humano Aprova/Rejeita (se PENDING_REVIEW)
  ├─ Aprovado → Status muda para ACTIVE
  └─ Rejeitado → Status muda para ARCHIVED
  ↓
Próxima Vez (mesmo padrão)
  └─ Playbook ACTIVE é reutilizado
```

---

## 📦 Componentes Principais

### 1. Neo4jPlaybookStore

**Arquivo:** `src/core/neo4j_playbook_store.py`

Gerencia persistência de playbooks com workflow de curação.

#### Nós Neo4j

```
Playbook
├─ playbook_id (PK)
├─ title, description
├─ pattern_type (LOG_METRIC, METRIC_METRIC, etc)
├─ service_name
├─ status (DRAFT, PENDING_REVIEW, ACTIVE, DEPRECATED, ARCHIVED)
├─ source (HUMAN_WRITTEN, LLM_GENERATED, HYBRID)
├─ steps (JSON array)
├─ estimated_time_minutes
├─ automation_level (MANUAL, ASSISTED, FULL)
├─ risk_level (MINIMAL, LOW, MEDIUM, HIGH, CRITICAL)
├─ prerequisites, success_criteria
├─ rollback_procedure
├─ created_at, created_by
├─ updated_at, updated_by
├─ approved_at, approved_by
├─ executions_count, success_count, failure_count
└─ metadata (JSON)

PlaybookExecution
├─ execution_id (PK)
├─ playbook_id (FK)
├─ alert_fingerprint
├─ started_at, completed_at
├─ status (RUNNING, SUCCESS, FAILURE, PARTIAL)
├─ duration_seconds
├─ steps_executed, steps_total
├─ error_message, feedback
└─ metadata (JSON)
```

#### Relacionamentos

```
Playbook -[DETECTED_PATTERN]→ PlaybookExecution
PlaybookExecution -[TRIGGERED_BY]→ Alert
Playbook -[BELONGS_TO]→ Service
```

#### Métodos Principais

| Método | Descrição |
|--------|-----------|
| `store_playbook(playbook)` | Armazena novo playbook |
| `get_playbook(playbook_id)` | Recupera playbook por ID |
| `get_active_playbooks_for_pattern(pattern_type, service_name)` | Busca playbooks ativos |
| `get_pending_review_playbooks(limit)` | Playbooks aguardando aprovação |
| `approve_playbook(playbook_id, approved_by, notes)` | Aprova playbook |
| `reject_playbook(playbook_id, rejected_by, reason)` | Rejeita playbook |
| `record_execution(execution)` | Registra execução |
| `get_playbook_statistics(playbook_id)` | Estatísticas de execução |

---

### 2. PlaybookGeneratorAgent

**Arquivo:** `src/agents/governance/playbook_generator.py`

Gera playbooks dinamicamente usando LLM.

#### Fluxo

```
Padrão Desconhecido
  ↓
Construir Prompt (com evidências e dados de correlação)
  ↓
Chamar LLM (GPT-4, Claude, etc)
  ↓
Parsear Resposta JSON
  ↓
Criar Objeto Playbook
  ↓
Armazenar com Status PENDING_REVIEW
  ↓
Retornar para Aprovação Humana
```

#### Prompt para LLM

O agente constrói um prompt estruturado que inclui:

- **Tipo de Padrão:** LOG_METRIC, METRIC_METRIC, TEMPORAL, etc
- **Serviço Afetado:** Nome do serviço
- **Hipótese:** Análise da correlação
- **Evidências:** Dados coletados (logs, métricas, etc)
- **Ações Sugeridas:** Recomendações iniciais
- **Dados de Correlação:** r, p-value, lag, significância

#### Resposta Esperada (JSON)

```json
{
  "title": "Clear, descriptive title",
  "description": "Detailed description",
  "steps": [
    {
      "step": 1,
      "title": "Step title",
      "description": "Detailed description",
      "commands": ["command1", "command2"],
      "expected_output": "What to expect",
      "rollback_command": "How to undo"
    }
  ],
  "estimated_time_minutes": 30,
  "automation_level": "MANUAL|ASSISTED|FULL",
  "risk_level": "MINIMAL|LOW|MEDIUM|HIGH|CRITICAL",
  "prerequisites": ["Prerequisite 1"],
  "success_criteria": ["Criterion 1"],
  "rollback_procedure": "How to rollback",
  "notes": "Additional notes"
}
```

#### Métodos

| Método | Descrição |
|--------|-----------|
| `generate_playbook(...)` | Gera novo playbook via LLM |
| `_build_prompt(...)` | Constrói prompt estruturado |
| `_call_llm(prompt)` | Chama LLM (implementação mock) |
| `get_status()` | Status do agente |

---

### 3. RecommenderAgentWithLearning

**Arquivo:** `src/agents/governance/recommender_with_learning.py`

Recomenda ações com lookup híbrido (Neo4j + LLM).

#### Fluxo de Recomendação

```
Correlação Detectada
  ↓
Extrair Tipo de Padrão e Serviço
  ↓
1️⃣ Buscar Playbook ACTIVE no Neo4j
  ├─ Encontrou? → Usar (rápido, confiável)
  └─ Não? → Ir para 2️⃣
  ↓
2️⃣ Gerar Playbook via LLM
  ├─ Sucesso? → Armazenar como PENDING_REVIEW
  └─ Falha? → Ir para 3️⃣
  ↓
3️⃣ Fallback
  └─ Usar ações sugeridas do Correlator
  ↓
Retornar Recomendação
```

#### Métodos

| Método | Descrição |
|--------|-----------|
| `recommend(correlation_result, alert_fingerprint)` | Recomenda ações |
| `_lookup_active_playbook(pattern_type, service_name)` | Busca no Neo4j |
| `_calculate_playbook_score(playbook)` | Score baseado em sucesso |
| `approve_playbook(playbook_id, approved_by, notes)` | Aprova playbook |
| `reject_playbook(playbook_id, rejected_by, reason)` | Rejeita playbook |
| `get_pending_playbooks()` | Playbooks aguardando aprovação |

#### Estrutura de Recomendação

```json
{
  "decision_id": "uuid",
  "timestamp": "ISO8601",
  "status": "READY|REQUIRES_APPROVAL|FALLBACK",
  "source": "KNOWN|GENERATED|FALLBACK",
  "playbook": { /* Playbook object */ },
  "correlation": {
    "hypothesis": "...",
    "confidence": 0.91,
    "evidence_count": 8,
    "suggested_actions": [...]
  },
  "execution_steps": ["Step 1", "Step 2", ...],
  "estimated_duration_minutes": 30,
  "risk_assessment": {
    "risk_level": "MEDIUM",
    "requires_approval": false,
    "rollback_available": true
  }
}
```

---

## 🔄 Ciclo de Vida do Conhecimento

### Fase 1: Cold Start (Primeiras Execuções)

```
Novo Padrão Detectado
  ↓
LLM Gera Playbook
  ↓
Armazenado como PENDING_REVIEW
  ↓
SRE Humano Revisa
  ├─ Aprova → Status ACTIVE
  └─ Rejeita → Status ARCHIVED
```

**Tempo:** Minutos a horas (requer intervenção humana)

### Fase 2: Warm Start (Padrões Conhecidos)

```
Mesmo Padrão Detectado Novamente
  ↓
Buscar no Neo4j
  ↓
Playbook ACTIVE Encontrado
  ↓
Usar Imediatamente
```

**Tempo:** Milissegundos (sem LLM, sem humano)

### Fase 3: Evolution (Aprendizado Contínuo)

```
Playbook Executado
  ↓
Registrar Resultado (sucesso/falha)
  ↓
Atualizar Estatísticas
  ├─ success_count++
  └─ executions_count++
  ↓
Próximas Recomendações Favorecem Playbooks com Maior Taxa de Sucesso
```

---

## 📊 Exemplos de Uso

### Exemplo 1: Padrão Conhecido (Rápido)

```python
# Correlação detectada: LOG_METRIC para api-service
correlation = SwarmResult(
    hypothesis="Picos de erro em logs correlacionam com latência alta",
    confidence=0.95,
    evidence=[...],
    suggested_actions=[...]
)

# Recomendação
recommender = RecommenderAgentWithLearning(playbook_store, generator)
recommendation = recommender.recommend(correlation, alert_fingerprint)

# Resultado
{
  "status": "READY",
  "source": "KNOWN",
  "playbook": {
    "playbook_id": "pb-12345",
    "title": "Remediate High Error Rate",
    "status": "ACTIVE",
    "steps": [...]
  }
}
```

**Tempo:** ~10ms (lookup no Neo4j)

### Exemplo 2: Padrão Novo (Com LLM)

```python
# Correlação detectada: Padrão novo não reconhecido
correlation = SwarmResult(
    hypothesis="Correlação entre latência de DB e timeout de API",
    confidence=0.82,
    evidence=[...],
    suggested_actions=[...]
)

# Recomendação
recommendation = recommender.recommend(correlation, alert_fingerprint)

# Resultado
{
  "status": "REQUIRES_APPROVAL",
  "source": "GENERATED",
  "playbook": {
    "playbook_id": "pb-new-uuid",
    "title": "Investigate Database Connection Timeout",
    "status": "PENDING_REVIEW",
    "steps": [...]
  }
}
```

**Tempo:** ~5-10s (chamada LLM)

### Exemplo 3: Aprovação Humana

```python
# SRE revisa playbook gerado
playbook_id = "pb-new-uuid"

# Aprova
recommender.approve_playbook(
    playbook_id=playbook_id,
    approved_by="sre-john@company.com",
    notes="Tested and verified. Good for production."
)

# Próxima vez, será reutilizado automaticamente
```

---

## 🎯 Benefícios

| Benefício | Descrição |
|-----------|-----------|
| **Evolução** | Sistema aprende e cria novos playbooks |
| **Velocidade** | Playbooks conhecidos são reutilizados (ms) |
| **Segurança** | Playbooks novos requerem aprovação humana |
| **Confiabilidade** | Estatísticas de sucesso guiam recomendações |
| **Auditoria** | Histórico completo de decisões e aprovações |
| **Escalabilidade** | Suporta crescimento ilimitado de playbooks |

---

## 🚀 Próximos Passos

1. **Integração com LLM Real:** Conectar com OpenAI, Anthropic, etc
2. **Feedback Loop:** Registrar execuções e atualizar estatísticas
3. **Dashboard de Curação:** Interface para SREs aprovarem/rejeitarem
4. **Análise de Tendências:** Detectar padrões emergentes
5. **Versionamento:** Manter histórico de versões de playbooks
6. **Otimização:** Treinar modelos locais para geração offline

---

## 📚 Referências

- **Neo4j Playbook Store:** `src/core/neo4j_playbook_store.py`
- **Playbook Generator:** `src/agents/governance/playbook_generator.py`
- **Recommender com Learning:** `src/agents/governance/recommender_with_learning.py`
- **Testes:** `tests/test_learning_engine.py`

---

## 🎉 Conclusão

O Motor de Aprendizado Autônomo transforma o Strands em um sistema verdadeiramente inteligente que:

- **Reutiliza** conhecimento (rápido)
- **Cria** novo conhecimento (criativo)
- **Aprende** com humanos (confiável)
- **Evolui** com o tempo (adaptável)

Isso é o futuro da remediação autônoma! 🚀
