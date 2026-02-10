# Enterprise-Grade SRE Guide - Strands Correlator & Recommender

**Version:** 2.0.0 (Enterprise)  
**Status:** Production-Ready  
**Last Updated:** 2026-02-10

---

## 📋 Visão Geral Executiva

Os agentes **Correlator** e **Recommender** foram refatorados para atender aos padrões de produção enterprise com foco em **resiliência**, **observabilidade** e **governança**. Esta documentação descreve a arquitetura, operação e monitoramento desses componentes.

### 🎯 Objetivos Alcançados

| Objetivo | Status | Detalhe |
|----------|--------|---------|
| Remover Mocks | ✅ | Integração real com Prometheus e Kubernetes API |
| Resiliência | ✅ | Circuit breaker, retry com backoff, timeout |
| Observabilidade | ✅ | Métricas, logging estruturado, correlation IDs |
| Correlação Avançada | ✅ | Lag detection, normalização, Bayesiano |
| Governança | ✅ | Versionamento, auditoria, rastreabilidade |

---

## 🏗️ Arquitetura

### Camadas de Infraestrutura

```
┌─────────────────────────────────────────────────────────────┐
│                  CorrelatorAgentEnterprise                  │
│                   RecommenderAgentEnterprise                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Camadas de Suporte                       │
├─────────────────────────────────────────────────────────────┤
│ • ObservabilityContext (métricas, logs, health)            │
│ • ResilienceContext (circuit breaker, retry, timeout)      │
│ • AdvancedCorrelationAnalyzer (lag, normalização)          │
│ • BayesianConfidenceCalculator (confiança estatística)     │
│ • ModelGovernance (versionamento, auditoria)               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Camadas de Dados Reais                     │
├─────────────────────────────────────────────────────────────┤
│ • PrometheusClient (métricas de infraestrutura)            │
│ • KubectlMCPClient (logs e eventos de cluster)             │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Análise com Resiliência

```
Alert → ResilienceContext
         ├─ Circuit Breaker (verifica estado)
         ├─ Retry (com backoff exponencial)
         ├─ Timeout (30s padrão)
         └─ Executa análise
            ├─ Log-Metric Correlation
            ├─ Metric-Metric Correlation (com lag)
            └─ Temporal Correlation
         └─ Consolida com Bayesiano
         └─ Registra em Governança
         └─ Exporta Observabilidade
```

---

## 🔄 Resiliência

### Circuit Breaker

Protege contra falhas em cascata em chamadas a Prometheus e Kubernetes.

**Estados:**
- **CLOSED:** Normal, requisições passam
- **OPEN:** Falhas detectadas, requisições bloqueadas
- **HALF_OPEN:** Testando recuperação

**Configuração Padrão:**
- Threshold de falha: 5 falhas consecutivas
- Timeout de recuperação: 60 segundos
- Métricas: Taxa de sucesso, falhas, rejeições

**Exemplo de Uso:**
```python
resilience_context = ResilienceContext(
    name="prometheus",
    circuit_breaker=CircuitBreaker("prometheus", failure_threshold=5),
    retry_config=RetryConfig(max_attempts=3),
    timeout_seconds=30.0
)

result = resilience_context.execute(
    prometheus_client.query_range,
    query, start_time, end_time
)
```

### Retry com Backoff Exponencial

Implementa retry automático com jitter para evitar thundering herd.

**Fórmula:**
```
delay = min(initial_delay * (base ^ attempt), max_delay)
delay += random(-20%, +20%)  # Jitter
```

**Configuração Padrão:**
- Máximo de tentativas: 3
- Delay inicial: 1.0s
- Delay máximo: 60.0s
- Base exponencial: 2.0
- Jitter: ±20%

### Timeout

Evita que requisições travem o agente.

**Padrão:** 30 segundos por chamada externa

---

## 📊 Observabilidade

### Métricas Coletadas

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `analysis_started` | COUNTER | Análises iniciadas |
| `analysis_completed` | COUNTER | Análises completadas |
| `analysis_errors` | COUNTER | Erros durante análise |
| `low_confidence_decisions` | COUNTER | Decisões com confiança baixa |
| `log_metric_correlations_found` | COUNTER | Correlações log-métrica |
| `metric_metric_correlations_found` | COUNTER | Correlações métrica-métrica |
| `temporal_correlations_found` | COUNTER | Correlações temporais |
| `analysis_duration` | TIMER | Tempo de análise (ms) |
| `log_metric_correlation` | TIMER | Tempo da análise log-métrica |
| `metric_metric_correlation` | TIMER | Tempo da análise métrica-métrica |
| `temporal_correlation` | TIMER | Tempo da análise temporal |

### Logging Estruturado

Todos os eventos são registrados em JSON com correlation ID.

**Exemplo de Log de Decisão:**
```json
{
  "timestamp": "2026-02-10T15:30:45.123Z",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "correlator-enterprise",
  "event_type": "DECISION",
  "decision_type": "CORRELATION",
  "hypothesis": "Correlação detectada (LOG_METRIC_CORRELATION): Investigar stack traces",
  "confidence": 0.92,
  "evidence_count": 2,
  "suggested_actions": 1,
  "metadata": {
    "decision_id": "dec-123456",
    "execution_time_ms": 245.67,
    "patterns": 1,
    "model_version": "2.0.0"
  }
}
```

### Health Status

Endpoint `/health` retorna status completo:

```python
status = agent.get_status()
# Retorna:
# {
#   "agent_id": "correlator-enterprise",
#   "model_version": "2.0.0",
#   "observability": {...},
#   "resilience": {
#     "prometheus": {...},
#     "kubectl": {...}
#   },
#   "governance": {...}
# }
```

---

## 🔬 Análise Avançada de Correlação

### Detecção de Lag (Cross-Correlation)

Detecta defasagem temporal entre séries.

**Exemplo:**
```
CPU:  ▁▂▃▄▅▆▇█ (sobe imediatamente)
Mem:  ▁▁▂▃▄▅▆▇ (sobe 1 passo depois)
      ← lag = 1
