# 🎫 Fluxo de Incidentes ServiceNow com EmbeddingAgent

## 📚 Visão Geral

Diferente de **alertas de métrica** (que são numéricos e estruturados), os **incidentes ServiceNow** são **textuais e menos estruturados**. O EmbeddingAgent funciona MELHOR com incidentes porque pode capturar a semântica completa da descrição.

```
ALERTA DE MÉTRICA          vs          INCIDENTE SERVICENOW
─────────────────────────────────────────────────────────────
"Error rate > 5%"                      "Database connection timeout
(Estruturado)                          causing checkout failures
                                       for 30 minutes. Customers
                                       unable to complete orders."
                                       (Textual, rico em contexto)

Embedding: Simples                     Embedding: Muito mais rico
Semântica: Limitada                    Semântica: Completa
```

---

## 🔄 Fluxo Completo - ServiceNow Incidente

### **Passo 1: Incidente Chega do ServiceNow**

```python
# Incidente criado manualmente por um usuário
incident = {
    "number": "INC0123456",
    "short_description": "Database connection timeout",
    "description": """
    Customers are unable to complete checkout transactions.
    Error message: "Connection timeout to payment database".
    
    Affected services:
    - checkout-service
    - payment-api
    - order-processor
    
    Impact: ~500 customers affected, revenue loss ~$5k/min
    
    Recent changes:
    - Database pool size reduced from 100 to 50 connections
    - New payment validation rules deployed 2 hours ago
    
    Symptoms:
    - 95% of checkout requests failing
    - Database CPU at 85%
    - Connection pool exhausted
    """,
    "severity": "1",  # Critical
    "state": "1",  # New
    "assigned_to": None,
    "created_at": "2026-02-06T12:00:00Z",
    "created_by": "user@company.com",
    "tags": ["database", "payment", "critical"]
}
```

### **Passo 2: AlertCollector Busca no ServiceNow**

```python
# AlertCollectorAgent agora suporta ServiceNow
class AlertCollectorAgent:
    def collect_active_alerts(self) -> List[Alert]:
        # Tenta Prometheus primeiro
        if prometheus_available:
            return self._collect_from_prometheus()
        
        # Tenta Grafana
        if grafana_available:
            return self._collect_from_grafana()
        
        # NEW: Tenta ServiceNow
        if servicenow_available:
            return self._collect_from_servicenow()
    
    def _collect_from_servicenow(self) -> List[Alert]:
        """Coleta incidentes abertos do ServiceNow"""
        
        # Query ServiceNow API
        response = requests.get(
            "https://company.service-now.com/api/now/table/incident",
            params={
                "sysparm_query": "stateIN1,2",  # New, In Progress
                "sysparm_limit": 100
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        incidents = response.json()["result"]
        alerts = []
        
        for incident in incidents:
            # Converte incidente ServiceNow para Alert
            alert = Alert(
                timestamp=datetime.fromisoformat(incident["created"]),
                fingerprint=incident["number"],  # INC0123456
                service=self._extract_service(incident),
                severity=self._map_severity(incident["severity"]),
                description=incident["short_description"],
                source=AlertSource.SERVICENOW,
                labels={
                    "incident_number": incident["number"],
                    "assigned_to": incident["assigned_to"],
                    "impact": incident["impact"],
                    "urgency": incident["urgency"],
                    "tags": incident["tags"]
                },
                annotations={
                    "full_description": incident["description"],
                    "created_by": incident["created_by"],
                    "company": incident["company"]
                }
            )
            alerts.append(alert)
        
        return alerts
```

### **Passo 3: AlertNormalizer Padroniza**

