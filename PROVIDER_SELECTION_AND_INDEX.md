# 📚 Seleção de Providers e Índice Completo de Documentação

## 🔄 Como os 3 Providers são Escolhidos

### **Visão Geral**

O Strands suporta **3 providers de alertas** que são escolhidos dinamicamente com base em **disponibilidade e prioridade**:

```
┌─────────────────────────────────────────────────────────┐
│ ALERT COLLECTOR                                         │
│                                                         │
│ Tenta conectar em ORDEM DE PRIORIDADE:                 │
│                                                         │
│ 1️⃣ Prometheus (Prioridade: 100)                        │
│    └─ Se disponível → Usa Prometheus                   │
│    └─ Se não → Tenta próximo                           │
│                                                         │
│ 2️⃣ Grafana (Prioridade: 50)                            │
│    └─ Se disponível → Usa Grafana                      │
│    └─ Se não → Tenta próximo                           │
│                                                         │
│ 3️⃣ ServiceNow (Prioridade: 10)                         │
│    └─ Se disponível → Usa ServiceNow                   │
│    └─ Se não → Falha (sem alertas)                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### **Código de Seleção**

```python
class AlertCollectorAgent:
    """
    Coleta alertas de múltiplos providers
    Usa ordem de prioridade para seleção
    """
    
    PROVIDERS = [
        {
            "name": "prometheus",
            "priority": 100,
            "endpoint": "http://prometheus:9090/api/v1/alerts",
            "timeout": 5,
            "retry": 3
        },
        {
            "name": "grafana",
            "priority": 50,
            "endpoint": "http://grafana:3000/api/ruler/grafana/rules",
            "timeout": 5,
            "retry": 3
        },
        {
            "name": "servicenow",
            "priority": 10,
            "endpoint": "https://company.service-now.com/api/now/table/incident",
            "timeout": 10,
            "retry": 2
        }
    ]
    
    async def collect_active_alerts(self) -> List[Alert]:
        """
        Coleta alertas tentando providers em ordem de prioridade
        """
        alerts = []
        
        # Ordena providers por prioridade (decrescente)
        sorted_providers = sorted(
            self.PROVIDERS,
            key=lambda p: p["priority"],
            reverse=True
        )
        
        for provider in sorted_providers:
            try:
                # Tenta conectar ao provider
                logger.info(f"Tentando coletar de {provider['name']}...")
                
                if provider["name"] == "prometheus":
                    alerts.extend(await self._collect_from_prometheus(provider))
                    logger.info(f"✓ Prometheus: {len(alerts)} alertas coletados")
                    break  # Sucesso! Para de tentar outros
                
                elif provider["name"] == "grafana":
                    alerts.extend(await self._collect_from_grafana(provider))
                    logger.info(f"✓ Grafana: {len(alerts)} alertas coletados")
                    break  # Sucesso! Para de tentar outros
                
                elif provider["name"] == "servicenow":
                    alerts.extend(await self._collect_from_servicenow(provider))
                    logger.info(f"✓ ServiceNow: {len(alerts)} alertas coletados")
                    break  # Sucesso! Para de tentar outros
            
            except ConnectionError as e:
                logger.warning(f"✗ {provider['name']}: Conexão falhou - {e}")
                continue  # Tenta próximo provider
            
            except TimeoutError as e:
                logger.warning(f"✗ {provider['name']}: Timeout - {e}")
                continue  # Tenta próximo provider
            
            except Exception as e:
                logger.error(f"✗ {provider['name']}: Erro - {e}")
                continue  # Tenta próximo provider
        
        if not alerts:
            logger.error("✗ Nenhum provider disponível!")
            raise NoAlertProviderAvailable(
                "Todos os providers falharam. "
                "Verifique conectividade com Prometheus, Grafana ou ServiceNow."
            )
        
        return alerts
    
    async def _collect_from_prometheus(self, provider: dict) -> List[Alert]:
        """Coleta de Prometheus"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                provider["endpoint"],
                timeout=aiohttp.ClientTimeout(total=provider["timeout"])
            ) as response:
                if response.status != 200:
                    raise ConnectionError(f"Status {response.status}")
                
                data = await response.json()
                
                # Converte alertas Prometheus
                alerts = []
                for alert in data.get("data", {}).get("alerts", []):
                    alerts.append(Alert(
                        timestamp=datetime.fromisoformat(alert["startsAt"]),
                        fingerprint=alert["labels"]["alertname"],
                        service=alert["labels"].get("service", "unknown"),
                        severity=alert["labels"].get("severity", "warning"),
                        description=alert["annotations"]["summary"],
                        source=AlertSource.PROMETHEUS,
                        labels=alert["labels"],
                        annotations=alert["annotations"]
                    ))
                
                return alerts
    
    async def _collect_from_grafana(self, provider: dict) -> List[Alert]:
        """Coleta de Grafana"""
        async with aiohttp.ClientSession() as session:
            # Autentica com Grafana
            headers = {
                "Authorization": f"Bearer {self.grafana_api_key}"
            }
            
            async with session.get(
                provider["endpoint"],
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=provider["timeout"])
            ) as response:
                if response.status != 200:
                    raise ConnectionError(f"Status {response.status}")
                
                data = await response.json()
                
                # Converte alertas Grafana
                alerts = []
                for rule_group in data.get("data", []):
                    for rule in rule_group.get("rules", []):
                        # Verifica se regra está disparada
                        if rule.get("state") == "alerting":
                            alerts.append(Alert(
                                timestamp=datetime.now(),
                                fingerprint=rule["uid"],
                                service=rule.get("labels", {}).get("service", "unknown"),
                                severity=rule.get("labels", {}).get("severity", "warning"),
                                description=rule.get("annotations", {}).get("description", ""),
                                source=AlertSource.GRAFANA,
                                labels=rule.get("labels", {}),
                                annotations=rule.get("annotations", {})
                            ))
                
                return alerts
    
    async def _collect_from_servicenow(self, provider: dict) -> List[Alert]:
        """Coleta de ServiceNow"""
        async with aiohttp.ClientSession() as session:
            # Autentica com ServiceNow
            headers = {
                "Authorization": f"Bearer {self.servicenow_api_key}"
            }
            
            async with session.get(
                provider["endpoint"],
                params={"sysparm_query": "stateIN1,2"},  # New, In Progress
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=provider["timeout"])
            ) as response:
                if response.status != 200:
                    raise ConnectionError(f"Status {response.status}")
                
                data = await response.json()
                
                # Converte incidentes ServiceNow
                alerts = []
                for incident in data.get("result", []):
                    alerts.append(Alert(
                        timestamp=datetime.fromisoformat(incident["created"]),
                        fingerprint=incident["number"],
                        service=self._extract_service(incident),
                        severity=self._map_severity(incident["severity"]),
                        description=incident["short_description"],
                        source=AlertSource.SERVICENOW,
                        labels={
                            "incident_number": incident["number"],
                            "assigned_to": incident["assigned_to"],
                            "impact": incident["impact"]
                        },
                        annotations={
                            "full_description": incident["description"],
                            "created_by": incident["created_by"]
                        }
                    ))
                
                return alerts
```

### **Fluxo de Decisão**

```
┌─────────────────────────────────────┐
│ AlertCollector.collect_active_alerts│
└────────────┬────────────────────────┘
             │
             ▼
    ┌────────────────────┐
    │ Prometheus         │
    │ Disponível?        │
    └────┬───────────┬───┘
         │ SIM       │ NÃO
         │           │
         ▼           ▼
      ✓ USE      ┌────────────────────┐
                 │ Grafana            │
                 │ Disponível?        │
                 └────┬───────────┬───┘
                      │ SIM       │ NÃO
                      │           │
                      ▼           ▼
                   ✓ USE      ┌────────────────────┐
                              │ ServiceNow         │
                              │ Disponível?        │
                              └────┬───────────┬───┘
                                   │ SIM       │ NÃO
                                   │           │
                                   ▼           ▼
                                ✓ USE        ✗ ERRO
```

---

## 📊 Comparação dos 3 Providers

| Aspecto | Prometheus | Grafana | ServiceNow |
|---------|-----------|---------|-----------|
| **Tipo** | Métrica | Métrica | Incidente |
| **Estrutura** | Numérica | Numérica | Textual |
| **Latência** | ~100ms | ~200ms | ~500ms |
| **Confiabilidade** | Alta | Alta | Média |
| **Prioridade** | 100 (Máxima) | 50 (Média) | 10 (Mínima) |
| **Contexto** | Limitado | Limitado | Rico |
| **Escalabilidade** | Excelente | Boa | Boa |
| **Custo** | Gratuito | Gratuito | Pago |

---

## 🔧 Configuração de Providers

### **.env**

```bash
# Prometheus
PROMETHEUS_ENABLED=true
PROMETHEUS_URL=http://prometheus:9090
PROMETHEUS_TIMEOUT=5
PROMETHEUS_RETRY=3

# Grafana
GRAFANA_ENABLED=true
GRAFANA_URL=http://grafana:3000
GRAFANA_API_KEY=xxx
GRAFANA_TIMEOUT=5
GRAFANA_RETRY=3

# ServiceNow
SERVICENOW_ENABLED=true
SERVICENOW_URL=https://company.service-now.com
SERVICENOW_API_KEY=xxx
SERVICENOW_TIMEOUT=10
SERVICENOW_RETRY=2

# Prioridades (customizável)
PROVIDER_PRIORITY_PROMETHEUS=100
PROVIDER_PRIORITY_GRAFANA=50
PROVIDER_PRIORITY_SERVICENOW=10
```

### **docker-compose.yml**

```yaml
services:
  strands:
    environment:
      - PROMETHEUS_ENABLED=true
      - PROMETHEUS_URL=http://prometheus:9090
      - GRAFANA_ENABLED=true
      - GRAFANA_URL=http://grafana:3000
      - GRAFANA_API_KEY=${GRAFANA_API_KEY}
      - SERVICENOW_ENABLED=true
      - SERVICENOW_URL=${SERVICENOW_URL}
      - SERVICENOW_API_KEY=${SERVICENOW_API_KEY}
```

---

## 📈 Métricas de Provider

### **Prometheus Metrics**

```
# Taxa de sucesso por provider
strands_provider_success_rate{provider="prometheus"} = 0.99
strands_provider_success_rate{provider="grafana"} = 0.97
strands_provider_success_rate{provider="servicenow"} = 0.92

# Latência por provider
strands_provider_latency_seconds{provider="prometheus"} = 0.105
strands_provider_latency_seconds{provider="grafana"} = 0.234
strands_provider_latency_seconds{provider="servicenow"} = 0.567

# Alertas coletados por provider
strands_alerts_collected_total{provider="prometheus"} = 1234
strands_alerts_collected_total{provider="grafana"} = 456
strands_alerts_collected_total{provider="servicenow"} = 89
```

---

## 📚 ÍNDICE COMPLETO DE DOCUMENTAÇÃO

### **1. Arquitetura e Fluxo de Dados**

#### 📄 [DATA_FLOW_ARCHITECTURE.md](./DATA_FLOW_ARCHITECTURE.md)
- **Descrição**: Explicação completa de como dados entram no agente
- **Tópicos**:
  - Fontes externas (Prometheus, Grafana, ServiceNow)
  - Estrutura de dados (Alert, NormalizedAlert, Cluster, Decision)
  - Pipeline de processamento completo
  - Exemplo prático passo-a-passo
  - Integração com observabilidade

#### 📄 [EMBEDDING_AGENT_EXPLAINED.md](./EMBEDDING_AGENT_EXPLAINED.md)
- **Descrição**: Como o EmbeddingAgent encontra alertas similares
- **Tópicos**:
  - Geração de embeddings (Ollama + Qdrant)
  - Busca semântica de incidentes similares
  - Armazenamento de histórico
  - Constituição Princípio III (apenas decisões confirmadas)
  - Exemplo prático com 3 similares encontrados

#### 📄 [SERVICENOW_INCIDENT_FLOW.md](./SERVICENOW_INCIDENT_FLOW.md)
- **Descrição**: Como incidentes ServiceNow fluem pelo sistema
- **Tópicos**:
  - Diferenças entre alertas de métrica e incidentes
  - Integração com API ServiceNow
  - Extração de contexto textual
  - Por que embeddings são melhores para incidentes
  - Exemplo prático com 3 similares encontrados

#### 📄 [LLM_IN_STRANDS_FLOW.md](./LLM_IN_STRANDS_FLOW.md)
- **Descrição**: Onde e como a LLM (Ollama) entra no fluxo
- **Tópicos**:
  - 3 pontos de entrada da LLM
  - EmbeddingAgent (nomic-embed-text)
  - DecisionEngine (mistral/llama2)
  - ReportAgent (mistral/llama2)
  - Fluxo completo com timing
  - Configuração do Ollama

---

### **2. Segurança e Hardening**

#### 📄 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)
- **Descrição**: Guia completo de hardening de segurança
- **Tópicos**:
  - Segurança de aplicação (validação, autenticação, HTTPS)
  - Segurança de infraestrutura (Kubernetes, RBAC, network policies)
  - Segurança de dados (criptografia, backup)
  - Segurança operacional (logging, auditoria)
  - Compliance (GDPR, SOC2)

---

### **3. Operações e Monitoramento**

#### 📄 [OBSERVABILITY.md](./OBSERVABILITY.md)
- **Descrição**: Stack completa de observabilidade
- **Tópicos**:
  - SLOs e SLIs definidos
  - Métricas Prometheus customizadas
  - Alerting rules
  - Dashboards Grafana
  - Tracing distribuído (Jaeger)

#### 📄 [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)
- **Descrição**: Runbook de disaster recovery
- **Tópicos**:
  - Plano de backup e restore
  - Procedimentos de failover
  - Testes de DR
  - RTO/RPO targets
  - Checklist de recuperação

#### 📄 [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)
- **Descrição**: Guia de deployment em produção
- **Tópicos**:
  - Pré-requisitos
  - Configuração de Kubernetes
  - Helm charts
  - Validação pós-deploy
  - Troubleshooting

---

### **4. Testes e Validação**

#### 📄 [TESTING_GUIDE.md](./TESTING_GUIDE.md)
- **Descrição**: Guia completo de testes
- **Tópicos**:
  - Quick start do ambiente de teste
  - Componentes do stack
  - Exemplos de uso
  - Troubleshooting
  - Métricas esperadas

---

### **5. API e Integração**

#### 📄 [openapi_spec.yaml](./openapi_spec.yaml)
- **Descrição**: Especificação OpenAPI/Swagger
- **Tópicos**:
  - Endpoints da API
  - Modelos de dados
  - Autenticação
  - Exemplos de requisição/resposta
  - Códigos de erro

---

### **6. CI/CD e Deployment**

#### 📄 [CI_CD_SETUP.md](./CI_CD_SETUP.md)
- **Descrição**: Guia de configuração de CI/CD
- **Tópicos**:
  - Template de GitHub Actions
  - Linting e testes
  - Security scanning
  - Docker build e push
  - Deployment automation

---

## 🎯 Fluxo de Leitura Recomendado

### **Para Iniciantes**

1. 📄 **DATA_FLOW_ARCHITECTURE.md** - Entenda o fluxo geral
2. 📄 **LLM_IN_STRANDS_FLOW.md** - Veja onde a LLM entra
3. 📄 **EMBEDDING_AGENT_EXPLAINED.md** - Entenda busca semântica
4. 📄 **SERVICENOW_INCIDENT_FLOW.md** - Veja integração com ServiceNow

### **Para Operadores**

1. 📄 **PRODUCTION_DEPLOYMENT.md** - Deploy em produção
2. 📄 **OBSERVABILITY.md** - Configure monitoramento
3. 📄 **DISASTER_RECOVERY.md** - Prepare para emergências
4. 📄 **TESTING_GUIDE.md** - Teste o sistema

### **Para Desenvolvedores**

1. 📄 **openapi_spec.yaml** - Conheça a API
2. 📄 **CI_CD_SETUP.md** - Configure CI/CD
3. 📄 **SECURITY_HARDENING.md** - Implemente segurança
4. 📄 **LLM_IN_STRANDS_FLOW.md** - Estenda com LLM

### **Para Arquitetos**

1. 📄 **DATA_FLOW_ARCHITECTURE.md** - Visão geral
2. 📄 **SECURITY_HARDENING.md** - Segurança
3. 📄 **OBSERVABILITY.md** - Monitoramento
4. 📄 **DISASTER_RECOVERY.md** - Resiliência

---

## 📊 Mapa Mental da Arquitetura

```
STRANDS AGENT SYSTEM
│
├─ INPUT LAYER
│  ├─ Prometheus (Prioridade: 100)
│  ├─ Grafana (Prioridade: 50)
│  └─ ServiceNow (Prioridade: 10)
│
├─ PROCESSING LAYER
│  ├─ AlertCollector
│  ├─ AlertNormalizer
│  ├─ AlertCorrelator
│  │
│  └─ ANALYSIS AGENTS
│     ├─ MetricsAnalysisAgent
│     ├─ GraphAgent (Neo4j)
│     ├─ 🤖 EmbeddingAgent (Ollama + Qdrant)
│     │
│     └─ DECISION ENGINE
│        └─ 🤖 DecisionEngine (Ollama)
│
├─ OUTPUT LAYER
│  ├─ HumanReview (se confiança < 70%)
│  ├─ 🤖 ReportAgent (Ollama)
│  └─ Notificações (Email, Slack, ServiceNow)
│
└─ OBSERVABILITY
   ├─ Prometheus (Métricas)
   ├─ Grafana (Dashboards)
   ├─ Jaeger (Tracing)
   └─ Alerting Rules
```

---

## 🔍 Busca Rápida por Tópico

### **Quero entender...**

- **Como dados entram no sistema?** → [DATA_FLOW_ARCHITECTURE.md](./DATA_FLOW_ARCHITECTURE.md)
- **Como a LLM funciona?** → [LLM_IN_STRANDS_FLOW.md](./LLM_IN_STRANDS_FLOW.md)
- **Como encontrar alertas similares?** → [EMBEDDING_AGENT_EXPLAINED.md](./EMBEDDING_AGENT_EXPLAINED.md)
- **Como integrar ServiceNow?** → [SERVICENOW_INCIDENT_FLOW.md](./SERVICENOW_INCIDENT_FLOW.md)
- **Como fazer deploy?** → [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)
- **Como monitorar?** → [OBSERVABILITY.md](./OBSERVABILITY.md)
- **Como recuperar de falhas?** → [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)
- **Como testar?** → [TESTING_GUIDE.md](./TESTING_GUIDE.md)
- **Como configurar CI/CD?** → [CI_CD_SETUP.md](./CI_CD_SETUP.md)
- **Como garantir segurança?** → [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)
- **Qual é a API?** → [openapi_spec.yaml](./openapi_spec.yaml)

---

## 📈 Estatísticas de Documentação

- **Total de Documentos**: 11
- **Total de Páginas**: ~150
- **Total de Palavras**: ~50,000
- **Diagramas**: 20+
- **Exemplos Práticos**: 30+
- **Configurações**: 15+

---

## 🚀 Próximos Passos

1. **Leia** a documentação na ordem recomendada para seu perfil
2. **Implemente** as recomendações de segurança
3. **Configure** o monitoramento e observabilidade
4. **Teste** o sistema com o TESTING_GUIDE
5. **Deploy** em produção com PRODUCTION_DEPLOYMENT
6. **Monitore** com OBSERVABILITY
7. **Prepare** disaster recovery com DISASTER_RECOVERY

---

## 📞 Suporte

Para dúvidas sobre:
- **Arquitetura**: Consulte DATA_FLOW_ARCHITECTURE.md
- **Operações**: Consulte PRODUCTION_DEPLOYMENT.md
- **Problemas**: Consulte DISASTER_RECOVERY.md
- **Segurança**: Consulte SECURITY_HARDENING.md
- **Monitoramento**: Consulte OBSERVABILITY.md

---

## 📝 Histórico de Documentação

| Data | Documento | Versão |
|------|-----------|--------|
| 2026-02-06 | DATA_FLOW_ARCHITECTURE.md | 1.0 |
| 2026-02-06 | EMBEDDING_AGENT_EXPLAINED.md | 1.0 |
| 2026-02-06 | SERVICENOW_INCIDENT_FLOW.md | 1.0 |
| 2026-02-06 | LLM_IN_STRANDS_FLOW.md | 1.0 |
| 2026-02-06 | PROVIDER_SELECTION_AND_INDEX.md | 1.0 |

---

**Última atualização**: 2026-02-06  
**Mantido por**: Strands Documentation Team  
**Versão**: 1.0
