# 📊 Fluxo de Dados no Strands - Arquitetura Completa

## 🎯 Visão Geral

O Strands é um **sistema de orquestração de agentes** que processa alertas através de um pipeline determinístico. Os dados entram via Prometheus/Grafana e saem como decisões acionáveis.

```
┌─────────────────────────────────────────────────────────────────┐
│                    FONTES DE DADOS EXTERNAS                     │
│  Prometheus │ Grafana │ ServiceNow │ Elasticsearch │ Datadog    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE STRANDS                             │
│  1. AlertCollector → 2. Normalizer → 3. Correlator → ...        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SAÍDAS / DECISÕES                            │
│  Tickets │ Escalações │ Remediação │ Relatórios │ Audit Logs    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ ENTRADA DE DADOS - Como Alertas Chegam

### 1.1 Fontes Suportadas

#### **Prometheus** (Primária)
```python
# Endpoint: http://localhost:9090/api/v1/alerts
# Retorna alertas disparados em tempo real

{
  "status": "success",
  "data": {
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "HighErrorRate",
          "severity": "critical",
          "service": "payment-api"
        },
        "annotations": {
          "summary": "Error rate > 5%",
          "description": "Payment API error rate is 7.2%"
        },
        "startsAt": "2026-02-06T12:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z"
      }
    ]
  }
}
```

#### **Grafana** (Fallback)
```python
# Endpoint: /api/v1/rules (via Grafana MCP)
# Retorna alertas em formato Grafana

{
  "id": "alert-123",
  "uid": "abc123",
  "title": "High CPU Usage",
  "condition": "A > 80",
  "data": [...],
  "noDataState": "NoData",
  "execErrState": "Alerting",
  "for": "5m",
  "annotations": {
    "description": "CPU usage is above 80%"
  },
  "labels": {
    "severity": "warning"
  }
}
```

#### **ServiceNow** (Integração Futura)
```python
# Via MCP ServiceNow connector
{
  "number": "INC0123456",
  "short_description": "Database connection timeout",
  "severity": "2",
  "state": "1"
}
```

### 1.2 Modelo de Dados de Entrada (Alert)

```python
class Alert(BaseModel):
    """Raw alert from external system"""
    
    timestamp: datetime           # Quando o alerta foi gerado
    fingerprint: str              # ID único (hash Prometheus ou ticket ID)
    service: str                  # Nome do serviço afetado
    severity: str                 # critical, warning, info
    description: str              # Descrição em texto livre
    source: AlertSource           # GRAFANA, SERVICENOW, PROMETHEUS
    labels: dict[str, str]        # Metadados key-value
    annotations: dict[str, str]   # Anotações adicionais
    status: str                   # firing, ok, resolved
```

---

## 2️⃣ PROCESSAMENTO - Pipeline de Agentes

### 2.1 Arquitetura do Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                   ALERT ORCHESTRATOR                            │
│  (Coordena execução determinística dos agentes)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌─────────┐     ┌──────────┐     ┌──────────┐
   │Collector│────▶│Normalizer│────▶│Correlator│
   └─────────┘     └──────────┘     └──────────┘
        │                │                │
        │ Raw Alerts     │ Normalized     │ Clusters
        │                │ Alerts         │
        └────────────────┼────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌──────────┐    ┌────────────┐   ┌──────────┐
   │Metrics   │    │Graph Agent │   │Embedding │
   │Analysis  │    │(Neo4j)     │   │(Qdrant)  │
   └──────────┘    └────────────┘   └──────────┘
        │                │                │
        │ Trends         │ Context        │ Similarity
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │Decision      │
                  │Engine        │
                  │(LLM + Rules) │
                  └──────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │Human Review  │
                  │(se necessário)│
                  └──────────────┘
```

### 2.2 Agentes e Suas Responsabilidades

#### **1. AlertCollectorAgent**
```python
# Input: None (queries external systems)
# Output: List[Alert]

def collect_active_alerts() -> List[Alert]:
    """
    Coleta alertas ativos de:
    1. Prometheus (primário)
    2. Grafana (fallback)
    3. ServiceNow (integração)
    """
    # Tenta Prometheus primeiro
    if prometheus_available:
        return fetch_from_prometheus()
    
    # Fallback para Grafana
    return fetch_from_grafana()
```

**Fluxo:**
```
Prometheus API → Parsing → Alert objects → Normalizer
```