```

**Implementação:**
```python
result = analyzer.analyze_with_lag(
    cpu_series,
    memory_series,
    max_lag=5,
    normalize=True
)
# result.lag_offset = 1  # Memória segue CPU com 1 passo de atraso
# result.correlation_coefficient = 0.92
# result.p_value = 0.0001
```

### Normalização (Z-Score)

Remove escala, permitindo comparação entre séries diferentes.

**Fórmula:**
```
z = (x - mean) / std_dev
```

**Benefício:** CPU (0-100%) e Memória (0-50GB) podem ser comparadas diretamente.

### Detrending

Remove tendência linear para focar em variações.

**Exemplo:**
```
Original:  ▂▃▄▅▆▇█▇▆▅  (tendência de subida)
Detrended: ▄▂▅▃▆▄█▅▃▁  (variações isoladas)
```

### Detecção de Anomalias

Usa z-score para identificar outliers.

**Padrão:** Valores > 3σ (desvio padrão) são considerados anomalias.

### Significância Estatística

Testa se correlação é real ou por acaso.

| P-Value | Significância | Interpretação |
|---------|---------------|---------------|
| < 0.01 | VERY_SIGNIFICANT | 99% confiança |
| < 0.05 | SIGNIFICANT | 95% confiança |
| < 0.10 | WEAK | 90% confiança |
| ≥ 0.10 | NOT_SIGNIFICANT | Pode ser acaso |

---

## 🧮 Confiança Bayesiana

### Fórmula

```
P(Correlação Real | Dados) = P(Dados | Correlação Real) × P(Correlação Real) / P(Dados)

Posterior = Likelihood × Prior / Evidence
```

### Componentes

**Prior (Probabilidade Anterior):**
- Baseado em histórico: quantas correlações foram reais?
- Padrão: 0.3 (30% das correlações detectadas são reais)

**Likelihood (Verossimilhança):**
- P(Dados | Correlação Real) = 0.95 (se correlação real, dados têm 95% chance)
- P(Dados | Correlação Falsa) = 0.05 (se falsa, dados têm 5% chance)

**Posterior (Probabilidade Final):**
- Resultado: 0.0 a 1.0 (confiança de que correlação é real)

### Exemplo

```
Correlação de Pearson: r = 0.85
P-value: 0.02
Amostras: 50

Likelihood = 0.95 (p < 0.05)
Prior = 0.3
Posterior = (0.95 × 0.3) / ((0.95 × 0.3) + (0.05 × 0.7))
         = 0.285 / 0.32
         = 0.89 (89% confiança)