```python
# O normalizer agora lida com incidentes textuais
class AlertNormalizerAgent:
    def normalize(self, alerts: List[Alert]) -> List[NormalizedAlert]:
        normalized = []
        
        for alert in alerts:
            # Para incidentes ServiceNow, extrai mais contexto
            if alert.source == AlertSource.SERVICENOW:
                
                # Extrai serviços mencionados na descrição
                services = self._extract_services_from_text(
                    alert.annotations.get("full_description", "")
                )
                
                # Extrai impacto
                impact = self._extract_impact(
                    alert.labels.get("impact", ""),
                    alert.annotations.get("full_description", "")
                )
                
                # Normaliza severidade
                severity = self._normalize_severity(
                    alert.labels.get("urgency", ""),
                    alert.labels.get("impact", "")
                )
                
                norm_alert = NormalizedAlert(
                    timestamp=alert.timestamp,
                    fingerprint=alert.fingerprint,
                    service=services[0] if services else "unknown",
                    severity=severity,
                    description=alert.description,
                    labels={
                        **alert.labels,
                        "affected_services": services,
                        "impact_level": impact,
                        "source_system": "servicenow"
                    },
                    validation_status=ValidationStatus.VALID
                )
                normalized.append(norm_alert)
        
        return normalized
    
    def _extract_services_from_text(self, text: str) -> List[str]:
        """Extrai nomes de serviços da descrição textual"""
        # Usa regex ou NLP para encontrar serviços mencionados
        services = []
        
        service_patterns = {
            "checkout": r"checkout[-_]?service|checkout\s+system",
            "payment": r"payment[-_]?api|payment\s+service",
            "order": r"order[-_]?processor|order\s+service",
            "database": r"database|db\s+server",
        }
        
        for service, pattern in service_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                services.append(service)
        
        return services
    
    def _extract_impact(self, impact_field: str, description: str) -> str:
        """Extrai nível de impacto"""
        # Mapeia campo de impacto ServiceNow
        impact_map = {
            "1": "critical",
            "2": "high",
            "3": "medium",
            "4": "low"
        }
        
        # Se não tiver, tenta extrair da descrição
        if impact_field in impact_map:
            return impact_map[impact_field]
        
        # Busca por palavras-chave
        if any(word in description.lower() for word in 
               ["500 customers", "revenue loss", "all users", "production down"]):
            return "critical"
        
        return "medium"
```

### **Passo 4: AlertCorrelator Agrupa**

```python
# Agrupa incidentes relacionados
class AlertCorrelationAgent:
    def correlate(self, alerts: List[NormalizedAlert]) -> List[AlertCluster]:
        clusters = {}
        
        for alert in alerts:
            # Para incidentes ServiceNow, agrupa por serviços afetados
            if alert.labels.get("source_system") == "servicenow":
                
                # Chave: lista de serviços afetados
                affected_services = tuple(sorted(
                    alert.labels.get("affected_services", ["unknown"])
                ))
                key = f"servicenow_{affected_services}"
                
                if key not in clusters:
                    clusters[key] = AlertCluster(
                        cluster_id=uuid4(),
                        service=affected_services[0],
                        cluster_type="INCIDENT_CORRELATION",
                        alerts=[alert]
                    )
                else:
                    clusters[key].alerts.append(alert)
            else:
                # Lógica normal para alertas de métrica
                key = alert.service
                if key not in clusters:
                    clusters[key] = AlertCluster(...)
                else:
                    clusters[key].alerts.append(alert)
        
        return list(clusters.values())
```

### **Passo 5: EmbeddingAgent - Busca Semântica**

Aqui é onde o embedding brilha para incidentes ServiceNow!

```python
# EmbeddingAgent agora recebe o cluster com incidente
async def analyze_embedding(cluster: AlertCluster) -> SimilarityResult:
    """
    Para incidentes ServiceNow, o embedding é MUITO mais poderoso
    porque captura a semântica completa da descrição textual.
    """
    
    # Constrói texto rico para embedding
    embedding_text = f"""
    {cluster.description}
    
    Affected services: {', '.join(cluster.labels.get('affected_services', []))}
    Impact: {cluster.labels.get('impact_level', 'unknown')}
    Severity: {cluster.severity}
    
    Full context:
    {cluster.annotations.get('full_description', '')}
    """
    
    # Exemplo real
    embedding_text = """
    Database connection timeout
    
    Customers are unable to complete checkout transactions.
    Error message: "Connection timeout to payment database".
    
    Affected services: checkout-service, payment-api, order-processor
    Impact: critical
    Severity: critical
    
    Full context:
    Customers are unable to complete checkout transactions.
    Error message: "Connection timeout to payment database".
    
    Affected services:
    - checkout-service
    - payment-api
    - order-processor
    
    Impact: ~500 customers affected, revenue loss ~$5k/min
    
    Recent changes:
    - Database pool size reduced from 100 to 50 connections
    - New payment validation rules deployed 2 hours ago
    
    Symptoms:
    - 95% of checkout requests failing
    - Database CPU at 85%
    - Connection pool exhausted
    """
    
    # Gera embedding via Ollama
    embedding_vector = await ollama.embed(embedding_text)
    # [0.156, -0.432, 0.789, ..., 0.234]  (384 dims)
    
    # Busca similares no Qdrant
    similar_results = await qdrant.search(
        collection="incident_decisions",
        vector=embedding_vector,
        top_k=5,
        score_threshold=0.75
    )
    
    return SimilarityResult(
        similar_alerts=similar_results,
        confidence=0.92
    )
```

