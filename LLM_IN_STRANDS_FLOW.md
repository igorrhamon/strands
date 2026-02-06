# 🤖 Onde a LLM (Ollama) Entra no Fluxo do Strands

## 📚 Visão Geral

A LLM (Ollama) entra em **3 pontos críticos** do pipeline do Strands:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE STRANDS                             │
│                                                                 │
│  1. AlertCollector → 2. Normalizer → 3. Correlator → ...       │
│                                                                 │
│     ┌──────────────────────────────────────────────────────┐   │
│     │                                                      │   │
│     │  🤖 LLM ENTRA EM 3 PONTOS:                          │   │
│     │                                                      │   │
│     │  1️⃣ EMBEDDING AGENT (Geração de Vetores)           │   │
│     │     └─ Converte texto em vetor semântico            │   │
│     │     └─ Modelo: nomic-embed-text                     │   │
│     │                                                      │   │
│     │  2️⃣ DECISION ENGINE (Análise de Contexto)          │   │
│     │     └─ Analisa contexto e gera recomendações       │   │
│     │     └─ Modelo: mistral, llama2, etc                │   │
│     │                                                      │   │
│     │  3️⃣ REPORT AGENT (Geração de Relatórios)           │   │
│     │     └─ Gera explicações legíveis para humanos       │   │
│     │     └─ Modelo: mistral, llama2, etc                │   │
│     │                                                      │   │
│     └──────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ LLM no EMBEDDING AGENT

### **Função: Geração de Embeddings (Vetores Semânticos)**

```python
# Modelo: nomic-embed-text (384 dimensões)
# Função: Converter texto em vetor numérico

class EmbeddingAgent:
    async def search_similar(self, alert_description: str):
        """
        Usa LLM para gerar embedding do alerta
        """
        
        # ENTRADA: Texto do alerta
        alert_text = """
        Database connection timeout causing checkout failures.
        500 customers affected, revenue loss $5k/min.
        """
        
        # 🤖 LLM AQUI: Ollama gera embedding
        embedding_vector = await ollama.embed(
            model="nomic-embed-text:latest",
            input=alert_text
        )
        # SAÍDA: [0.156, -0.432, 0.789, ..., 0.234]  (384 números)
        
        # Usa vetor para buscar similares no Qdrant
        similar_results = await qdrant.search(
            vector=embedding_vector,
            top_k=5
        )
        
        return similar_results
```

### **Fluxo Detalhado**

```
┌─────────────────────────────────────────────────────────────┐
│ EMBEDDING AGENT                                             │
└─────────────────────────────────────────────────────────────┘

Entrada:
├─ Alert Text: "Database connection timeout..."
└─ Service: "payment-api"

        ↓

🤖 LLM (Ollama - nomic-embed-text)
├─ POST http://localhost:11434/api/embed
├─ Input: "Database connection timeout..."
└─ Output: [0.156, -0.432, 0.789, ..., 0.234]

        ↓

Qdrant Search:
├─ Vector: [0.156, -0.432, 0.789, ..., 0.234]
├─ Top K: 5
└─ Results: 3 similar incidents

        ↓

Saída:
├─ SimilarityResult 1: 0.96 similarity
├─ SimilarityResult 2: 0.88 similarity
└─ SimilarityResult 3: 0.82 similarity
```

### **Quando é Usado**

- ✅ Quando um novo alerta chega
- ✅ Para buscar incidentes similares no histórico
- ✅ Para encontrar resoluções anteriores

### **Modelo Usado**

```
Modelo: nomic-embed-text:latest
Dimensões: 384
Velocidade: ~100ms por embedding
Uso: Busca semântica
```

---

## 2️⃣ LLM no DECISION ENGINE

### **Função: Análise de Contexto e Recomendação**

