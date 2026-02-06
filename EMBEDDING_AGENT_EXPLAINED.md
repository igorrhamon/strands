# 🧠 EmbeddingAgent - Busca Semântica de Alertas Similares

## 📚 Visão Geral

O **EmbeddingAgent** é responsável por buscar alertas similares no histórico usando **busca semântica com embeddings vetoriais**. Ele encontra decisões passadas que são semanticamente similares ao alerta atual, permitindo reutilizar resoluções conhecidas.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALERT ATUAL                                  │
│  "Payment API error rate exceeded 5%"                           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  EmbeddingAgent        │
        │  (Busca Semântica)     │
        └────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
   ┌─────────┐             ┌──────────┐
   │ Ollama  │             │ Qdrant   │
   │ Embed   │             │ Search   │
   └─────────┘             └──────────┘
        │                         │
        └────────────┬────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ 3 Alertas Similares    │
        │ com Resoluções         │
        └────────────────────────┘
```

---

## 🔄 Fluxo Completo - Passo a Passo

### **Passo 1: Entrada - Alerta Atual**

```python
# Alerta que chegou agora
alert = {
    "timestamp": "2026-02-06T12:00:00Z",
    "service": "payment-api",
    "severity": "critical",
    "description": "Error rate exceeded 5% (currently 7.2%)",
    "labels": {
        "alertname": "HighErrorRate",
        "instance": "payment-api:8000"
    }
}

# O EmbeddingAgent recebe a descrição
alert_description = "Error rate exceeded 5% (currently 7.2%)"
```

### **Passo 2: Geração de Embedding (Ollama)**

O texto do alerta é convertido em um **vetor numérico** usando o modelo Ollama:

```
┌──────────────────────────────────────────────────────────────┐
│ TEXTO: "Error rate exceeded 5% (currently 7.2%)"            │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Ollama (nomic-embed)   │
        │ POST /api/embed        │
        └────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ EMBEDDING (384 dimensões):                                   │
│ [0.234, -0.567, 0.891, -0.123, ..., 0.456]                 │
│                                                              │
│ Cada número representa um aspecto semântico do texto:       │
│ - Posição 1-50: Conceitos de "erro"                        │
│ - Posição 51-100: Conceitos de "taxa/percentual"           │
│ - Posição 101-150: Conceitos de "API"                      │
│ - Posição 151-384: Outros padrões semânticos               │
└──────────────────────────────────────────────────────────────┘
```

**Como funciona o embedding:**
```python
# Código real
response = await ollama.post(
    "http://localhost:11434/api/embed",
    json={
        "model": "nomic-embed-text:latest",
        "input": "Error rate exceeded 5% (currently 7.2%)"
    }
)

# Resposta
embedding_vector = response.json()["embeddings"][0]
# [0.234, -0.567, 0.891, -0.123, ..., 0.456]  # 384 números
```

### **Passo 3: Busca no Qdrant (Banco Vetorial)**

Agora o vetor é usado para buscar **vetores similares** no banco de dados Qdrant:

```
┌─────────────────────────────────────────────────────────────┐
│ QUERY VECTOR (do alerta atual):                             │
│ [0.234, -0.567, 0.891, -0.123, ..., 0.456]                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Qdrant (HNSW Index)    │
        │ Busca Vetorial         │
        └────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ HISTÓRICO NO QDRANT (Embeddings Armazenados):              │
│                                                             │
│ 1. [0.245, -0.580, 0.885, -0.120, ..., 0.460]            │
│    Similaridade: 0.98 ← MUITO SIMILAR!                    │
│    Texto: "Payment API error rate high (6.8%)"            │
│    Resolução: ESCALATE                                    │
│                                                             │
│ 2. [0.210, -0.550, 0.870, -0.150, ..., 0.440]            │
│    Similaridade: 0.92 ← SIMILAR                           │
│    Texto: "API error spike detected"                      │
│    Resolução: RESTART_SERVICE                             │
│                                                             │
│ 3. [0.190, -0.520, 0.850, -0.180, ..., 0.420]            │
│    Similaridade: 0.88 ← SIMILAR                           │
│    Texto: "High error rate on checkout"                   │
│    Resolução: ROLLBACK_DEPLOY                             │
│                                                             │
│ 4. [0.050, 0.200, 0.500, 0.800, ..., 0.100]              │
│    Similaridade: 0.45 ← NÃO SIMILAR                       │
│    (Descartado - abaixo do threshold 0.75)                │
└─────────────────────────────────────────────────────────────┘
```

**Como funciona a busca:**
```python
# Código real
results = qdrant.search(
    collection_name="alert_decisions",
    query_vector=[0.234, -0.567, 0.891, -0.123, ..., 0.456],
    limit=5,  # Top 5 resultados
    score_threshold=0.75  # Mínimo 75% de similaridade
)