---

## 🎯 Exemplo Prático - Incidente ServiceNow

### **Cenário: Novo Incidente de Timeout de Banco de Dados**

```
TEMPO: 2026-02-06 12:00:00

1. INCIDENTE CRIADO NO SERVICENOW
   ├─ Número: INC0123456
   ├─ Título: "Database connection timeout"
   ├─ Descrição: "Customers unable to checkout... 500 affected..."
   ├─ Severidade: Critical
   └─ Serviços: checkout, payment, order-processor

2. ALERT COLLECTOR BUSCA SERVICENOW
   └─ Query: GET /api/now/table/incident?state=1,2
   └─ Retorna: Incidente como Alert

3. ALERT NORMALIZER PADRONIZA
   ├─ Extrai serviços: [checkout-service, payment-api, order-processor]
   ├─ Extrai impacto: "critical" (500 customers, $5k/min loss)
   ├─ Normaliza severidade: "critical"
   └─ Retorna: NormalizedAlert

4. ALERT CORRELATOR AGRUPA
   └─ Agrupa por serviços afetados
   └─ Cria cluster: "servicenow_checkout-service_payment-api_order-processor"

5. EMBEDDING AGENT - BUSCA SEMÂNTICA ← AQUI É DIFERENTE!
   
   Texto para Embedding:
   ┌─────────────────────────────────────────────────────────┐
   │ "Database connection timeout                            │
   │                                                          │
   │ Customers are unable to complete checkout transactions. │
   │ Error message: Connection timeout to payment database.  │
   │                                                          │
   │ Affected services: checkout-service, payment-api,       │
   │                    order-processor                       │
   │ Impact: critical                                         │
   │ Severity: critical                                       │
   │                                                          │
   │ Full context:                                            │
   │ ...500 customers affected, revenue loss ~$5k/min...     │
   │ ...Database pool size reduced from 100 to 50...         │
   │ ...New payment validation rules deployed 2 hours ago... │
   │ ...95% of checkout requests failing...                  │
   │ ...Database CPU at 85%...                               │
   │ ...Connection pool exhausted..."                         │
   └─────────────────────────────────────────────────────────┘
   
   Ollama Embedding:
   └─ [0.156, -0.432, 0.789, ..., 0.234]  (384 dims)
   
   Qdrant Search:
   └─ Busca similares em "incident_decisions"
   
   RESULTADOS ENCONTRADOS:
   
   ✓ Resultado 1 (Similaridade: 0.96)
   ├─ Incidente Histórico: "Database pool exhaustion"
   ├─ Data: 2026-01-28 09:15:00 (1 semana atrás)
   ├─ Descrição: "Payment database connection pool exhausted
   │             causing checkout failures. Pool size was
   │             reduced during maintenance."
   ├─ Resolução: "INCREASE_POOL_SIZE + ROLLBACK_RECENT_CHANGES"
   ├─ Tempo de Resolução: 15 minutos
   └─ Confiança: 0.94
   
   ✓ Resultado 2 (Similaridade: 0.88)
   ├─ Incidente Histórico: "Checkout service timeout"
   ├─ Data: 2026-01-15 14:30:00 (3 semanas atrás)
   ├─ Descrição: "Checkout service unable to connect to
   │             payment database. Timeout errors for all
   │             transactions."
   ├─ Resolução: "RESTART_PAYMENT_API + INCREASE_TIMEOUT"
   ├─ Tempo de Resolução: 8 minutos
   └─ Confiança: 0.87
   
   ✓ Resultado 3 (Similaridade: 0.82)
   ├─ Incidente Histórico: "Order processor database timeout"
   ├─ Data: 2026-01-05 11:00:00 (1 mês atrás)
   ├─ Descrição: "Order processor unable to write to database.
   │             Connection timeout errors."
   ├─ Resolução: "SCALE_DATABASE_REPLICAS"
   ├─ Tempo de Resolução: 25 minutos
   └─ Confiança: 0.81

6. DECISION ENGINE UTILIZA RESULTADOS
   ├─ "Encontrei 3 incidentes similares!"
   ├─ "O mais similar (96%) foi resolvido com:"
   │  └─ "INCREASE_POOL_SIZE + ROLLBACK_RECENT_CHANGES"
   ├─ "Tempo de resolução anterior: 15 minutos"
   └─ "Vou recomendar a mesma ação"

7. DECISÃO FINAL
   ├─ Action: "INCREASE_POOL_SIZE + ROLLBACK_RECENT_CHANGES"
   ├─ Confidence: 0.96
   ├─ Reasoning: "96% similar to incident INC0112345 from
   │             1 week ago. Same symptoms: pool exhaustion
   │             after pool size reduction. Same resolution
   │             worked in 15 minutes."
   ├─ Estimated Resolution Time: 15 minutes
   └─ Risk Level: LOW

8. HUMAN REVIEW (se necessário)
   ├─ Se confiança < 70%: Encaminha para analista
   ├─ Se confiança > 70%: Aprova automaticamente
   └─ Neste caso: Confiança = 0.96 → APROVA

9. EXECUÇÃO
   ├─ Aumenta pool de conexões de 50 para 100
   ├─ Faz rollback das mudanças de validação
   ├─ Monitora taxa de sucesso de checkout
   ├─ Atualiza incidente no ServiceNow
   └─ Registra resolução no histórico

10. PERSISTÊNCIA DO EMBEDDING
    └─ Após confirmação, armazena em Qdrant:
       {
           "vector": [0.156, -0.432, 0.789, ..., 0.234],
           "payload": {
               "source_decision_id": "dec-999",
               "source_text": "Database connection timeout...",
               "service": "payment-api",
               "severity": "critical",
               "rules_applied": ["PoolExhaustion", "DatabaseTimeout"],
               "resolution_action": "INCREASE_POOL_SIZE",
               "resolution_time_minutes": 12,
               "human_validator": "analyst-john",
               "created_at": "2026-02-06T12:15:00Z"
           }
       }
```