```python
# Modelo: mistral, llama2, neural-chat, etc
# Função: Analisar contexto e gerar recomendação

class DecisionEngine:
    async def make_decision(
        self,
        cluster: AlertCluster,
        metrics: MetricsAnalysisResult,
        graph: GraphContext,
        similar: SimilarityResult
    ) -> Decision:
        """
        Usa LLM para analisar contexto e gerar decisão
        """
        
        # Constrói prompt com todo o contexto
        prompt = f"""
        Você é um especialista em resolução de incidentes de infraestrutura.
        
        ALERTA ATUAL:
        - Serviço: {cluster.service}
        - Severidade: {cluster.severity}
        - Descrição: {cluster.description}
        
        ANÁLISE DE MÉTRICAS:
        - Tendência: {metrics.trend}
        - Anomalias: {metrics.anomalies}
        - Confiança: {metrics.confidence}
        
        CONTEXTO DE DEPENDÊNCIAS:
        - Serviços dependentes: {graph.dependent_services}
        - Histórico de falhas: {graph.failure_history}
        
        INCIDENTES SIMILARES ENCONTRADOS:
        - Mais similar (96%): {similar[0].source_text}
          Resolução anterior: {similar[0].previous_action}
          Tempo: {similar[0].resolution_time}
        
        Com base em toda essa análise, qual é a melhor ação a tomar?
        Justifique sua recomendação.
        """
        
        # 🤖 LLM AQUI: Ollama analisa contexto
        response = await ollama.generate(
            model="mistral:latest",
            prompt=prompt,
            stream=False
        )
        
        # SAÍDA: Recomendação da LLM
        llm_recommendation = response.response
        
        # Exemplo de resposta:
        # "Com base na análise, recomendo INCREASE_POOL_SIZE
        #  porque:
        #  1. 96% similar ao incidente INC0112345
        #  2. Métrica mostra pool exhausted
        #  3. Resolução anterior funcionou em 15 min
        #  Confiança: 95%"
        
        # Converte resposta em Decision
        decision = Decision(
            action=parse_action(llm_recommendation),
            confidence=parse_confidence(llm_recommendation),
            reasoning=llm_recommendation,
            evidence={
                "metrics": metrics,
                "graph": graph,
                "similar": similar
            }
        )
        
        return decision
```

### **Fluxo Detalhado**

```
┌─────────────────────────────────────────────────────────────┐
│ DECISION ENGINE                                             │
└─────────────────────────────────────────────────────────────┘

Entrada:
├─ Alert Cluster: {service, severity, description}
├─ Metrics: {trend, anomalies, confidence}
├─ Graph Context: {dependent_services, failure_history}
└─ Similar Incidents: {3 incidentes similares}

        ↓

🤖 LLM (Ollama - mistral)
├─ POST http://localhost:11434/api/generate
├─ Prompt: "Você é especialista em incidentes..."
│          "Alerta: Database connection timeout..."
│          "Métricas: Trend=UP, Pool=Exhausted..."
│          "Similar (96%): INCREASE_POOL_SIZE..."
└─ Output: "Recomendo INCREASE_POOL_SIZE porque..."

        ↓

Parsing:
├─ Action: INCREASE_POOL_SIZE
├─ Confidence: 0.95
└─ Reasoning: "96% similar ao INC0112345..."

        ↓

Saída:
└─ Decision {
     action: "INCREASE_POOL_SIZE",
     confidence: 0.95,
     reasoning: "..."
   }
```

### **Quando é Usado**

- ✅ Quando precisa analisar contexto complexo
- ✅ Para gerar recomendações baseadas em múltiplas fontes
- ✅ Para justificar decisões para humanos
- ✅ Quando confiança de regras é baixa (< 0.7)

### **Modelos Disponíveis**

```
mistral:latest       - Bom balanço velocidade/qualidade
llama2:latest        - Mais preciso, mais lento
neural-chat:latest   - Otimizado para chat
dolphin-mixtral      - Muito bom para análise
```

---

## 3️⃣ LLM no REPORT AGENT

