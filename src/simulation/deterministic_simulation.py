"""
Simulações Determinísticas - Garantir reprodutibilidade.

Este módulo implementa simulações determinísticas com seed fixo,
permitindo replay exato de execuções para testes e debugging.

Padrão: Deterministic Simulation (inspirado em Redux DevTools, Temporal.io)
"""

import hashlib
import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class DeterministicRandom:
    """Gerador de números aleatórios determinístico com seed."""
    
    def __init__(self, seed: int):
        """
        Inicializar gerador.
        
        Args:
            seed: Seed para reprodutibilidade
        """
        self.seed = seed
        self.rng = np.random.RandomState(seed)
        self.python_rng = random.Random(seed)
        self.call_count = 0
    
    def random(self) -> float:
        """
        Gerar número aleatório entre 0 e 1.
        
        Returns:
            Número aleatório determinístico
        """
        self.call_count += 1
        return float(self.rng.random())
    
    def randint(self, a: int, b: int) -> int:
        """
        Gerar inteiro aleatório entre a e b.
        
        Args:
            a: Valor mínimo
            b: Valor máximo
            
        Returns:
            Inteiro aleatório determinístico
        """
        self.call_count += 1
        return int(self.rng.randint(a, b + 1))
    
    def choice(self, seq: List[Any]) -> Any:
        """
        Escolher elemento aleatório de sequência.
        
        Args:
            seq: Sequência para escolher
            
        Returns:
            Elemento aleatório determinístico
        """
        self.call_count += 1
        return self.python_rng.choice(seq)
    
    def shuffle(self, seq: List[Any]) -> List[Any]:
        """
        Embaralhar sequência.
        
        Args:
            seq: Sequência para embaralhar
            
        Returns:
            Sequência embaralhada determinística
        """
        self.call_count += 1
        shuffled = seq.copy()
        self.python_rng.shuffle(shuffled)
        return shuffled
    
    def reset(self):
        """Resetar gerador para seed original."""
        self.rng = np.random.RandomState(self.seed)
        self.python_rng = random.Random(self.seed)
        self.call_count = 0


class SimulationEvent:
    """Evento em uma simulação."""
    
    def __init__(
        self,
        event_type: str,
        timestamp: float,
        data: Dict[str, Any],
        agent_id: Optional[str] = None
    ):
        """
        Inicializar evento.
        
        Args:
            event_type: Tipo de evento
            timestamp: Timestamp do evento
            data: Dados do evento
            agent_id: ID do agente que gerou evento
        """
        self.event_type = event_type
        self.timestamp = timestamp
        self.data = data
        self.agent_id = agent_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter para dicionário."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
            "agent_id": self.agent_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationEvent":
        """Criar a partir de dicionário."""
        return cls(
            event_type=data["event_type"],
            timestamp=data["timestamp"],
            data=data["data"],
            agent_id=data.get("agent_id")
        )


class DeterministicSimulation:
    """Simulação determinística com replay completo."""
    
    def __init__(self, seed: int):
        """
        Inicializar simulação.
        
        Args:
            seed: Seed para reprodutibilidade
        """
        self.seed = seed
        self.rng = DeterministicRandom(seed)
        self.events: List[SimulationEvent] = []
        self.start_time = datetime.utcnow().timestamp()
        self.current_time = self.start_time
        self.execution_id = self._generate_execution_id()
    
    def _generate_execution_id(self) -> str:
        """Gerar ID de execução determinístico."""
        seed_str = f"{self.seed}_{self.start_time}"
        return hashlib.md5(seed_str.encode()).hexdigest()[:16]
    
    def record_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        agent_id: Optional[str] = None,
        delta_ms: float = 0.0
    ) -> SimulationEvent:
        """
        Registrar evento na simulação.
        
        Args:
            event_type: Tipo de evento
            data: Dados do evento
            agent_id: ID do agente
            delta_ms: Tempo decorrido em ms
            
        Returns:
            Evento registrado
        """
        self.current_time += delta_ms / 1000.0
        
        event = SimulationEvent(
            event_type=event_type,
            timestamp=self.current_time - self.start_time,
            data=data,
            agent_id=agent_id
        )
        
        self.events.append(event)
        return event
    
    def get_events(self) -> List[SimulationEvent]:
        """Obter todos os eventos."""
        return self.events.copy()
    
    def get_events_by_agent(self, agent_id: str) -> List[SimulationEvent]:
        """Obter eventos de um agente específico."""
        return [e for e in self.events if e.agent_id == agent_id]
    
    def get_events_by_type(self, event_type: str) -> List[SimulationEvent]:
        """Obter eventos de um tipo específico."""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_execution_timeline(self) -> List[Dict[str, Any]]:
        """Obter timeline de execução."""
        return [event.to_dict() for event in self.events]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter simulação para dicionário."""
        return {
            "seed": self.seed,
            "execution_id": self.execution_id,
            "start_time": self.start_time,
            "end_time": self.current_time,
            "duration_seconds": self.current_time - self.start_time,
            "event_count": len(self.events),
            "events": self.get_execution_timeline()
        }
    
    def to_json(self) -> str:
        """Converter simulação para JSON."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeterministicSimulation":
        """Criar simulação a partir de dicionário."""
        sim = cls(seed=data["seed"])
        sim.execution_id = data["execution_id"]
        sim.start_time = data["start_time"]
        sim.current_time = data["end_time"]
        
        for event_data in data["events"]:
            event = SimulationEvent.from_dict(event_data)
            sim.events.append(event)
        
        return sim