# Resposta
results = [
    {
        "id": "vec-123",
        "score": 0.98,  # 98% similar
        "payload": {
            "source_decision_id": "dec-456",
            "source_text": "Payment API error rate high (6.8%)",
            "service": "payment-api",
            "severity": "critical",
            "rules_applied": ["HighErrorRate"],
            "decision_action": "ESCALATE"
        }
    },
    {
        "id": "vec-124",
        "score": 0.92,  # 92% similar
        "payload": {...}
    },
    {
        "id": "vec-125",
        "score": 0.88,  # 88% similar
        "payload": {...}
    }
]
```

### **Passo 4: Retorno dos Resultados**

Os 3 alertas similares são retornados com suas resoluções anteriores:

```python
# Saída do EmbeddingAgent
similarity_results = [
    SimilarityResult(
        decision_id=UUID("dec-456"),
        similarity_score=0.98,
        source_text="Payment API error rate high (6.8%)",
        service="payment-api",
        rules_applied=["HighErrorRate"],
        previous_action="ESCALATE"
    ),
    SimilarityResult(
        decision_id=UUID("dec-789"),
        similarity_score=0.92,
        source_text="API error spike detected",
        service="payment-api",
        rules_applied=["ErrorSpike"],
        previous_action="RESTART_SERVICE"
    ),
    SimilarityResult(
        decision_id=UUID("dec-999"),
        similarity_score=0.88,
        source_text="High error rate on checkout",
        service="checkout-service",
        rules_applied=["HighErrorRate"],
        previous_action="ROLLBACK_DEPLOY"
    )
]
```

---

## 🎯 Exemplo Prático Completo

### **Cenário: Novo Alerta de Erro no Payment API**

```
TEMPO: 2026-02-06 12:00:00

1. ALERTA CHEGA
   └─ Service: payment-api
   └─ Severity: critical
   └─ Description: "Error rate exceeded 5% (currently 7.2%)"

2. EMBEDDING AGENT INICIA
   └─ Texto: "Error rate exceeded 5% (currently 7.2%)"

3. OLLAMA GERA EMBEDDING
   └─ Modelo: nomic-embed-text:latest
   └─ Entrada: "Error rate exceeded 5% (currently 7.2%)"
   └─ Saída: [0.234, -0.567, 0.891, ..., 0.456]  (384 dims)

4. QDRANT BUSCA SIMILARES
   └─ Query Vector: [0.234, -0.567, 0.891, ..., 0.456]
   └─ Collection: alert_decisions
   └─ Top K: 5
   └─ Score Threshold: 0.75

5. RESULTADOS ENCONTRADOS
   
   ✓ Resultado 1 (Similaridade: 0.98)
   ├─ Texto Histórico: "Payment API error rate high (6.8%)"
   ├─ Data: 2026-02-05 14:30:00 (ontem)
   ├─ Resolução: ESCALATE
   ├─ Confiança: 0.95
   └─ Regras: ["HighErrorRate"]
   
   ✓ Resultado 2 (Similaridade: 0.92)
   ├─ Texto Histórico: "API error spike detected"
   ├─ Data: 2026-02-04 10:15:00 (2 dias atrás)
   ├─ Resolução: RESTART_SERVICE
   ├─ Confiança: 0.87
   └─ Regras: ["ErrorSpike"]
   
   ✓ Resultado 3 (Similaridade: 0.88)
   ├─ Texto Histórico: "High error rate on checkout"
   ├─ Data: 2026-02-03 16:45:00 (3 dias atrás)
   ├─ Resolução: ROLLBACK_DEPLOY
   ├─ Confiança: 0.82
   └─ Regras: ["HighErrorRate"]