#### **2. AlertNormalizerAgent**
```python
# Input: List[Alert]
# Output: List[NormalizedAlert]

def normalize(alerts: List[Alert]) -> List[NormalizedAlert]:
    """
    Padroniza alertas de diferentes fontes:
    - Valida campos obrigatórios
    - Normaliza severidade (critical, warning, info)
    - Extrai service name
    - Limpa descrição
    """
    normalized = []
    for alert in alerts:
        # Valida
        if not alert.service or not alert.severity:
            continue
        
        # Normaliza
        norm_alert = NormalizedAlert(
            service=alert.service.lower(),
            severity=normalize_severity(alert.severity),
            description=clean_text(alert.description)
        )
        normalized.append(norm_alert)
    
    return normalized
```

**Fluxo:**
```
Raw Alerts → Validation → Normalization → Normalized Alerts
```

#### **3. AlertCorrelationAgent**
```python
# Input: List[NormalizedAlert]
# Output: List[AlertCluster]

def correlate(alerts: List[NormalizedAlert]) -> List[AlertCluster]:
    """
    Agrupa alertas relacionados:
    - Mesma origem (service)
    - Janela de tempo similar
    - Padrões de erro comuns
    """
    clusters = {}
    
    for alert in alerts:
        # Agrupa por service
        key = alert.service
        
        if key not in clusters:
            clusters[key] = AlertCluster(
                cluster_id=uuid4(),
                service=key,
                alerts=[alert]
            )
        else:
            clusters[key].alerts.append(alert)
    
    return list(clusters.values())
```

**Fluxo:**
```
Normalized Alerts → Grouping → Correlation → Alert Clusters
```

#### **4. MetricsAnalysisAgent**
```python
# Input: AlertCluster
# Output: MetricsAnalysisResult

async def analyze(cluster: AlertCluster) -> MetricsAnalysisResult:
    """
    Analisa métricas históricas:
    - Tendências (trending up/down)
    - Anomalias (desvio padrão)
    - Correlações com outras métricas
    """
    # Query Prometheus para histórico
    metrics = await prometheus.query_range(
        query=f'rate({cluster.service}_errors_total[5m])',
        start=now - 1h,
        end=now
    )
    
    # Analisa tendência
    trend = analyze_trend(metrics)
    
    # Detecta anomalias
    anomalies = detect_anomalies(metrics)
    
    return MetricsAnalysisResult(
        trend=trend,
        anomalies=anomalies,
        confidence=0.95
    )
```

**Fluxo:**
```
Alert Cluster → Prometheus Query → Trend Analysis → Metrics Result
```

#### **5. GraphAgent** (Neo4j)
```python
# Input: AlertCluster
# Output: GraphContext

def analyze_graph(cluster: AlertCluster) -> GraphContext:
    """
    Busca contexto de dependências:
    - Serviços dependentes
    - Histórico de falhas
    - Relacionamentos conhecidos
    """
    # Query Neo4j
    query = """
    MATCH (service:Service {name: $service})
    -[:DEPENDS_ON]->(dep:Service)
    -[:HAS_FAILURE]->(failure:Failure)
    WHERE failure.timestamp > $cutoff
    RETURN dep, failure
    """
    
    results = neo4j.run(query, service=cluster.service)
    
    return GraphContext(
        dependent_services=results,
        failure_history=results
    )
```

**Fluxo:**
```
Alert Cluster → Neo4j Query → Dependency Graph → Graph Context
```

#### **6. EmbeddingAgent** (Qdrant)
```python
# Input: AlertCluster
# Output: SimilarityResult

async def find_similar(cluster: AlertCluster) -> SimilarityResult:
    """
    Busca alertas similares no histórico:
    - Embeddings semânticos (Ollama)
    - Busca vetorial (Qdrant)
    - Resoluções anteriores
    """
    # Gera embedding da descrição
    embedding = await ollama.embed(cluster.description)
    
    # Busca similares no Qdrant
    similar = await qdrant.search(
        collection="alert_decisions",
        vector=embedding,
        limit=5
    )
    
    return SimilarityResult(
        similar_alerts=similar,
        confidence=0.87
    )
```

**Fluxo:**
```
Alert Description → Ollama Embedding → Qdrant Search → Similar Alerts
```

#### **7. DecisionEngine**
```python
# Input: AlertCluster + Analysis Results
# Output: Decision

def make_decision(
    cluster: AlertCluster,
    metrics: MetricsAnalysisResult,
    graph: GraphContext,
    similar: SimilarityResult
) -> Decision:
    """
    Combina análises para tomar decisão:
    - Regras determinísticas
    - LLM (Ollama) para contexto
    - Confiança baseada em evidências
    """
    
    # Regras determinísticas
    if metrics.trend == "CRITICAL_UP":
        return Decision(
            action="ESCALATE",
            severity="CRITICAL",
            confidence=0.99
        )
    
    # Se similar encontrado, usa resolução anterior
    if similar.confidence > 0.9:
        return Decision(
            action=similar.previous_action,
            confidence=similar.confidence
        )
    
    # Consulta LLM para contexto
    llm_analysis = await ollama.analyze(
        alert=cluster,
        context=graph
    )
    
    return Decision(
        action=llm_analysis.recommended_action,
        confidence=llm_analysis.confidence,
        reasoning=llm_analysis.reasoning
    )
```

