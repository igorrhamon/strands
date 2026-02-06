"""
Unit Integration Tests for Strands System

Testa integração entre componentes sem dependências externas
"""

import pytest
import sys
import os
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agents.base_agent import BaseAgent, AgentResponse
from services.confidence_service import ConfidenceService, ConfidenceStrategy
from controllers.decision_controller import DecisionController
from engines.replay_engine import ReplayEngine


class MockAgent(BaseAgent):
    """Mock agent para testes"""
    
    def __init__(self, name: str, confidence: float = 0.8):
        super().__init__(name)
        self.confidence = confidence
    
    async def analyze(self, data: dict) -> AgentResponse:
        """Mock analysis"""
        return AgentResponse(
            agent_id=self.id,
            agent_name=self.name,
            confidence=self.confidence,
            analysis="Mock analysis result",
            recommendations=["Recommendation 1", "Recommendation 2"]
        )


class TestBaseAgentContract:
    """Testa contrato base de agentes"""

    def test_agent_initialization(self):
        """Verifica inicialização de agente"""
        agent = MockAgent("TestAgent", 0.85)
        assert agent.name == "TestAgent"
        assert agent.id is not None
        assert agent.confidence == 0.85

    def test_agent_has_required_methods(self):
        """Verifica se agente tem métodos obrigatórios"""
        agent = MockAgent("TestAgent")
        assert hasattr(agent, 'analyze')
        assert hasattr(agent, 'id')
        assert hasattr(agent, 'name')

    @pytest.mark.asyncio
    async def test_agent_analysis(self):
        """Testa análise de agente"""
        agent = MockAgent("TestAgent", 0.9)
        response = await agent.analyze({"test": "data"})
        
        assert isinstance(response, AgentResponse)
        assert response.agent_name == "TestAgent"
        assert response.confidence == 0.9
        assert len(response.recommendations) > 0


class TestConfidenceService:
    """Testa serviço de confiança"""

    def test_confidence_service_initialization(self):
        """Verifica inicialização do serviço"""
        service = ConfidenceService()
        assert service is not None

    def test_calculate_confidence_single_agent(self):
        """Testa cálculo de confiança para um agente"""
        service = ConfidenceService()
        agent_response = AgentResponse(
            agent_id="agent-1",
            agent_name="TestAgent",
            confidence=0.85,
            analysis="Test analysis",
            recommendations=["Rec1"]
        )
        
        confidence = service.calculate_confidence([agent_response])
        assert 0 <= confidence <= 1
        assert confidence > 0

    def test_calculate_confidence_multiple_agents(self):
        """Testa cálculo de confiança para múltiplos agentes"""
        service = ConfidenceService()
        responses = [
            AgentResponse(
                agent_id="agent-1",
                agent_name="Agent1",
                confidence=0.9,
                analysis="Analysis 1",
                recommendations=["Rec1"]
            ),
            AgentResponse(
                agent_id="agent-2",
                agent_name="Agent2",
                confidence=0.8,
                analysis="Analysis 2",
                recommendations=["Rec2"]
            ),
            AgentResponse(
                agent_id="agent-3",
                agent_name="Agent3",
                confidence=0.7,
                analysis="Analysis 3",
                recommendations=["Rec3"]
            )
        ]
        
        confidence = service.calculate_confidence(responses)
        assert 0 <= confidence <= 1
        assert confidence > 0

    def test_confidence_strategies(self):
        """Testa diferentes estratégias de confiança"""
        service = ConfidenceService()
        responses = [
            AgentResponse(
                agent_id=f"agent-{i}",
                agent_name=f"Agent{i}",
                confidence=0.5 + (i * 0.1),
                analysis=f"Analysis {i}",
                recommendations=[f"Rec{i}"]
            )
            for i in range(3)
        ]
        
        # Testar cada estratégia
        for strategy in ConfidenceStrategy:
            confidence = service.calculate_confidence(responses, strategy)
            assert 0 <= confidence <= 1


class TestDecisionController:
    """Testa controlador de decisões"""

    @pytest.mark.asyncio
    async def test_decision_controller_initialization(self):
        """Verifica inicialização do controlador"""
        controller = DecisionController()
        assert controller is not None

    @pytest.mark.asyncio
    async def test_orchestrate_agents(self):
        """Testa orquestração de múltiplos agentes"""
        controller = DecisionController()
        agents = [
            MockAgent("Agent1", 0.9),
            MockAgent("Agent2", 0.85),
            MockAgent("Agent3", 0.8)
        ]
        
        alert_data = {
            "service": "payment-api",
            "severity": "critical",
            "description": "Error rate exceeded"
        }
        
        decision = await controller.orchestrate(agents, alert_data)
        assert decision is not None
        assert "consensus" in str(decision).lower() or "decision" in str(decision).lower()

    @pytest.mark.asyncio
    async def test_consensus_logic(self):
        """Testa lógica de consenso"""
        controller = DecisionController()
        
        # Agentes com alta confiança
        high_confidence_agents = [
            MockAgent("Agent1", 0.95),
            MockAgent("Agent2", 0.92),
            MockAgent("Agent3", 0.90)
        ]
        
        decision_high = await controller.orchestrate(
            high_confidence_agents,
            {"test": "data"}
        )
        
        # Agentes com baixa confiança
        low_confidence_agents = [
            MockAgent("Agent1", 0.45),
            MockAgent("Agent2", 0.42),
            MockAgent("Agent3", 0.40)
        ]
        
        decision_low = await controller.orchestrate(
            low_confidence_agents,
            {"test": "data"}
        )
        
        # Ambas decisões devem ser válidas
        assert decision_high is not None
        assert decision_low is not None