6. DECISION ENGINE UTILIZA RESULTADOS
   └─ "Encontrei 3 alertas similares!"
   └─ "O mais similar (98%) foi resolvido com ESCALATE"
   └─ "Vou usar a mesma resolução"
   └─ Decision: ESCALATE (confiança: 0.98)
```

---

## 🔐 Ciclo de Vida dos Embeddings

### **Fase 1: Coleta (Histórico)**

```
Alertas Históricos
        │
        ▼
┌──────────────────────┐
│ AlertCollector       │
│ (coleta alertas)     │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ AlertNormalizer      │
│ (padroniza)          │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ DecisionEngine       │
│ (toma decisão)       │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ HumanReview          │
│ (aprova decisão)     │
└──────────────────────┘
```

### **Fase 2: Persistência (Após Aprovação)**

```
Decision APPROVED
        │
        ▼
┌──────────────────────────────┐
│ EmbeddingAgent               │
│ persist_confirmed_decision() │
│ (APENAS após confirmação!)   │
└──────────────────────────────┘
        │
        ├─ Gera embedding via Ollama
        │
        ├─ Cria VectorEmbedding
        │
        └─ Armazena em Qdrant
                │
                ▼
        ┌──────────────────┐
        │ Qdrant Collection│
        │ alert_decisions  │
        └──────────────────┘
```

### **Fase 3: Busca (Novo Alerta)**

```
Novo Alerta
        │
        ▼
┌──────────────────────────┐
│ EmbeddingAgent           │
│ search_similar()         │
│ (busca histórico)        │
└──────────────────────────┘
        │
        ├─ Gera embedding via Ollama
        │
        ├─ Busca em Qdrant
        │
        └─ Retorna Top 3 similares
                │
                ▼
        ┌──────────────────┐
        │ DecisionEngine   │
        │ (reutiliza       │
        │  resoluções)     │
        └──────────────────┘
```

---

## 📊 Dados Armazenados no Qdrant

### **Estrutura de um Ponto (Point) no Qdrant**

```python
{
    "id": "vec-123",  # UUID único
    "vector": [0.234, -0.567, 0.891, ..., 0.456],  # 384 dimensões
    "payload": {
        # Referência à decisão original
        "source_decision_id": "dec-456",
        
        # Texto que foi embarcado
        "source_text": "Payment API error rate high (6.8%)",
        
        # Contexto
        "service": "payment-api",
        "severity": "critical",
        
        # Regras que dispararam
        "rules_applied": ["HighErrorRate", "CriticalSeverity"],
        
        # Quem confirmou
        "human_validator": "analyst-john",
        
        # Quando foi criado
        "created_at": "2026-02-05T14:30:00Z"
    }
}
```

### **Exemplo: 3 Pontos no Histórico**

```json
[
  {
    "id": "vec-001",
    "vector": [0.245, -0.580, 0.885, -0.120, ..., 0.460],
    "payload": {
      "source_decision_id": "dec-001",
      "source_text": "Payment API error rate high (6.8%)",
      "service": "payment-api",
      "severity": "critical",
      "rules_applied": ["HighErrorRate"],
      "human_validator": "analyst-john",
      "created_at": "2026-02-05T14:30:00Z"
    }
  },
  {
    "id": "vec-002",
    "vector": [0.210, -0.550, 0.870, -0.150, ..., 0.440],
    "payload": {
      "source_decision_id": "dec-002",
      "source_text": "API error spike detected",
      "service": "payment-api",
      "severity": "critical",
      "rules_applied": ["ErrorSpike"],
      "human_validator": "analyst-jane",
      "created_at": "2026-02-04T10:15:00Z"
    }
  },
  {
    "id": "vec-003",
    "vector": [0.190, -0.520, 0.850, -0.180, ..., 0.420],
    "payload": {
      "source_decision_id": "dec-003",
      "source_text": "High error rate on checkout",
      "service": "checkout-service",
      "severity": "critical",
      "rules_applied": ["HighErrorRate"],
      "human_validator": "analyst-bob",
      "created_at": "2026-02-03T16:45:00Z"
    }
  }
]
```

---

## 🔍 Como a Similaridade é Calculada

### **Distância Cosseno (Cosine Similarity)**

```
Query Vector:    [0.234, -0.567, 0.891, -0.123, ..., 0.456]
Stored Vector:   [0.245, -0.580, 0.885, -0.120, ..., 0.460]

