# 🏗️ Arquitetura de Agentes do Strands - Guia Completo

## Visão Geral

A arquitetura de agentes do Strands foi projetada seguindo **princípios SOLID** e padrões de design inspirados em Java, garantindo tipagem forte, contratos claros e extensibilidade.

## 📋 Componentes Principais

### 1. **BaseAgent** - Contrato Abstrato

O `BaseAgent` é uma classe abstrata que define o contrato obrigatório para todos os agentes.

**Localização**: `src/agents/base_agent.py`

**Responsabilidades**:
- Definir interface padrão para todos os agentes
- Garantir implementação de métodos obrigatórios
- Fornecer funcionalidades comuns (logging, métricas, registro)
- Gerenciar ciclo de vida do agente

**Métodos Obrigatórios**:

| Método | Responsabilidade | Retorno |
|--------|------------------|---------|
| `execute()` | Executar análise completa | `AgentOutput` |
| `collect_data()` | Coletar dados da fonte | Dados brutos |
| `analyze()` | Analisar dados coletados | Resultado da análise |
| `validate_output()` | Validar saída | `bool` |
| `generate_evidence()` | Gerar evidências | `List[Evidence]` |

**Exemplo de Implementação**:

```python
class MyAgent(BaseAgent):
    async def execute(self, input_data: Dict) -> AgentOutput:
        try:
            # 1. Coletar dados
            data = await self.collect_data(input_data)
            
            # 2. Analisar
            result = self.analyze(data)
            
            # 3. Validar
            self.validate_output(result)
            
            # 4. Gerar evidências
            evidence = await self.generate_evidence(data, result)
            
            # 5. Registrar evidências (automático)
            await self.register_evidence(evidence, input_data.get("context_id"))
            
            # 6. Retornar saída padronizada
            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                result=result,
                confidence=0.95,
                evidence=evidence,
            )
        except Exception as e:
            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.name,
                status=AgentStatus.FAILED,
                result=None,
                confidence=0.0,
                error_message=str(e),
            )
```

### 2. **ConfidenceService** - Cálculo Inteligente de Confiança

O `ConfidenceService` implementa múltiplas estratégias de cálculo de confiança.

**Localização**: `src/services/confidence_service.py`

**Estratégias Disponíveis**:

| Estratégia | Descrição | Caso de Uso |
|-----------|-----------|-----------|
| **EVIDENCE_BASED** | Baseado na qualidade de evidências | Quando há múltiplas evidências |
| **CONSENSUS_BASED** | Baseado em consenso entre agentes | Quando múltiplos agentes analisam |
| **HISTORICAL** | Baseado em acurácia histórica | Para agentes com histórico |
| **CROSS_VALIDATION** | Validação cruzada com outros agentes | Para validação mútua |
| **ENSEMBLE** | Combina todas as estratégias | Recomendado para produção |

**Exemplo de Uso**:

```python
from src.services.confidence_service import ConfidenceService, ConfidenceStrategy

service = ConfidenceService()

# Calcular confiança com ensemble (recomendado)
confidence_score = service.calculate(
    output=agent_output,
    strategy=ConfidenceStrategy.ENSEMBLE,
    other_outputs=[other_agent_output1, other_agent_output2]
)

print(f"Score: {confidence_score.final_score:.1%}")
print(f"Explicação: {confidence_score.explanation}")
```

**Fatores de Cálculo**:

1. **Evidence Quality** (40%)
   - Número de evidências
   - Confiança média
   - Diversidade de fontes
   - Recência

2. **Consensus Level** (30%)
   - Concordância entre agentes
   - Força do consenso

3. **Historical Accuracy** (30%)
   - Acurácia passada do agente
   - Tendência histórica

### 3. **DecisionController** - Orquestração de Decisões

O `DecisionController` toma decisões baseadas nos outputs de múltiplos agentes.

**Localização**: `src/controllers/decision_controller.py`

**Responsabilidades**:
- Coletar outputs de múltiplos agentes
- Calcular confiança geral
- Aplicar políticas de decisão
- Gerar decisão final
- Determinar se requer revisão humana

**Tipos de Decisão**:

| Tipo | Descrição | Ação |
|------|-----------|------|
| **APPROVE** | Aprovar ação | Prosseguir |
| **REJECT** | Rejeitar ação | Bloquear |
| **ESCALATE** | Escalar para humano | Notificar |
| **INVESTIGATE** | Investigar mais | Coletar mais dados |
| **MONITOR** | Monitorar | Reavaliar em 5min |
| **REMEDIATE** | Remediar | Executar ação corretiva |

**Políticas de Decisão**:

```python
# Política Estrita (requer 90% confiança e 95% consenso)
policy = DecisionPolicy("strict", confidence_threshold=0.9, consensus_threshold=0.95)

# Política Balanceada (requer 70% confiança e 80% consenso)
policy = DecisionPolicy("balanced", confidence_threshold=0.7, consensus_threshold=0.8)

# Política Permissiva (requer 50% confiança e 60% consenso)
policy = DecisionPolicy("permissive", confidence_threshold=0.5, consensus_threshold=0.6)
```

**Exemplo de Uso**:

```python
from src.controllers.decision_controller import DecisionController

controller = DecisionController()

# Tomar decisão
decision = controller.make_decision(
    outputs=[agent1_output, agent2_output, agent3_output],
    policy_name="balanced",
    context={"alert_id": "alert_123"}
)

# Explicar decisão
explanation = controller.explain_decision(decision)
print(explanation)

# Validar decisão
is_valid, errors = controller.validate_decision(decision)
if not is_valid:
    print(f"Erros: {errors}")
```

### 4. **ReplayEngine** - Análise Histórica e Viagem no Tempo

O `ReplayEngine` permite reinjetar eventos históricos para validação, treinamento e simulação.

**Localização**: `src/engines/replay_engine.py`

**Modos de Replay**:

| Modo | Objetivo | Uso |
|------|----------|-----|
| **VALIDATION** | Validar decisões passadas | Auditoria de decisões |
| **TRAINING** | Treinar agentes com histórico | Melhorar acurácia |
| **SIMULATION** | Simular cenários "e se" | Planejamento |
| **AUDIT** | Auditoria completa | Compliance |

**Exemplo de Uso**:

```python
from src.engines.replay_engine import ReplayEngine, ReplayMode, ReplayEvent
from datetime import datetime, timedelta

engine = ReplayEngine()

# Recuperar eventos históricos
start_time = datetime.utcnow() - timedelta(days=7)
end_time = datetime.utcnow()
events = engine.get_events_by_time_range(start_time, end_time)

# Criar sessão de replay
session = engine.create_session(ReplayMode.VALIDATION, events)

# Executar replay
results = await engine.execute_replay(session)

# Analisar resultados
print(f"Eventos replicados: {results['replayed_events']}")
print(f"Decisões correspondentes: {results['matching_decisions']}")
print(f"Decisões divergentes: {results['diverging_decisions']}")
```

## 🏛️ Padrões de Design Utilizados

### 1. **Abstract Factory Pattern** (BaseAgent)

Define interface abstrata para criação de agentes, permitindo subclasses implementarem suas próprias estratégias.

```python
class BaseAgent(ABC):
    @abstractmethod
    async def execute(self, input_data: Dict) -> AgentOutput:
        pass
```

### 2. **Strategy Pattern** (ConfidenceService)

Encapsula diferentes estratégias de cálculo de confiança, permitindo seleção em tempo de execução.

```python
confidence_score = service.calculate(
    output=output,
    strategy=ConfidenceStrategy.ENSEMBLE
)
```

### 3. **Registry Pattern** (AgentRegistry)

Registro centralizado de agentes para descoberta e gerenciamento.

```python
AgentRegistry.register(my_agent)
agent = AgentRegistry.get("my_agent_name")
```

### 4. **Command Pattern** (ReplayEngine)

Encapsula eventos históricos como objetos para replay.

```python
session = engine.create_session(ReplayMode.VALIDATION, events)
await engine.execute_replay(session)
```

### 5. **Specification Pattern** (DecisionPolicy)

Define políticas de decisão como objetos reutilizáveis.

```python
policy = DecisionPolicy("strict", confidence_threshold=0.9)
is_satisfied, reason = policy.evaluate(outputs, confidence)
```

## 📊 Fluxo Completo de Execução

```
┌─────────────────────────────────────────────────────────────┐
│ 1. ENTRADA: Alerta/Incidente                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. MÚLTIPLOS AGENTES EXECUTAM EM PARALELO                   │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Agent 1      │  │ Agent 2      │  │ Agent 3      │       │
│  │ (Metrics)    │  │ (Logs)       │  │ (Threat)     │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           │                                 │
│                    ┌──────▼──────┐                          │
│                    │ AgentOutput  │                          │
│                    │ + Evidence   │                          │
│                    └──────┬───────┘                          │
└─────────────────────────────┼──────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. CALCULAR CONFIANÇA (ConfidenceService)                   │
│                                                               │
│  Evidence Quality + Consensus + Historical = Final Score    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. APLICAR POLÍTICAS (DecisionController)                   │
│                                                               │
│  Verificar: Confiança >= Threshold?                         │
│  Verificar: Consenso >= Threshold?                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. GERAR DECISÃO                                             │
│                                                               │
│  Tipo: APPROVE/REJECT/ESCALATE/...                          │
│  Requer Revisão Humana?                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. EXECUTAR AÇÃO                                             │
│                                                               │
│  - Criar ticket                                              │
│  - Notificar stakeholders                                    │
│  - Executar remediação                                       │
│  - Registrar audit log                                       │
└─────────────────────────────────────────────────────────────┘
```