**Fluxo:**
```
All Analyses → Rules Engine → LLM Consultation → Decision
```

#### **8. HumanReviewAgent**
```python
# Input: Decision (se confidence < threshold)
# Output: ReviewedDecision

def review_decision(decision: Decision) -> ReviewedDecision:
    """
    Se confiança < 70%, encaminha para revisão humana:
    - Cria ticket
    - Notifica analista
    - Aguarda aprovação
    """
    
    if decision.confidence < 0.7:
        ticket = create_ticket(
            title=f"Review: {decision.action}",
            description=decision.reasoning,
            priority="HIGH"
        )
        
        notify_analyst(ticket)
        
        return ReviewedDecision(
            status="PENDING_REVIEW",
            ticket_id=ticket.id
        )
    
    return ReviewedDecision(
        status="APPROVED",
        decision=decision
    )
```

**Fluxo:**
```
Decision → Confidence Check → Human Review (se necessário) → Final Decision
```

---

## 3️⃣ ESTRUTURA DE DADOS - Modelos Internos

### 3.1 Alert (Entrada)
```python
{
    "timestamp": "2026-02-06T12:00:00Z",
    "fingerprint": "abc123def456",
    "service": "payment-api",
    "severity": "critical",
    "description": "Error rate exceeded 5%",
    "source": "PROMETHEUS",
    "labels": {
        "alertname": "HighErrorRate",
        "instance": "payment-api:8000",
        "job": "payment-api"
    },
    "annotations": {
        "summary": "High error rate detected",
        "runbook": "https://wiki.company.com/runbooks/high-error-rate"
    }
}
```

### 3.2 NormalizedAlert (Intermediário)
```python
{
    "timestamp": "2026-02-06T12:00:00Z",
    "fingerprint": "abc123def456",
    "service": "payment-api",
    "severity": "critical",
    "description": "Error rate exceeded 5%",
    "labels": {...},
    "validation_status": "VALID",
    "normalized_at": "2026-02-06T12:00:01Z"
}
```

### 3.3 AlertCluster (Agrupado)
```python
{
    "cluster_id": "cluster-xyz789",
    "service": "payment-api",
    "alerts": [NormalizedAlert, ...],
    "cluster_type": "SERVICE_DEGRADATION",
    "formed_at": "2026-02-06T12:00:02Z"
}
```

### 3.4 Decision (Saída)
```python
{
    "decision_id": "dec-123",
    "cluster_id": "cluster-xyz789",
    "action": "ESCALATE",
    "severity": "CRITICAL",
    "confidence": 0.95,
    "reasoning": "Error rate trending up for 15 minutes",
    "evidence": {
        "metrics": MetricsAnalysisResult,
        "graph": GraphContext,
        "similar": SimilarityResult
    },
    "status": "APPROVED",
    "created_at": "2026-02-06T12:00:05Z"
}
```

---

## 4️⃣ FLUXO COMPLETO - Exemplo Prático

### Cenário: Alerta de Alta Taxa de Erro

```
1. PROMETHEUS DISPARA ALERTA
   └─ HighErrorRate: payment-api error rate = 7.2%

2. ALERT COLLECTOR
   └─ Busca em http://localhost:9090/api/v1/alerts
   └─ Retorna: Alert(service="payment-api", severity="critical")

3. ALERT NORMALIZER
   └─ Valida: ✓ service, ✓ severity, ✓ description
   └─ Retorna: NormalizedAlert(...)

4. ALERT CORRELATOR
   └─ Agrupa com outros alertas de payment-api
   └─ Retorna: AlertCluster(service="payment-api", alerts=[...])

5. METRICS ANALYSIS (Paralelo)
   └─ Query Prometheus: rate(payment_api_errors_total[5m])
   └─ Analisa: Trending UP (7.2% → 8.1% → 9.3%)
   └─ Retorna: MetricsAnalysisResult(trend=CRITICAL_UP, confidence=0.98)

6. GRAPH ANALYSIS (Paralelo)
   └─ Query Neo4j: Serviços que dependem de payment-api
   └─ Encontra: checkout-service, order-service
   └─ Retorna: GraphContext(dependent_services=[...])

7. EMBEDDING ANALYSIS (Paralelo)
   └─ Gera embedding: "payment api error rate high"
   └─ Busca Qdrant: Alertas similares
   └─ Encontra: 3 alertas similares (resolução: ESCALATE)
   └─ Retorna: SimilarityResult(confidence=0.92)

8. DECISION ENGINE
   └─ Aplica regra: IF trend=CRITICAL_UP THEN ESCALATE
   └─ Confiança: 0.95 (> 0.7, sem revisão humana)
   └─ Retorna: Decision(action=ESCALATE, confidence=0.95)

9. SAÍDA
   └─ Cria ticket de escalação
   └─ Notifica on-call engineer
   └─ Registra audit log
   └─ Armazena decision em Neo4j para futuro
```