Similaridade = Produto Escalar / (Norma1 × Norma2)

Resultado: 0.98 (98% similar)
```

**Interpretação:**
- **0.98 (98%)**: Quase idêntico - use a mesma resolução
- **0.92 (92%)**: Muito similar - considere a mesma resolução
- **0.88 (88%)**: Similar - pode ser útil como referência
- **0.75 (75%)**: Minimamente similar - considere com cuidado
- **< 0.75**: Não similar - descarte

### **Visualização**

```
Espaço Vetorial 384-dimensional:

Query Vector (novo alerta)
        •
        │ Distância: 0.02 (98% similar)
        │
        • Stored Vector 1 ✓ MUITO SIMILAR
        │
        │ Distância: 0.08 (92% similar)
        │
        • Stored Vector 2 ✓ SIMILAR
        │
        │ Distância: 0.12 (88% similar)
        │
        • Stored Vector 3 ✓ SIMILAR
        │
        │ Distância: 0.25 (45% similar)
        │
        • Stored Vector 4 ✗ NÃO SIMILAR
```

---

## 💾 Constituição Princípio III

> **"Apenas decisões CONFIRMADAS são armazenadas como embeddings"**

```python
# ✓ CORRETO - Decisão confirmada
decision = Decision(
    action="ESCALATE",
    confidence=0.95,
    is_confirmed=True  # ← Confirmada
)

embedding = embedding_agent.persist_confirmed_decision(decision)
# ✓ Embedding armazenado com sucesso

# ✗ INCORRETO - Decisão não confirmada
decision = Decision(
    action="RESTART_SERVICE",
    confidence=0.65,
    is_confirmed=False  # ← Não confirmada
)

embedding = embedding_agent.persist_confirmed_decision(decision)
# ✗ Erro: "Cannot persist embedding for unconfirmed decision"
```

---

## 📈 Métricas e Monitoramento

### **Prometheus Metrics**

```
# Número de embeddings armazenados
strands_embedding_count = 1234

# Latência de busca
strands_embedding_search_seconds = 0.234

# Taxa de sucesso
strands_embedding_search_success_rate = 0.98

# Distribuição de scores
strands_embedding_similarity_score_histogram = [0.75, 0.82, 0.88, 0.92, 0.98]
```

### **Jaeger Traces**

```
Trace: embedding_search_abc123
├─ Ollama.embed (123ms)
│  └─ POST /api/embed
│  └─ Input: "Error rate exceeded 5%"
│  └─ Output: 384-dim vector
│
├─ Qdrant.search (89ms)
│  └─ Query vector
│  └─ Top K: 5
│  └─ Score threshold: 0.75
│
└─ Total: 212ms
```

---

## 🚀 Fluxo Resumido

```
1. Novo Alerta Chega
   └─ "Error rate exceeded 5% (currently 7.2%)"

2. EmbeddingAgent.search_similar()
   └─ Texto → Ollama → Embedding Vector

3. Qdrant.search()
   └─ Vector → Busca Vetorial → Top 3 Similares

4. Resultados Retornados
   ├─ 98% similar: "ESCALATE"
   ├─ 92% similar: "RESTART_SERVICE"
   └─ 88% similar: "ROLLBACK_DEPLOY"

5. DecisionEngine Utiliza
   └─ "Vou usar ESCALATE (98% de confiança)"

6. Decisão Final
   └─ Action: ESCALATE
   └─ Confidence: 0.98
```

---

## 📚 Referências

- **Ollama**: http://localhost:11434
- **Qdrant**: http://localhost:6333
- **Código**: `src/agents/embedding_agent.py`
- **Vector Store**: `src/tools/vector_store.py`
- **Modelos**: `src/models/embedding.py`
