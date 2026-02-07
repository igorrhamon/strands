"""
Testes para CheckpointEngine

Testa:
1. Persistência de passos de execução
2. Carregamento de estado
3. Replay de execução
4. Limpeza de checkpoints antigos
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from src.persistence.checkpoint_engine import (
    CheckpointEngine,
    ExecutionStep,
)


class MockCheckpointSaver:
    """Mock do Neo4jCheckpointSaver para testes."""
    
    def __init__(self):
        self.checkpoints: Dict[str, Dict] = {}
        self.connected = False
    
    def connect(self):
        """Conecta (mock)."""
        self.connected = True
    
    def close(self):
        """Fecha (mock)."""
        self.connected = False
    
    def save_checkpoint(self, checkpoint) -> str:
        """Salva checkpoint (mock)."""
        checkpoint_id = checkpoint.checkpoint_id
        self.checkpoints[checkpoint_id] = {
            "thread_id": checkpoint.thread_id,
            "step": checkpoint.step,
            "state_data": checkpoint.state_data,
            "created_at": datetime.now(timezone.utc),
        }
        return checkpoint_id
    
    def load_checkpoint(self, thread_id: str, step: int):
        """Carrega checkpoint (mock)."""
        for checkpoint_id, data in self.checkpoints.items():
            if data["thread_id"] == thread_id and data["step"] == step:
                # Retornar mock de CheckpointState
                class MockCheckpoint:
                    def __init__(self, cid, td, s, sd):
                        self.checkpoint_id = cid
                        self.thread_id = td
                        self.step = s
                        self.state_data = sd
                        self.created_at = data["created_at"]
                        self.metadata = {}
                
                return MockCheckpoint(checkpoint_id, thread_id, step, data["state_data"])
        return None
    
    def list_checkpoints(self, thread_id: str):
        """Lista checkpoints (mock)."""
        checkpoints = []
        for checkpoint_id, data in self.checkpoints.items():
            if data["thread_id"] == thread_id:
                class MockCheckpoint:
                    def __init__(self, cid, td, s, sd):
                        self.checkpoint_id = cid
                        self.thread_id = td
                        self.step = s
                        self.state_data = sd
                        self.created_at = data["created_at"]
                        self.metadata = {}
                
                checkpoints.append(MockCheckpoint(checkpoint_id, thread_id, data["step"], data["state_data"]))
        
        # Ordenar por step
        checkpoints.sort(key=lambda x: x.step)
        return checkpoints
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Deleta checkpoint (mock)."""
        if checkpoint_id in self.checkpoints:
            del self.checkpoints[checkpoint_id]
            return True
        return False
    
    def cleanup_old_checkpoints(self, thread_id: str, keep_last: int = 10) -> int:
        """Limpa checkpoints antigos (mock)."""
        checkpoints = self.list_checkpoints(thread_id)
        
        if len(checkpoints) <= keep_last:
            return 0
        
        to_delete = len(checkpoints) - keep_last
        
        for checkpoint in checkpoints[:-keep_last]:
            self.delete_checkpoint(checkpoint.checkpoint_id)
        
        return to_delete