### **Função: Geração de Relatórios Legíveis**

```python
# Modelo: mistral, llama2, etc
# Função: Gerar explicações em linguagem natural

class ReportAgent:
    async def generate_report(
        self,
        decision: Decision,
        cluster: AlertCluster,
        metrics: MetricsAnalysisResult,
        similar: SimilarityResult
    ) -> str:
        """
        Usa LLM para gerar relatório legível para humanos
        """
        
        prompt = f"""
        Gere um relatório executivo sobre este incidente para um analista.
        
        INCIDENTE:
        - Serviço: {cluster.service}
        - Severidade: {cluster.severity}
        - Descrição: {cluster.description}
        
        ANÁLISE:
        - Causa provável: {metrics.root_cause}
        - Impacto: {metrics.impact}
        - Duração estimada: {metrics.estimated_duration}
        
        DECISÃO RECOMENDADA:
        - Ação: {decision.action}
        - Confiança: {decision.confidence}
        - Justificativa: {decision.reasoning}
        
        HISTÓRICO SIMILAR:
        - Incidente anterior: {similar[0].source_text}
        - Resolução: {similar[0].previous_action}
        - Tempo para resolver: {similar[0].resolution_time}
        
        Gere um relatório profissional em português que:
        1. Resuma o problema
        2. Explique a causa
        3. Recomende a ação
        4. Cite o histórico similar
        5. Indique próximos passos
        """
        
        # 🤖 LLM AQUI: Ollama gera relatório
        response = await ollama.generate(
            model="mistral:latest",
            prompt=prompt,
            stream=False
        )
        
        # SAÍDA: Relatório legível
        report = response.response
        
        # Exemplo de saída:
        # """
        # RELATÓRIO DE INCIDENTE - INC0123456
        #
        # RESUMO:
        # O serviço payment-api está indisponível devido a esgotamento
        # do pool de conexões do banco de dados.
        #
        # CAUSA:
        # O tamanho do pool foi reduzido de 100 para 50 conexões durante
        # manutenção, e não foi restaurado. Além disso, novas regras de
        # validação de pagamento aumentaram o tempo de conexão.
        #
        # AÇÃO RECOMENDADA:
        # Aumentar o pool de conexões de 50 para 100 e fazer rollback
        # das regras de validação.
        #
        # HISTÓRICO SIMILAR:
        # Este problema é 96% similar ao incidente INC0112345 de 1 semana
        # atrás, que foi resolvido em 15 minutos com a mesma ação.
        #
        # PRÓXIMOS PASSOS:
        # 1. Executar ação recomendada
        # 2. Monitorar taxa de sucesso de checkout
        # 3. Validar métricas de banco de dados
        # 4. Fazer rollback completo das mudanças
        # """
        
        return report
```

### **Fluxo Detalhado**

```
┌─────────────────────────────────────────────────────────────┐
│ REPORT AGENT                                                │
└─────────────────────────────────────────────────────────────┘

Entrada:
├─ Decision: {action, confidence, reasoning}
├─ Cluster: {service, severity, description}
├─ Metrics: {root_cause, impact, duration}
└─ Similar: {3 incidentes similares}

        ↓

🤖 LLM (Ollama - mistral)
├─ POST http://localhost:11434/api/generate
├─ Prompt: "Gere um relatório executivo..."
│          "Serviço: payment-api..."
│          "Ação: INCREASE_POOL_SIZE..."
└─ Output: "RELATÓRIO DE INCIDENTE..."

        ↓

Formatação:
├─ Resumo
├─ Causa
├─ Ação Recomendada
├─ Histórico Similar
└─ Próximos Passos

        ↓

Saída:
└─ Relatório em Markdown/HTML
```

### **Quando é Usado**

- ✅ Para notificar analistas humanos
- ✅ Para criar tickets no ServiceNow
- ✅ Para enviar alertas por email/Slack
- ✅ Para documentar incidentes
- ✅ Para treinamento e aprendizado