---

## 🔍 Por Que Embeddings São Melhores para Incidentes

### **Alertas de Métrica**
```
Entrada: "Error rate > 5%"
         ↓
Embedding: Simples
         ↓
Busca: "Procura por 'error rate'" (palavra-chave)
         ↓
Problema: Perde contexto semântico
```

### **Incidentes ServiceNow**
```
Entrada: "Database connection timeout causing checkout failures.
          500 customers affected, revenue loss $5k/min.
          Recent changes: pool size reduced, new validation rules."
         ↓
Embedding: Captura TODA a semântica
         ↓
Busca: Encontra incidentes com MESMA SEMÂNTICA
       (mesmo que use palavras diferentes)
         ↓
Vantagem: Captura contexto completo, causa-raiz, impacto
```

### **Exemplo de Semântica Capturada**

```
Incidente 1: "Database connection pool exhausted"
Incidente 2: "Too many connections to payment database"
Incidente 3: "Connection limit reached on DB server"

Sem Embedding:
└─ Nenhuma correspondência (palavras diferentes)

Com Embedding:
└─ Todos reconhecidos como SIMILARES (mesma semântica)
```

---

## 📊 Diferenças: Métrica vs. Incidente

| Aspecto | Alerta de Métrica | Incidente ServiceNow |
|---------|-------------------|----------------------|
| **Fonte** | Prometheus/Grafana | ServiceNow (manual) |
| **Estrutura** | Numérica | Textual |
| **Contexto** | Limitado | Rico |
| **Embedding** | Simples | Complexo |
| **Busca** | Palavra-chave | Semântica |
| **Precisão** | Média | Alta |
| **Reutilização** | Boa | Excelente |

---

## 🔗 Integração com ServiceNow

### **Configuração**

