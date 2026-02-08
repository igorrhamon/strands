"""
Testes para simulações determinísticas.

Valida reprodutibilidade e replay de execuções.
"""

import pytest
import json

from src.simulation.deterministic_simulation import (
    DeterministicRandom,
    SimulationEvent,
    DeterministicSimulation,
    SimulationReplay,
    SimulationComparator,
)


class TestDeterministicRandom:
    """Testes para gerador aleatório determinístico."""
    
    def test_same_seed_produces_same_sequence(self):
        """Mesmo seed produz mesma sequência."""
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=42)
        
        for _ in range(10):
            assert rng1.random() == rng2.random()
    
    def test_different_seed_produces_different_sequence(self):
        """Seeds diferentes produzem sequências diferentes."""
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=43)
        
        values1 = [rng1.random() for _ in range(10)]
        values2 = [rng2.random() for _ in range(10)]
        
        assert values1 != values2
    
    def test_randint_deterministic(self):
        """randint é determinístico."""
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=42)
        
        for _ in range(10):
            assert rng1.randint(1, 100) == rng2.randint(1, 100)
    
    def test_choice_deterministic(self):
        """choice é determinístico."""
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=42)
        
        seq = ["a", "b", "c", "d", "e"]
        
        for _ in range(10):
            assert rng1.choice(seq) == rng2.choice(seq)
    
    def test_shuffle_deterministic(self):
        """shuffle é determinístico."""
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=42)
        
        seq = [1, 2, 3, 4, 5]
        
        assert rng1.shuffle(seq.copy()) == rng2.shuffle(seq.copy())
    
    def test_call_count_increments(self):
        """call_count incrementa corretamente."""
        rng = DeterministicRandom(seed=42)
        
        assert rng.call_count == 0
        rng.random()
        assert rng.call_count == 1
        rng.randint(1, 10)
        assert rng.call_count == 2
    
    def test_reset(self):
        """reset volta ao estado inicial."""
        rng = DeterministicRandom(seed=42)
        
        values1 = [rng.random() for _ in range(5)]
        rng.reset()
        values2 = [rng.random() for _ in range(5)]
        
        assert values1 == values2


class TestSimulationEvent:
    """Testes para eventos de simulação."""
    
    def test_create_event(self):
        """Criar evento."""
        event = SimulationEvent(
            event_type="agent_executed",
            timestamp=1.5,
            data={"confidence": 0.85},
            agent_id="agent_1"
        )
        
        assert event.event_type == "agent_executed"
        assert event.timestamp == 1.5
        assert event.agent_id == "agent_1"
    
    def test_event_to_dict(self):
        """Converter evento para dicionário."""
        event = SimulationEvent(
            event_type="agent_executed",
            timestamp=1.5,
            data={"confidence": 0.85},
            agent_id="agent_1"
        )
        
        d = event.to_dict()
        assert d["event_type"] == "agent_executed"
        assert d["timestamp"] == 1.5
        assert d["agent_id"] == "agent_1"
    
    def test_event_from_dict(self):
        """Criar evento a partir de dicionário."""
        d = {
            "event_type": "agent_executed",
            "timestamp": 1.5,
            "data": {"confidence": 0.85},
            "agent_id": "agent_1"
        }
        
        event = SimulationEvent.from_dict(d)
        assert event.event_type == "agent_executed"
        assert event.timestamp == 1.5


class TestDeterministicSimulation:
    """Testes para simulação determinística."""
    
    def test_create_simulation(self):
        """Criar simulação."""
        sim = DeterministicSimulation(seed=42)
        
        assert sim.seed == 42
        assert len(sim.events) == 0
        assert sim.execution_id is not None
    
    def test_same_seed_same_execution_id(self):
        """Mesmo seed produz mesmo execution_id."""
        sim1 = DeterministicSimulation(seed=42)
        sim2 = DeterministicSimulation(seed=42)
        
        assert sim1.execution_id == sim2.execution_id
    
    def test_different_seed_different_execution_id(self):
        """Seeds diferentes produzem execution_ids diferentes."""
        sim1 = DeterministicSimulation(seed=42)
        sim2 = DeterministicSimulation(seed=43)
        
        assert sim1.execution_id != sim2.execution_id
    
    def test_record_event(self):
        """Registrar evento."""
        sim = DeterministicSimulation(seed=42)
        
        event = sim.record_event(
            event_type="agent_executed",
            data={"confidence": 0.85},
            agent_id="agent_1",
            delta_ms=100.0
        )
        
        assert event.event_type == "agent_executed"
        assert len(sim.events) == 1
    
    def test_get_events_by_agent(self):
        """Obter eventos de um agente."""
        sim = DeterministicSimulation(seed=42)
        
        sim.record_event("agent_executed", {"confidence": 0.85}, agent_id="agent_1")
        sim.record_event("agent_executed", {"confidence": 0.75}, agent_id="agent_2")
        sim.record_event("agent_executed", {"confidence": 0.80}, agent_id="agent_1")
        
        events = sim.get_events_by_agent("agent_1")
        assert len(events) == 2
        assert all(e.agent_id == "agent_1" for e in events)
    
    def test_get_events_by_type(self):
        """Obter eventos de um tipo."""
        sim = DeterministicSimulation(seed=42)
        
        sim.record_event("agent_executed", {"confidence": 0.85})
        sim.record_event("decision_made", {"decision": "approve"})
        sim.record_event("agent_executed", {"confidence": 0.75})
        
        events = sim.get_events_by_type("agent_executed")
        assert len(events) == 2
        assert all(e.event_type == "agent_executed" for e in events)
    
    def test_simulation_to_dict(self):
        """Converter simulação para dicionário."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85}, agent_id="agent_1")
        
        d = sim.to_dict()
        assert d["seed"] == 42
        assert d["event_count"] == 1
        assert len(d["events"]) == 1
    
    def test_simulation_to_json(self):
        """Converter simulação para JSON."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85})
        
        json_str = sim.to_json()
        data = json.loads(json_str)
        
        assert data["seed"] == 42
        assert data["event_count"] == 1
    
    def test_simulation_from_dict(self):
        """Criar simulação a partir de dicionário."""
        sim1 = DeterministicSimulation(seed=42)
        sim1.record_event("agent_executed", {"confidence": 0.85})
        
        d = sim1.to_dict()
        sim2 = DeterministicSimulation.from_dict(d)
        
        assert sim2.seed == 42
        assert len(sim2.events) == 1
        assert sim2.events[0].event_type == "agent_executed"