class TestCheckpointEngine:
    """Testa CheckpointEngine."""
    
    @pytest.fixture
    def mock_saver(self):
        """Cria mock do saver."""
        return MockCheckpointSaver()
    
    @pytest.fixture
    def engine(self, mock_saver):
        """Cria instância do engine."""
        engine = CheckpointEngine(neo4j_saver=mock_saver)
        return engine
    
    def test_initialization(self, engine):
        """Testa inicialização."""
        assert engine.neo4j_saver is not None
        assert engine.logger is not None
    
    def test_persist_execution_step(self, engine):
        """Testa persistência de passo."""
        thread_id = "thread_123"
        step_index = 0
        agent_data = {
            "agent_executions": [
                {
                    "agent_id": "agent_1",
                    "agent_name": "Agent 1",
                    "confidence_score": 0.9,
                    "result": "escalate",
                }
            ]
        }
        
        checkpoint_id = engine.persist_execution_step(
            thread_id=thread_id,
            step_index=step_index,
            agent_data=agent_data,
        )
        
        assert checkpoint_id is not None
        assert isinstance(checkpoint_id, str)
    
    def test_load_execution_step(self, engine):
        """Testa carregamento de passo."""
        thread_id = "thread_123"
        step_index = 0
        agent_data = {"test": "data"}
        
        # Persistir
        engine.persist_execution_step(thread_id, step_index, agent_data)
        
        # Carregar
        execution_step = engine.load_execution_step(thread_id, step_index)
        
        assert execution_step is not None
        assert execution_step.thread_id == thread_id
        assert execution_step.step_index == step_index
        assert execution_step.agent_data == agent_data
    
    def test_load_nonexistent_step(self, engine):
        """Testa carregamento de passo inexistente."""
        execution_step = engine.load_execution_step("thread_999", 999)
        
        assert execution_step is None
    
    def test_list_execution_steps(self, engine):
        """Testa listagem de passos."""
        thread_id = "thread_123"
        
        # Persistir múltiplos passos
        for i in range(5):
            engine.persist_execution_step(
                thread_id=thread_id,
                step_index=i,
                agent_data={"step": i},
            )
        
        # Listar
        steps = engine.list_execution_steps(thread_id)
        
        assert len(steps) == 5
        assert steps[0].step_index == 0
        assert steps[4].step_index == 4
    
    def test_get_latest_step(self, engine):
        """Testa obtenção do passo mais recente."""
        thread_id = "thread_123"
        
        # Persistir múltiplos passos
        for i in range(5):
            engine.persist_execution_step(
                thread_id=thread_id,
                step_index=i,
                agent_data={"step": i},
            )
        
        # Obter último
        latest = engine.get_latest_step(thread_id)
        
        assert latest is not None
        assert latest.step_index == 4
    
    def test_get_latest_step_empty(self, engine):
        """Testa obtenção do passo mais recente quando vazio."""
        latest = engine.get_latest_step("thread_empty")
        
        assert latest is None
    
    def test_replay_from_step(self, engine):
        """Testa replay a partir de um passo."""
        thread_id = "thread_123"
        step_index = 2
        agent_data = {"replay": "data"}
        
        # Persistir
        engine.persist_execution_step(thread_id, step_index, agent_data)
        
        # Replay
        replay_state = engine.replay_from_step(thread_id, step_index)
        
        assert replay_state is not None
        assert replay_state["thread_id"] == thread_id
        assert replay_state["step_index"] == step_index
        assert replay_state["agent_data"] == agent_data
    
    def test_replay_nonexistent_step(self, engine):
        """Testa replay de passo inexistente."""
        replay_state = engine.replay_from_step("thread_999", 999)
        
        assert replay_state is None
    
    def test_cleanup_old_steps(self, engine):
        """Testa limpeza de passos antigos."""
        thread_id = "thread_123"
        
        # Persistir 15 passos
        for i in range(15):
            engine.persist_execution_step(
                thread_id=thread_id,
                step_index=i,
                agent_data={"step": i},
            )
        
        # Limpar, mantendo últimos 10
        deleted = engine.cleanup_old_steps(thread_id, keep_last=10)
        
        assert deleted == 5
        
        # Verificar que restaram 10
        remaining = engine.list_execution_steps(thread_id)
        assert len(remaining) == 10
    
    def test_delete_step(self, engine):
        """Testa deleção de passo."""
        thread_id = "thread_123"
        step_index = 0
        
        # Persistir
        checkpoint_id = engine.persist_execution_step(thread_id, step_index, {"data": "test"})
        
        # Deletar
        success = engine.delete_step(checkpoint_id)
        
        assert success is True
        
        # Verificar que foi deletado
        execution_step = engine.load_execution_step(thread_id, step_index)
        assert execution_step is None
    
    def test_delete_nonexistent_step(self, engine):
        """Testa deleção de passo inexistente."""
        success = engine.delete_step("nonexistent_id")
        
        assert success is False


class TestCheckpointEngineIntegration:
    """Testa integração do CheckpointEngine."""
    
    def test_full_workflow(self):
        """Testa workflow completo."""
        mock_saver = MockCheckpointSaver()
        engine = CheckpointEngine(neo4j_saver=mock_saver)
        
        thread_id = "workflow_thread"
        
        # Passo 1: Coleta de dados
        engine.persist_execution_step(
            thread_id=thread_id,
            step_index=0,
            agent_data={
                "stage": "collection",
                "agents": ["collector_1", "collector_2"],
            },
        )
        
        # Passo 2: Análise
        engine.persist_execution_step(
            thread_id=thread_id,
            step_index=1,
            agent_data={
                "stage": "analysis",
                "agents": ["analyzer_1"],
            },
        )
        
        # Passo 3: Decisão
        engine.persist_execution_step(
            thread_id=thread_id,
            step_index=2,
            agent_data={
                "stage": "decision",
                "decision": "escalate",
            },
        )
        
        # Verificar workflow
        steps = engine.list_execution_steps(thread_id)
        assert len(steps) == 3
        
        # Verificar cada passo
        assert steps[0].agent_data["stage"] == "collection"
        assert steps[1].agent_data["stage"] == "analysis"
        assert steps[2].agent_data["stage"] == "decision"
        
        # Replay do passo 1
        replay = engine.replay_from_step(thread_id, 1)
        assert replay["agent_data"]["stage"] == "analysis"
    
    def test_multiple_threads(self):
        """Testa múltiplas threads."""
        mock_saver = MockCheckpointSaver()
        engine = CheckpointEngine(neo4j_saver=mock_saver)
        
        # Thread 1
        for i in range(3):
            engine.persist_execution_step(
                thread_id="thread_1",
                step_index=i,
                agent_data={"thread": 1, "step": i},
            )
        
        # Thread 2
        for i in range(5):
            engine.persist_execution_step(
                thread_id="thread_2",
                step_index=i,
                agent_data={"thread": 2, "step": i},
            )
        
        # Verificar isolamento
        steps_1 = engine.list_execution_steps("thread_1")
        steps_2 = engine.list_execution_steps("thread_2")
        
        assert len(steps_1) == 3
        assert len(steps_2) == 5