```python
# .env
SERVICENOW_URL=https://company.service-now.com
SERVICENOW_API_KEY=xxx
SERVICENOW_TABLE=incident
SERVICENOW_QUERY=stateIN1,2  # New, In Progress

# Mapeamento de severidade
SERVICENOW_SEVERITY_MAP={
    "1": "critical",
    "2": "high",
    "3": "medium",
    "4": "low"
}
```

### **Fluxo de Atualização**

```python
# Após decisão, atualiza incidente no ServiceNow
class ServiceNowUpdater:
    def update_incident(self, incident_id: str, decision: Decision):
        """Atualiza incidente com decisão"""
        
        update_data = {
            "state": "2",  # In Progress
            "assigned_to": "strands-automation",
            "work_notes": f"""
            Strands Decision Engine Analysis:
            
            Recommended Action: {decision.action}
            Confidence: {decision.confidence * 100:.1f}%
            
            Similar Incidents Found: 3
            - Most similar (96%): INC0112345
              Resolution: {decision.action}
              Time to resolve: 15 minutes
            
            Reasoning: {decision.reasoning}
            """,
            "u_strands_decision_id": str(decision.decision_id),
            "u_strands_confidence": decision.confidence
        }
        
        # PATCH /api/now/table/incident/INC0123456
        response = requests.patch(
            f"{SERVICENOW_URL}/api/now/table/incident/{incident_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        return response.json()
```

---

## 💾 Armazenamento em Qdrant

### **Collection: incident_decisions**

```python
# Estrutura de um ponto armazenado
{
    "id": "vec-incident-001",
    "vector": [0.156, -0.432, 0.789, ..., 0.234],  # 384 dims
    "payload": {
        "source_decision_id": "dec-999",
        "source_incident_id": "INC0123456",
        "source_text": "Database connection timeout causing...",
        
        # Contexto
        "service": "payment-api",
        "severity": "critical",
        "affected_services": ["checkout-service", "payment-api", "order-processor"],
        "impact_level": "critical",
        
        # Resolução
        "resolution_action": "INCREASE_POOL_SIZE",
        "resolution_steps": ["Increase pool from 50 to 100", "Rollback validation rules"],
        "resolution_time_minutes": 12,
        
        # Rastreabilidade
        "human_validator": "analyst-john",
        "created_at": "2026-02-06T12:15:00Z",
        "source_system": "servicenow"
    }
}
```

---

## 🚀 Fluxo Resumido - ServiceNow vs. Métrica

### **Alerta de Métrica**
```
Prometheus Alert
    ↓
AlertCollector (query /api/v1/alerts)
    ↓
AlertNormalizer (valida numéricos)
    ↓
AlertCorrelator (agrupa por serviço)
    ↓
MetricsAnalysis (analisa tendência)
    ↓
EmbeddingAgent (busca similares)
    ↓
Decision (ação)
```

### **Incidente ServiceNow**
```
ServiceNow Incident (manual)
    ↓
AlertCollector (query /api/now/table/incident)
    ↓
AlertNormalizer (extrai contexto textual)
    ↓
AlertCorrelator (agrupa por serviços afetados)
    ↓
GraphAnalysis (busca dependências)
    ↓
EmbeddingAgent (busca similares com SEMÂNTICA RICA)
    ↓
Decision (ação baseada em histórico similar)
```

---

## 📈 Vantagens do Embedding para Incidentes

1. **Semântica Completa**: Captura contexto, causa-raiz, impacto
2. **Flexibilidade**: Funciona com qualquer descrição textual
3. **Reutilização**: Encontra resoluções anteriores similares
4. **Aprendizado**: Quanto mais incidentes, melhor a busca
5. **Redução de MTTR**: Reutiliza resoluções conhecidas
6. **Qualidade**: Decisões baseadas em histórico validado

---

## 🎯 Resumo

**Incidentes ServiceNow são IDEAIS para EmbeddingAgent porque:**

- ✅ Texto rico em contexto
- ✅ Semântica capturável por LLM
- ✅ Histórico de resoluções reutilizável
- ✅ Busca semântica muito mais eficaz
- ✅ Reduz tempo de resolução (MTTR)
- ✅ Melhora qualidade das decisões

O embedding funciona transformando a descrição textual completa em um vetor semântico, permitindo encontrar incidentes similares mesmo com palavras diferentes, mas mesma semântica!