class TestSimulationReplay:
    """Testes para replay de simulação."""
    
    def test_create_replay(self):
        """Criar replay."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85})
        
        replay = SimulationReplay(sim)
        assert replay.current_index == 0
    
    def test_advance_through_events(self):
        """Avançar através de eventos."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85})
        sim.record_event("decision_made", {"decision": "approve"})
        
        replay = SimulationReplay(sim)
        
        event1 = replay.advance()
        assert event1.event_type == "agent_executed"
        assert replay.current_index == 1
        
        event2 = replay.advance()
        assert event2.event_type == "decision_made"
        assert replay.current_index == 2
        
        event3 = replay.advance()
        assert event3 is None
    
    def test_rewind(self):
        """Voltar em eventos."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85})
        sim.record_event("decision_made", {"decision": "approve"})
        
        replay = SimulationReplay(sim)
        replay.advance()
        replay.advance()
        
        event = replay.rewind()
        assert event.event_type == "agent_executed"
        assert replay.current_index == 1
    
    def test_jump_to(self):
        """Pular para índice específico."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85})
        sim.record_event("decision_made", {"decision": "approve"})
        sim.record_event("completed", {})
        
        replay = SimulationReplay(sim)
        
        event = replay.jump_to(2)
        assert event.event_type == "completed"
        assert replay.current_index == 2
    
    def test_get_progress(self):
        """Obter progresso do replay."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85})
        sim.record_event("decision_made", {"decision": "approve"})
        
        replay = SimulationReplay(sim)
        
        assert replay.get_progress() == (0, 2)
        replay.advance()
        assert replay.get_progress() == (1, 2)
    
    def test_reset(self):
        """Resetar replay."""
        sim = DeterministicSimulation(seed=42)
        sim.record_event("agent_executed", {"confidence": 0.85})
        
        replay = SimulationReplay(sim)
        replay.advance()
        assert replay.current_index == 1
        
        replay.reset()
        assert replay.current_index == 0


class TestSimulationComparator:
    """Testes para comparador de simulações."""
    
    def test_identical_simulations(self):
        """Comparar simulações idênticas."""
        sim1 = DeterministicSimulation(seed=42)
        sim1.record_event("agent_executed", {"confidence": 0.85})
        
        sim2 = DeterministicSimulation(seed=42)
        sim2.record_event("agent_executed", {"confidence": 0.85})
        
        assert SimulationComparator.are_identical(sim1, sim2)
    
    def test_different_event_count(self):
        """Detectar diferença em contagem de eventos."""
        sim1 = DeterministicSimulation(seed=42)
        sim1.record_event("agent_executed", {"confidence": 0.85})
        
        sim2 = DeterministicSimulation(seed=42)
        sim2.record_event("agent_executed", {"confidence": 0.85})
        sim2.record_event("decision_made", {"decision": "approve"})
        
        comparison = SimulationComparator.compare(sim1, sim2)
        assert comparison["identical"] is False
        assert comparison["difference_count"] > 0
    
    def test_different_event_type(self):
        """Detectar diferença em tipo de evento."""
        sim1 = DeterministicSimulation(seed=42)
        sim1.record_event("agent_executed", {"confidence": 0.85})
        
        sim2 = DeterministicSimulation(seed=42)
        sim2.record_event("decision_made", {"decision": "approve"})
        
        comparison = SimulationComparator.compare(sim1, sim2)
        assert comparison["identical"] is False
    
    def test_different_event_data(self):
        """Detectar diferença em dados de evento."""
        sim1 = DeterministicSimulation(seed=42)
        sim1.record_event("agent_executed", {"confidence": 0.85})
        
        sim2 = DeterministicSimulation(seed=42)
        sim2.record_event("agent_executed", {"confidence": 0.75})
        
        comparison = SimulationComparator.compare(sim1, sim2)
        assert comparison["identical"] is False