## 🔒 Princípios SOLID Aplicados

### Single Responsibility Principle (SRP)

Cada classe tem uma única responsabilidade:
- **BaseAgent**: Define contrato para agentes
- **ConfidenceService**: Calcula confiança
- **DecisionController**: Toma decisões
- **ReplayEngine**: Gerencia replay de eventos

### Open/Closed Principle (OCP)

Classes abertas para extensão, fechadas para modificação:
- Novos agentes herdam de `BaseAgent`
- Novas estratégias de confiança implementam `ConfidenceStrategy`
- Novas políticas herdam de `DecisionPolicy`

### Liskov Substitution Principle (LSP)

Subclasses podem substituir a classe base:
```python
# Qualquer agente pode ser usado onde BaseAgent é esperado
def process_agent(agent: BaseAgent):
    output = await agent.execute(data)
```

### Interface Segregation Principle (ISP)

Interfaces específicas em vez de genéricas:
- `Evidence`: Contém apenas dados de evidência
- `AgentOutput`: Contém apenas saída de agente
- `Decision`: Contém apenas dados de decisão

### Dependency Inversion Principle (DIP)

Depender de abstrações, não de implementações:
```python
# Bom: Depender de BaseAgent
def orchestrate(agents: List[BaseAgent]):
    pass

# Ruim: Depender de implementações específicas
def orchestrate(agent1: MetricsAgent, agent2: LogsAgent):
    pass
```

## 📈 Métricas e Monitoramento

Cada agente fornece métricas de execução:

```python
metrics = agent.get_metrics()
# {
#     "agent_id": "...",
#     "agent_name": "...",
#     "execution_count": 100,
#     "error_count": 5,
#     "error_rate": 0.05,
#     "avg_execution_time_ms": 250.5,
#     "total_execution_time_ms": 25050.0
# }
```

## 🧪 Testes

### Teste de Agente Individual

```python
@pytest.mark.asyncio
async def test_agent_execution():
    agent = MyAgent("test_agent")
    output = await agent.execute({"data": "test"})
    
    assert output.status == AgentStatus.SUCCESS
    assert output.confidence >= 0.7
    assert len(output.evidence) > 0
```

### Teste de Confiança

```python
def test_confidence_calculation():
    service = ConfidenceService()
    score = service.calculate_evidence_based(agent_output)
    
    assert 0.0 <= score.final_score <= 1.0
    assert score.strategy == ConfidenceStrategy.EVIDENCE_BASED
```

### Teste de Decisão

```python
def test_decision_making():
    controller = DecisionController()
    decision = controller.make_decision(
        outputs=[output1, output2, output3],
        policy_name="balanced"
    )
    
    assert decision.decision_type in DecisionType
    assert 0.0 <= decision.confidence <= 1.0
```

## 📚 Extensão e Customização

### Criar Novo Agente

```python
from src.agents.base_agent import BaseAgent, AgentOutput, Evidence, EvidenceType

class CustomAgent(BaseAgent):
    async def execute(self, input_data: Dict) -> AgentOutput:
        # Implementar lógica
        pass
    
    async def collect_data(self, input_data: Dict) -> Any:
        # Coletar dados
        pass
    
    def analyze(self, data: Any) -> Any:
        # Analisar
        pass
    
    def validate_output(self, result: Any) -> bool:
        # Validar
        pass
    
    async def generate_evidence(self, data: Any, result: Any) -> List[Evidence]:
        # Gerar evidências
        pass
```

### Criar Nova Política de Decisão

```python
from src.controllers.decision_controller import DecisionPolicy

policy = DecisionPolicy(
    name="custom",
    confidence_threshold=0.75,
    consensus_threshold=0.85
)
```

## 🚀 Boas Práticas

1. **Sempre validar outputs**: Use `validate_output()` para garantir qualidade
2. **Gerar evidências ricas**: Inclua múltiplas fontes e tipos de evidência
3. **Usar ensemble de confiança**: Combine múltiplas estratégias
4. **Registrar tudo**: Use logging extensivo para debugging
5. **Testar completamente**: Cobertura mínima de 80%
6. **Documentar contratos**: Deixe claro o que cada método faz

## 📖 Referências

- **SOLID Principles**: https://en.wikipedia.org/wiki/SOLID
- **Design Patterns**: https://refactoring.guru/design-patterns
- **Python ABC Module**: https://docs.python.org/3/library/abc.html
- **Async/Await**: https://docs.python.org/3/library/asyncio.html

---

**Versão**: 1.0  
**Última atualização**: 2026-02-06  
**Autor**: Manus AI