### **Saída Exemplo**

```markdown
# RELATÓRIO DE INCIDENTE - INC0123456

## RESUMO
O serviço payment-api está indisponível devido a esgotamento do pool 
de conexões do banco de dados.

## CAUSA
O tamanho do pool foi reduzido de 100 para 50 conexões durante 
manutenção, e não foi restaurado. Além disso, novas regras de 
validação aumentaram o tempo de conexão.

## AÇÃO RECOMENDADA
Aumentar pool de 50 para 100 e fazer rollback das validações.

## HISTÓRICO SIMILAR
96% similar ao INC0112345 (resolvido em 15 minutos)

## PRÓXIMOS PASSOS
1. Executar ação recomendada
2. Monitorar taxa de sucesso
3. Validar métricas de DB
```

---

## 🔄 Fluxo Completo com LLM

```
┌──────────────────────────────────────────────────────────────┐
│ 1. ALERTA CHEGA                                              │
│    └─ "Database connection timeout"                          │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│ 2. ALERT COLLECTOR                                           │
│    └─ Coleta de Prometheus/Grafana/ServiceNow               │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│ 3. ALERT NORMALIZER                                          │
│    └─ Valida e padroniza                                    │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│ 4. ALERT CORRELATOR                                          │
│    └─ Agrupa alertas relacionados                           │
└────────────────┬─────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐   ┌──────────────────┐
│ METRICS      │   │ GRAPH AGENT      │
│ ANALYSIS     │   │ (Neo4j)          │
└──────────────┘   └──────────────────┘
        │                 │
        └────────┬────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ 🤖 EMBEDDING AGENT         │
    │ (LLM - nomic-embed-text)   │
    │                            │
    │ 1. Gera embedding do alerta│
    │ 2. Busca similares em      │
    │    Qdrant                  │
    │ 3. Retorna 3 similares     │
    └────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ 🤖 DECISION ENGINE         │
    │ (LLM - mistral/llama2)     │
    │                            │
    │ 1. Analisa contexto        │
    │ 2. Consulta histórico      │
    │ 3. Gera recomendação       │
    │ 4. Retorna Decision        │
    └────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ HUMAN REVIEW               │
    │ (se confiança < 70%)       │
    └────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ 🤖 REPORT AGENT            │
    │ (LLM - mistral/llama2)     │
    │                            │
    │ 1. Gera relatório          │
    │ 2. Cria notificação        │
    │ 3. Atualiza ServiceNow     │
    │ 4. Envia email/Slack       │
    └────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ SAÍDA                      │
    │ - Ticket criado            │
    │ - Notificação enviada      │
    │ - Ação executada           │
    │ - Relatório gerado         │
    └────────────────────────────┘
```

---

## 📊 Resumo: Onde LLM Entra

| Ponto | Agente | Modelo | Função | Entrada | Saída |
|-------|--------|--------|--------|---------|-------|
| **1️⃣** | EmbeddingAgent | nomic-embed-text | Gera embedding | Texto do alerta | Vetor 384-dim |
| **2️⃣** | DecisionEngine | mistral/llama2 | Analisa contexto | Contexto completo | Recomendação |
| **3️⃣** | ReportAgent | mistral/llama2 | Gera relatório | Decision + contexto | Relatório legível |

---

## 🎯 Exemplo Prático Completo

### **Cenário: Novo Alerta de Timeout**

