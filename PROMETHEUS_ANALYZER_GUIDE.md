# 🔍 Prometheus Analyzer - LLM-Powered Metrics Analysis

## 📋 Overview

O **Prometheus Analyzer** é um serviço que coleta métricas do Prometheus e usa LLM (Ollama) para gerar insights inteligentes sobre o estado do sistema.

## 🎯 Funcionalidades

- ✅ **Coleta de Métricas**: Consulta Prometheus em tempo real
- ✅ **Detecção de Alertas**: Identifica anomalias e thresholds
- ✅ **Análise com LLM**: Usa Ollama para análise inteligente
- ✅ **API REST**: Endpoints para consulta sob demanda
- ✅ **Análise Periódica**: Executa análises automaticamente a cada 60s

## 🚀 Quick Start

### 1. Com Docker Compose

```bash
# Usar docker-compose-frontend.yml (desenvolvimento)
docker-compose -f docker-compose-frontend.yml up -d prometheus-analyzer

# Ou docker-compose.yaml (produção)
docker-compose up -d prometheus-analyzer
```

### 2. Acessar API

```bash
# Health check
curl http://localhost:8001/health

# Análise sob demanda
curl http://localhost:8001/analyze

# Última análise
curl http://localhost:8001/last-analysis

# Métricas coletadas
curl http://localhost:8001/metrics

# Alertas atuais
curl http://localhost:8001/alerts
```

## 📊 Endpoints Disponíveis

### GET /health
Verificar saúde do serviço

```bash
curl http://localhost:8001/health
```

**Resposta:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-06T12:00:00"
}
```

### GET /analyze
Executar análise sob demanda

```bash
curl http://localhost:8001/analyze
```

**Resposta:**
```json
{
  "timestamp": "2026-02-06T12:00:00",
  "metrics": {
    "error_rate": {"value": "0.02", "timestamp": "..."},
    "request_latency_p95": {"value": "0.45", "timestamp": "..."},
    ...
  },
  "alerts": [
    {
      "severity": "warning",
      "metric": "latency_p95",
      "value": 0.45,
      "message": "P95 latency is 0.45s"
    }
  ],
  "analysis": {
    "status": "success",
    "analysis": "O sistema está operando normalmente...",
    "timestamp": "..."
  },
  "alert_count": 1,
  "critical_alerts": 0
}
```

### GET /last-analysis
Obter última análise realizada

```bash
curl http://localhost:8001/last-analysis
```

### GET /metrics
Obter métricas coletadas

```bash
curl http://localhost:8001/metrics
```

**Resposta:**
```json
{
  "error_rate": {
    "value": "0.02",
    "timestamp": "2026-02-06T12:00:00",
    "labels": {"job": "prometheus"}
  },
  "request_latency_p95": {
    "value": "0.45",
    "timestamp": "2026-02-06T12:00:00",
    "labels": {}
  },
  ...
}
```

### GET /alerts
Obter alertas atuais

```bash
curl http://localhost:8001/alerts
```

**Resposta:**
```json
{
  "alerts": [
    {
      "severity": "warning",
      "metric": "cpu_usage",
      "value": 85.5,
      "message": "CPU usage is 85.50%"
    }
  ],
  "count": 1,
  "critical": 0,
  "timestamp": "2026-02-06T12:00:00"
}
```

### POST /analyze
Disparar análise (mesmo que GET)

```bash
curl -X POST http://localhost:8001/analyze
```

## 🔧 Configuração

### Variáveis de Ambiente

```bash
PROMETHEUS_URL=http://prometheus:9090
OLLAMA_URL=http://ollama:11434
LOG_LEVEL=INFO
ANALYSIS_INTERVAL=60  # Segundos
ALERT_THRESHOLD=0.8   # 80%
```

### Métricas Monitoradas

O analyzer coleta as seguintes métricas:

| Métrica | Query | Threshold |
|---------|-------|-----------|
| **Error Rate** | `rate(http_requests_total{status=~'5..'}[5m])` | > 5% |
| **Latência P95** | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` | > 1s |
| **CPU Usage** | `rate(process_cpu_seconds_total[5m]) * 100` | > 80% |
| **Memory Usage** | `process_resident_memory_bytes / 1024 / 1024` | - |
| **Conexões Ativas** | `up` | - |
| **Erros do Simulator** | `simulator_errors_total` | - |