class SimulationReplay:
    """Replay de simulação determinística."""
    
    def __init__(self, simulation: DeterministicSimulation):
        """
        Inicializar replay.
        
        Args:
            simulation: Simulação para fazer replay
        """
        self.simulation = simulation
        self.current_index = 0
        self.current_time = simulation.start_time
    
    def get_current_event(self) -> Optional[SimulationEvent]:
        """Obter evento atual."""
        if self.current_index < len(self.simulation.events):
            return self.simulation.events[self.current_index]
        return None
    
    def advance(self) -> Optional[SimulationEvent]:
        """
        Avançar para próximo evento.
        
        Returns:
            Próximo evento ou None se fim
        """
        if self.current_index < len(self.simulation.events):
            event = self.simulation.events[self.current_index]
            self.current_index += 1
            self.current_time = self.simulation.start_time + event.timestamp
            return event
        return None
    
    def rewind(self) -> Optional[SimulationEvent]:
        """
        Voltar para evento anterior.
        
        Returns:
            Evento anterior ou None se início
        """
        if self.current_index > 0:
            self.current_index -= 1
            event = self.simulation.events[self.current_index]
            self.current_time = self.simulation.start_time + event.timestamp
            return event
        return None
    
    def jump_to(self, index: int) -> Optional[SimulationEvent]:
        """
        Pular para índice específico.
        
        Args:
            index: Índice de evento
            
        Returns:
            Evento no índice ou None
        """
        if 0 <= index < len(self.simulation.events):
            self.current_index = index
            event = self.simulation.events[index]
            self.current_time = self.simulation.start_time + event.timestamp
            return event
        return None
    
    def get_progress(self) -> Tuple[int, int]:
        """
        Obter progresso do replay.
        
        Returns:
            Tupla (índice atual, total de eventos)
        """
        return (self.current_index, len(self.simulation.events))
    
    def reset(self):
        """Resetar replay para início."""
        self.current_index = 0
        self.current_time = self.simulation.start_time


class SimulationComparator:
    """Comparar duas simulações."""
    
    @staticmethod
    def compare(
        sim1: DeterministicSimulation,
        sim2: DeterministicSimulation
    ) -> Dict[str, Any]:
        """
        Comparar duas simulações.
        
        Args:
            sim1: Primeira simulação
            sim2: Segunda simulação
            
        Returns:
            Dicionário com comparação
        """
        events1 = sim1.get_events()
        events2 = sim2.get_events()
        
        differences = []
        
        # Comparar número de eventos
        if len(events1) != len(events2):
            differences.append({
                "type": "event_count_mismatch",
                "sim1_count": len(events1),
                "sim2_count": len(events2)
            })
        
        # Comparar eventos individuais
        for i, (e1, e2) in enumerate(zip(events1, events2)):
            if e1.event_type != e2.event_type:
                differences.append({
                    "type": "event_type_mismatch",
                    "index": i,
                    "sim1_type": e1.event_type,
                    "sim2_type": e2.event_type
                })
            
            if e1.agent_id != e2.agent_id:
                differences.append({
                    "type": "agent_id_mismatch",
                    "index": i,
                    "sim1_agent": e1.agent_id,
                    "sim2_agent": e2.agent_id
                })
            
            if e1.data != e2.data:
                differences.append({
                    "type": "event_data_mismatch",
                    "index": i,
                    "sim1_data": e1.data,
                    "sim2_data": e2.data
                })
        
        return {
            "identical": len(differences) == 0,
            "difference_count": len(differences),
            "differences": differences,
            "sim1_duration": sim1.current_time - sim1.start_time,
            "sim2_duration": sim2.current_time - sim2.start_time
        }
    
    @staticmethod
    def are_identical(
        sim1: DeterministicSimulation,
        sim2: DeterministicSimulation
    ) -> bool:
        """
        Verificar se simulações são idênticas.
        
        Args:
            sim1: Primeira simulação
            sim2: Segunda simulação
            
        Returns:
            True se idênticas
        """
        comparison = SimulationComparator.compare(sim1, sim2)
        return comparison["identical"]