```

---

## 📋 Governança de Modelos

### Versionamento

Quatro versões de modelo disponíveis:

| Versão | Nome | Características |
|--------|------|-----------------|
| 1.0.0 | BASIC | Pearson simples, sem lag |
| 1.1.0 | LAG_DETECTION | Com detecção de lag |
| 2.0.0 | BAYESIAN | Com confiança Bayesiana |
| 2.1.0 | ADAPTIVE | Com threshold adaptativo |

**Mudar Versão:**
```python
governance.switch_model_version(ModelVersion.V2_BAYESIAN)
```

### Auditoria de Decisões

Cada decisão é registrada com:
- ID único (UUID)
- Versão do modelo
- Hash da configuração
- Hipótese e confiança
- Evidência coletada
- Timestamp e tempo de execução
- Status (PENDING → APPROVED → EXECUTED)

**Recuperar Trilha:**
```python
audit = governance.get_decision_audit_trail(decision_id)
# Retorna histórico completo da decisão
```

### Métricas de Desempenho

```python
metrics = governance.get_model_performance_metrics()
# {
#   "total_decisions": 1000,
#   "approved": 850,
#   "rejected": 150,
#   "executed": 750,
#   "approval_rate": 0.85,
#   "execution_rate": 0.75,
#   "avg_confidence": 0.82,
#   "by_correlation_type": {...}
# }
```

---

## 🚨 Operação em Produção

### Inicialização

```python
from src.agents.analysis.correlator_enterprise import CorrelatorAgentEnterprise

agent = CorrelatorAgentEnterprise()
# Inicializa com:
# - Clientes reais (Prometheus, Kubernetes)
# - Circuit breakers
# - Observabilidade
# - Governança
```

### Análise de Alerta

```python
from src.models.alert import NormalizedAlert

alert = NormalizedAlert(
    fingerprint="alert-123",
    service="api-service",
    severity="critical",
    description="High error rate",
    timestamp=datetime.now(timezone.utc),
    labels={"pod": "api-pod-1", "namespace": "default"},
    validation_status=ValidationStatus.VALID
)

result = agent.analyze(alert)
# Retorna SwarmResult com:
# - hypothesis: Descrição da correlação
# - confidence: 0.0 a 1.0
# - evidence: Lista de evidências
# - suggested_actions: Ações recomendadas
```

### Monitoramento

```python
# Status completo do agente
status = agent.get_status()

# Observabilidade
health = agent.observability.get_health_status()
metrics = agent.observability.metrics.get_summary()

# Governança
audit = agent.governance.export_audit_trail()
```

---

## ⚠️ Tratamento de Falhas

### Cenários Comuns

**1. Prometheus Indisponível**
- Circuit breaker abre após 5 falhas
- Modo degradado: análise apenas com logs
- Retry automático a cada 60s

**2. Kubernetes API Lenta**
- Timeout de 30s
- Retry com backoff
- Fallback: usar cache de pods anterior

**3. Série Vazia**
- Detecção automática
- Retorna confiança 0.0
- Log de aviso estruturado

**4. Ruído Alto em Métricas**
- Detrending automático
- Detecção de anomalias
- Threshold de significância aplicado

---

## 📈 Tuning e Otimização

### Ajustar Threshold de Confiança

```python
config = governance.get_current_config()
config.confidence_threshold = 0.70  # Mais permissivo
config.confidence_threshold = 0.80  # Mais rigoroso
```

### Ajustar Lag Máximo

```python
# Para sistemas com latência maior
config.max_lag = 10  # Padrão: 5

# Para sistemas com latência baixa
config.max_lag = 2
```

### Ajustar Tamanho de Amostra

```python
# Mais rigoroso (mais dados necessários)
config.min_sample_size = 50

# Mais permissivo (menos dados)
config.min_sample_size = 10
```

---

## 🔍 Troubleshooting

### Confiança Sempre Baixa

**Causas:**
- Séries desalinhadas (lag não detectado)
- Ruído alto
- Correlação real é fraca

**Solução:**
- Aumentar `max_lag`
- Usar detrending
- Revisar dados brutos

### Circuit Breaker Sempre Aberto

**Causas:**
- Prometheus/Kubernetes realmente indisponível
- Timeout muito curto
- Rede instável

**Solução:**
- Verificar conectividade
- Aumentar `timeout_seconds`
- Aumentar `recovery_timeout_seconds`

### Muitos Falsos Positivos

**Causas:**
- Threshold de confiança muito baixo
- Correlação de Pearson sensível a outliers

**Solução:**
- Aumentar `confidence_threshold`
- Ativar detecção de anomalias
- Usar detrending

---

## 📚 Referências

- **Correlação de Pearson:** [Wikipedia](https://en.wikipedia.org/wiki/Pearson_correlation_coefficient)
- **Teste de Significância:** [P-value](https://en.wikipedia.org/wiki/P-value)
- **Teorema de Bayes:** [Bayesian Inference](https://en.wikipedia.org/wiki/Bayesian_inference)
- **Circuit Breaker Pattern:** [Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)
- **SRE Principles:** [Google SRE Book](https://sre.google/books/)

---

**Versão:** 2.0.0 Enterprise  
**Última Atualização:** 2026-02-10  
**Status:** Production-Ready ✅