```
TEMPO: 12:00:00

1. ALERTA CHEGA
   └─ "Database connection timeout"

2. EMBEDDING AGENT
   ├─ 🤖 Ollama (nomic-embed-text)
   ├─ Input: "Database connection timeout..."
   ├─ Output: [0.156, -0.432, 0.789, ..., 0.234]
   ├─ Qdrant Search: Top 3 similares
   └─ Retorna: 3 incidentes similares (96%, 88%, 82%)

3. DECISION ENGINE
   ├─ 🤖 Ollama (mistral)
   ├─ Input: "Você é especialista em incidentes..."
   │         "Alerta: Database timeout..."
   │         "Similar (96%): INCREASE_POOL_SIZE..."
   ├─ Output: "Recomendo INCREASE_POOL_SIZE porque..."
   └─ Retorna: Decision(action=INCREASE_POOL_SIZE, confidence=0.95)

4. HUMAN REVIEW
   ├─ Confiança: 0.95 (> 0.7)
   └─ Status: APROVADO (sem revisão)

5. REPORT AGENT
   ├─ 🤖 Ollama (mistral)
   ├─ Input: "Gere um relatório executivo..."
   │         "Serviço: payment-api..."
   │         "Ação: INCREASE_POOL_SIZE..."
   ├─ Output: "RELATÓRIO DE INCIDENTE..."
   └─ Retorna: Relatório em Markdown

6. SAÍDA
   ├─ Ticket criado no ServiceNow
   ├─ Email enviado para analista
   ├─ Slack notificado
   ├─ Ação executada
   └─ Relatório documentado

TEMPO TOTAL: ~2 segundos
```

---

## 🔐 Configuração do Ollama

### **.env**

```bash
# Ollama
OLLAMA_URL=http://localhost:11434

# Modelos
OLLAMA_EMBEDDING_MODEL=nomic-embed-text:latest
OLLAMA_DECISION_MODEL=mistral:latest
OLLAMA_REPORT_MODEL=mistral:latest

# Timeouts
OLLAMA_EMBEDDING_TIMEOUT=30s
OLLAMA_DECISION_TIMEOUT=60s
OLLAMA_REPORT_TIMEOUT=60s
```

### **docker-compose.yml**

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    environment:
      - OLLAMA_NUM_PARALLEL=4
      - OLLAMA_NUM_THREAD=8
    volumes:
      - ollama-data:/root/.ollama
    command: serve

volumes:
  ollama-data:
```

### **Inicializar Modelos**

```bash
# Pull modelos
ollama pull nomic-embed-text:latest
ollama pull mistral:latest
ollama pull llama2:latest

# Verificar
curl http://localhost:11434/api/tags
```

---

## 📈 Métricas de LLM

### **Prometheus Metrics**

```
# Latência de embedding
strands_llm_embedding_seconds = 0.123

# Latência de decisão
strands_llm_decision_seconds = 2.456

# Taxa de sucesso
strands_llm_success_rate = 0.98

# Tokens processados
strands_llm_tokens_processed = 12345

# Custo (se usar API externa)
strands_llm_cost_usd = 0.45
```

### **Jaeger Traces**

```
Trace: decision_generation_abc123
├─ EmbeddingAgent
│  ├─ Ollama.embed (123ms)
│  └─ Qdrant.search (89ms)
├─ DecisionEngine
│  ├─ Ollama.generate (2456ms)
│  └─ Parse response (12ms)
├─ ReportAgent
│  ├─ Ollama.generate (1234ms)
│  └─ Format markdown (8ms)
└─ Total: 3.9s
```

---

## 🚀 Resumo

**A LLM (Ollama) entra em 3 pontos críticos:**

1. **🤖 EMBEDDING AGENT** (nomic-embed-text)
   - Converte texto em vetor semântico
   - Busca incidentes similares no Qdrant
   - ~100ms por embedding

2. **🤖 DECISION ENGINE** (mistral/llama2)
   - Analisa contexto complexo
   - Gera recomendações baseadas em histórico
   - ~2-3 segundos por decisão

3. **🤖 REPORT AGENT** (mistral/llama2)
   - Gera relatórios legíveis para humanos
   - Cria notificações e tickets
   - ~1-2 segundos por relatório

**Total: ~4-5 segundos do alerta à decisão final**

A LLM não substitui as regras determinísticas, mas as **complementa** com análise semântica e contexto!