class TestReplayEngine:
    """Testa engine de replay"""

    def test_replay_engine_initialization(self):
        """Verifica inicialização do engine"""
        engine = ReplayEngine()
        assert engine is not None

    def test_record_event(self):
        """Testa gravação de evento"""
        engine = ReplayEngine()
        event = {
            "type": "alert",
            "service": "payment-api",
            "severity": "critical"
        }
        
        engine.record_event(event)
        assert len(engine.events) > 0

    def test_replay_events(self):
        """Testa replay de eventos"""
        engine = ReplayEngine()
        
        # Gravar alguns eventos
        events = [
            {"type": "alert", "id": 1},
            {"type": "analysis", "id": 2},
            {"type": "decision", "id": 3}
        ]
        
        for event in events:
            engine.record_event(event)
        
        # Replay
        replayed = engine.replay_events()
        assert len(replayed) == len(events)

    def test_time_travel_simulation(self):
        """Testa simulação de time-travel"""
        engine = ReplayEngine()
        
        # Gravar timeline
        for i in range(5):
            engine.record_event({"type": "event", "id": i})
        
        # Voltar no tempo
        state_at_3 = engine.get_state_at(3)
        assert state_at_3 is not None


class TestAgentIntegration:
    """Testa integração entre agentes"""

    @pytest.mark.asyncio
    async def test_multiple_agents_coordination(self):
        """Testa coordenação entre múltiplos agentes"""
        agents = [
            MockAgent("MetricsAgent", 0.92),
            MockAgent("LogAnalyzerAgent", 0.88),
            MockAgent("RecommenderAgent", 0.85)
        ]
        
        # Cada agente analisa os dados
        results = []
        for agent in agents:
            response = await agent.analyze({"alert": "test"})
            results.append(response)
        
        assert len(results) == len(agents)
        assert all(isinstance(r, AgentResponse) for r in results)

    @pytest.mark.asyncio
    async def test_confidence_aggregation(self):
        """Testa agregação de confiança entre agentes"""
        agents = [
            MockAgent("Agent1", 0.95),
            MockAgent("Agent2", 0.85),
            MockAgent("Agent3", 0.75)
        ]
        
        responses = []
        for agent in agents:
            response = await agent.analyze({"test": "data"})
            responses.append(response)
        
        service = ConfidenceService()
        overall_confidence = service.calculate_confidence(responses)
        
        # Confiança geral deve estar entre min e max
        min_confidence = min(r.confidence for r in responses)
        max_confidence = max(r.confidence for r in responses)
        
        assert min_confidence <= overall_confidence <= max_confidence


class TestDataFlow:
    """Testa fluxo de dados"""

    @pytest.mark.asyncio
    async def test_alert_to_decision_flow(self):
        """Testa fluxo: Alerta → Análise → Decisão"""
        # 1. Criar alerta
        alert = {
            "service": "payment-api",
            "severity": "critical",
            "description": "Error rate exceeded 5%"
        }
        
        # 2. Analisar com agentes
        agents = [
            MockAgent("MetricsAgent", 0.9),
            MockAgent("LogAnalyzerAgent", 0.85)
        ]
        
        responses = []
        for agent in agents:
            response = await agent.analyze(alert)
            responses.append(response)
        
        # 3. Calcular confiança
        service = ConfidenceService()
        confidence = service.calculate_confidence(responses)
        
        # 4. Gerar decisão
        controller = DecisionController()
        decision = await controller.orchestrate(agents, alert)
        
        # Validar fluxo
        assert len(responses) == len(agents)
        assert 0 <= confidence <= 1
        assert decision is not None


class TestErrorHandling:
    """Testa tratamento de erros"""

    @pytest.mark.asyncio
    async def test_empty_agents_list(self):
        """Testa comportamento com lista vazia de agentes"""
        controller = DecisionController()
        decision = await controller.orchestrate([], {"test": "data"})
        # Deve retornar algo válido ou None
        assert decision is None or isinstance(decision, dict)

    def test_invalid_confidence_values(self):
        """Testa valores inválidos de confiança"""
        service = ConfidenceService()
        
        # Valores fora do intervalo [0, 1]
        responses = [
            AgentResponse(
                agent_id="agent-1",
                agent_name="Agent1",
                confidence=1.5,  # Inválido
                analysis="Analysis",
                recommendations=[]
            )
        ]
        
        # Deve lidar graciosamente
        try:
            confidence = service.calculate_confidence(responses)
            assert 0 <= confidence <= 1
        except ValueError:
            pass  # Comportamento esperado


class TestPerformance:
    """Testa performance"""

    @pytest.mark.asyncio
    async def test_agent_response_time(self):
        """Testa tempo de resposta de agente"""
        import time
        
        agent = MockAgent("TestAgent")
        
        start = time.time()
        response = await agent.analyze({"test": "data"})
        elapsed = time.time() - start
        
        assert response is not None
        assert elapsed < 1.0  # Deve responder em menos de 1 segundo

    @pytest.mark.asyncio
    async def test_multiple_agents_parallel(self):
        """Testa execução paralela de agentes"""
        import time
        import asyncio
        
        agents = [MockAgent(f"Agent{i}") for i in range(5)]
        
        start = time.time()
        tasks = [agent.analyze({"test": "data"}) for agent in agents]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        assert len(results) == len(agents)
        assert elapsed < 2.0  # Execução paralela deve ser rápida


# Fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para testes assíncronos"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