---

## 5️⃣ INTEGRAÇÃO COM OBSERVABILIDADE

### 5.1 Métricas Prometheus

```
# Latência de cada agente
strands_agent_execution_seconds{agent="collector"} = 0.234
strands_agent_execution_seconds{agent="normalizer"} = 0.045
strands_agent_execution_seconds{agent="correlator"} = 0.123

# Taxa de sucesso
strands_agent_success_rate{agent="collector"} = 0.98
strands_agent_success_rate{agent="normalizer"} = 0.95

# Confiança de decisões
strands_decision_confidence_histogram = [0.45, 0.67, 0.89, 0.95, ...]
```

### 5.2 Traces Distribuídos (Jaeger)

```
Trace: alert-processing-abc123
├─ AlertCollector
│  ├─ prometheus.query_alerts (45ms)
│  └─ parse_response (12ms)
├─ AlertNormalizer
│  ├─ validate_alert (8ms)
│  └─ normalize_fields (5ms)
├─ AlertCorrelator
│  ├─ group_by_service (3ms)
│  └─ form_clusters (15ms)
├─ MetricsAnalysis (paralelo)
│  ├─ prometheus.query_range (234ms)
│  └─ analyze_trend (45ms)
├─ GraphAnalysis (paralelo)
│  ├─ neo4j.query (67ms)
│  └─ build_context (12ms)
├─ EmbeddingAnalysis (paralelo)
│  ├─ ollama.embed (123ms)
│  └─ qdrant.search (89ms)
├─ DecisionEngine
│  ├─ apply_rules (5ms)
│  └─ ollama.analyze (456ms)
└─ Total: 1.2s
```

---

## 6️⃣ CONFIGURAÇÃO E DEPLOYMENT

### 6.1 Variáveis de Ambiente

```bash
# Prometheus
PROMETHEUS_URL=http://localhost:9090
PROMETHEUS_TIMEOUT=10s

# Grafana
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=xxx

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Qdrant
QDRANT_URL=http://localhost:6333

# Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=nomic-embed-text:latest

# Timeouts
AGENT_TIMEOUT=30s
DECISION_CONFIDENCE_THRESHOLD=0.7
```

### 6.2 Docker Compose

```yaml
services:
  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  
  neo4j:
    image: neo4j:5-community
    ports: ["7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/password
  
  qdrant:
    image: qdrant/qdrant
    ports: ["6333:6333"]
  
  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
  
  strands:
    build: .
    ports: ["8000:8000"]
    depends_on:
      - prometheus
      - neo4j
      - qdrant
      - ollama
```

---

## 7️⃣ RESUMO - Fluxo de Dados

```
ENTRADA
├─ Prometheus: /api/v1/alerts
├─ Grafana: /api/v1/rules
└─ ServiceNow: /api/incidents

PROCESSAMENTO
├─ Collector: Raw Alerts
├─ Normalizer: Validated Alerts
├─ Correlator: Alert Clusters
├─ Metrics Analysis: Trends & Anomalies
├─ Graph Analysis: Dependencies & Context
├─ Embedding Analysis: Similar Alerts
├─ Decision Engine: Recommended Action
└─ Human Review: Final Approval (se necessário)

SAÍDA
├─ Tickets (ServiceNow/Jira)
├─ Notifications (Slack/Email)
├─ Escalations (PagerDuty)
├─ Remediation Actions
└─ Audit Logs (Neo4j)

OBSERVABILIDADE
├─ Prometheus: Métricas de agentes
├─ Jaeger: Traces distribuídos
└─ Grafana: Dashboards em tempo real
```

---

## 📚 Referências

- **Prometheus API**: http://localhost:9090/api/v1/alerts
- **Grafana API**: http://localhost:3000/api/v1/rules
- **Neo4j**: bolt://localhost:7687
- **Qdrant**: http://localhost:6333
- **Ollama**: http://localhost:11434