## 🚨 Alertas

O analyzer detecta automaticamente alertas baseado em thresholds:

### Críticos
- Error rate > 10%
- Latência P95 > 2s
- CPU > 95%

### Warnings
- Error rate > 5%
- Latência P95 > 1s
- CPU > 80%

## 🤖 Integração com LLM

O analyzer usa **Ollama (mistral)** para análise inteligente:

```python
# Exemplo de prompt enviado ao LLM
prompt = """
Você é um especialista em observabilidade...

Analise as seguintes métricas do Prometheus:
{metrics_json}

Por favor, forneça:
1. Resumo do status atual
2. Alertas detectados
3. Recomendações
4. Tendências
"""
```

### Resposta do LLM

```
O sistema está operando normalmente com latência aceitável.
Detectei 1 alerta de warning: CPU usage está em 85%.

Recomendações:
- Monitorar CPU nos próximos 10 minutos
- Se persistir, considerar scaling horizontal
- Verificar processos pesados em background
```

## 📈 Fluxo de Análise

```
1. Coleta de Métricas
   └─ Consulta Prometheus (6 métricas principais)

2. Detecção de Alertas
   └─ Compara valores com thresholds

3. Análise com LLM
   └─ Envia métricas + alertas para Ollama
   └─ Recebe análise inteligente

4. Compilação de Resultado
   └─ Retorna JSON com tudo
```

## 🔄 Análise Periódica

O analyzer executa análise automática a cada 60 segundos:

```bash
# Ver logs
docker-compose logs -f prometheus-analyzer

# Exemplo de log
# INFO: Starting Prometheus analysis...
# INFO: Collected metrics: 6 metrics
# INFO: Found 1 alerts
# INFO: LLM analysis completed: success
```

## 🧪 Teste Manual

### 1. Verificar Saúde

```bash
curl http://localhost:8001/health
```

### 2. Executar Análise

```bash
curl -X POST http://localhost:8001/analyze | jq .
```

### 3. Ver Alertas

```bash
curl http://localhost:8001/alerts | jq .
```

### 4. Simular Erro (no Error Simulator)

```bash
curl -X POST http://localhost:8001/simulate/error?error_type=database_timeout

# Aguardar ~5 segundos

# Verificar alertas
curl http://localhost:8001/alerts
```

## 🐛 Troubleshooting

### Analyzer não inicia

```bash
# Ver logs
docker-compose logs prometheus-analyzer

# Verificar conectividade
docker-compose exec prometheus-analyzer curl http://prometheus:9090/api/v1/targets
```

### Prometheus não responde

```bash
# Verificar se Prometheus está rodando
curl http://localhost:9090/api/v1/targets

# Verificar health
docker-compose exec prometheus curl http://localhost:9090/-/healthy
```

### Ollama não responde

```bash
# Verificar se Ollama está rodando
curl http://localhost:11434/api/tags

# Verificar se modelo está carregado
docker-compose exec ollama ollama list
```

### Métricas vazias

```bash
# Verificar se Prometheus tem dados
curl 'http://localhost:9090/api/v1/query?query=up'

# Se vazio, Prometheus pode não ter targets configurados
# Verificar prometheus.yml
```

## 📊 Integração com Dashboard

O frontend pode exibir análises do Prometheus Analyzer:

```javascript
// Buscar análise
fetch('http://localhost:8001/analyze')
  .then(r => r.json())
  .then(data => {
    console.log('Alertas:', data.alerts);
    console.log('Análise:', data.analysis.analysis);
  });
```

## 🔗 Relacionados

- `prometheus_analyzer.py` - Código fonte
- `Dockerfile.analyzer` - Configuração Docker
- `docker-compose-frontend.yml` - Stack desenvolvimento
- `docker-compose.yaml` - Stack produção
- `DOCKER_FRONTEND_GUIDE.md` - Guia Docker completo

## 📞 Suporte

Para problemas:

1. Verificar logs: `docker-compose logs prometheus-analyzer`
2. Verificar conectividade: `curl http://localhost:8001/health`
3. Verificar Prometheus: `curl http://localhost:9090/api/v1/targets`
4. Verificar Ollama: `curl http://localhost:11434/api/tags`

---

**Status**: Pronto para uso  
**Última atualização**: 2026-02-06  
**Versão**: 1.0
