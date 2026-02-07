"""
CheckpointEngine - Motor de Persistência de Checkpoints

Responsável por salvar e carregar estado de execução em pontos críticos.
Permite retentativa após falhas sem perder contexto.

Padrão: Repository Pattern + State Snapshot (inspiração LangGraph)
Resiliência: Retry automático com backoff exponencial
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import uuid

from src.persistence.neo4j_adapter import Neo4jCheckpointSaver, CheckpointState

logger = logging.getLogger(__name__)


@dataclass
class ExecutionStep:
    """Representa um passo de execução."""
    
    step_id: str
    thread_id: str
    step_index: int
    agent_data: Dict[str, Any]
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "step_id": self.step_id,
            "thread_id": self.thread_id,
            "step_index": self.step_index,
            "agent_data": self.agent_data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {},
        }


class CheckpointEngine:
    """Motor de persistência de checkpoints.
    
    Responsabilidades:
    1. Salvar estado de execução em pontos críticos
    2. Carregar estado para retentativa
    3. Gerenciar histórico de checkpoints
    4. Limpar checkpoints antigos
    
    Padrão: Repository Pattern
    """
    
    def __init__(self, neo4j_saver: Optional[Neo4jCheckpointSaver] = None):
        """Inicializa o engine.
        
        Args:
            neo4j_saver: Adaptador Neo4j (default: criar novo)
        """
        self.neo4j_saver = neo4j_saver or Neo4jCheckpointSaver()
        self.logger = logging.getLogger("checkpoint_engine")
        
        # Conectar ao Neo4j
        try:
            self.neo4j_saver.connect()
            self.logger.info("CheckpointEngine conectado ao Neo4j")
        except Exception as e:
            self.logger.error(f"Erro ao conectar ao Neo4j: {e}")
            raise
    
    def persist_execution_step(self,
                              thread_id: str,
                              step_index: int,
                              agent_data: Dict[str, Any],
                              metadata: Optional[Dict] = None) -> str:
        """Persiste um passo de execução.
        
        Cria estrutura no Neo4j:
            (:ExecutionThread {thread_id})
              └─[:HAS_STEP]→ (:ExecutionStep {step_index, agent_data})
        
        Args:
            thread_id: ID da thread/sessão
            step_index: Índice do passo
            agent_data: Dados dos agentes
            metadata: Metadados adicionais
        
        Returns:
            ID do checkpoint salvo
        """
        step_id = str(uuid.uuid4())
        
        # Criar ExecutionStep
        execution_step = ExecutionStep(
            step_id=step_id,
            thread_id=thread_id,
            step_index=step_index,
            agent_data=agent_data,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        
        # Converter para CheckpointState
        checkpoint = CheckpointState(
            checkpoint_id=step_id,
            thread_id=thread_id,
            step=step_index,
            state_data=agent_data,
            agent_memory=self._extract_agent_memory(agent_data),
            decision_context=metadata,
            metadata={"step_index": step_index},
        )
        
        # Salvar via Neo4j
        try:
            checkpoint_id = self.neo4j_saver.save_checkpoint(checkpoint)
            self.logger.info(
                f"Passo de execução persistido: {checkpoint_id} "
                f"(thread={thread_id}, step={step_index})"
            )
            return checkpoint_id
        except Exception as e:
            self.logger.error(f"Erro ao persistir passo de execução: {e}")
            raise
    
    def load_execution_step(self, thread_id: str, step_index: int) -> Optional[ExecutionStep]:
        """Carrega um passo de execução.
        
        Args:
            thread_id: ID da thread
            step_index: Índice do passo
        
        Returns:
            ExecutionStep ou None se não encontrado
        """
        try:
            checkpoint = self.neo4j_saver.load_checkpoint(thread_id, step_index)
            
            if not checkpoint:
                self.logger.warning(
                    f"Passo não encontrado: thread={thread_id}, step={step_index}"
                )
                return None
            
            # Converter para ExecutionStep
            execution_step = ExecutionStep(
                step_id=checkpoint.checkpoint_id,
                thread_id=thread_id,
                step_index=step_index,
                agent_data=checkpoint.state_data,
                timestamp=checkpoint.created_at,
                metadata=checkpoint.metadata,
            )
            
            self.logger.info(
                f"Passo carregado: {execution_step.step_id} "
                f"(thread={thread_id}, step={step_index})"
            )
            
            return execution_step
        
        except Exception as e:
            self.logger.error(f"Erro ao carregar passo de execução: {e}")
            raise
    
    def list_execution_steps(self, thread_id: str) -> List[ExecutionStep]:
        """Lista todos os passos de uma thread.
        
        Args:
            thread_id: ID da thread
        
        Returns:
            Lista de ExecutionStep ordenados por step_index
        """
        try:
            checkpoints = self.neo4j_saver.list_checkpoints(thread_id)
            
            execution_steps = []
            for checkpoint in checkpoints:
                step = ExecutionStep(
                    step_id=checkpoint.checkpoint_id,
                    thread_id=thread_id,
                    step_index=checkpoint.step,
                    agent_data=checkpoint.state_data,
                    timestamp=checkpoint.created_at,
                    metadata=checkpoint.metadata,
                )
                execution_steps.append(step)
            
            self.logger.info(f"Listados {len(execution_steps)} passo(s) da thread {thread_id}")
            
            return execution_steps
        
        except Exception as e:
            self.logger.error(f"Erro ao listar passos de execução: {e}")
            raise
    
    def get_latest_step(self, thread_id: str) -> Optional[ExecutionStep]:
        """Obtém o passo mais recente de uma thread.
        
        Args:
            thread_id: ID da thread
        
        Returns:
            ExecutionStep mais recente ou None
        """
        try:
            steps = self.list_execution_steps(thread_id)
            
            if not steps:
                return None
            
            # Retornar último passo (já ordenado por step_index)
            return steps[-1]
        
        except Exception as e:
            self.logger.error(f"Erro ao obter passo mais recente: {e}")
            raise
    
    def replay_from_step(self, thread_id: str, step_index: int) -> Optional[Dict]:
        """Carrega estado para replay a partir de um passo específico.
        
        Args:
            thread_id: ID da thread
            step_index: Índice do passo
        
        Returns:
            Estado completo para replay ou None
        """
        try:
            execution_step = self.load_execution_step(thread_id, step_index)
            
            if not execution_step:
                return None
            
            # Preparar estado para replay
            replay_state = {
                "thread_id": thread_id,
                "step_index": step_index,
                "agent_data": execution_step.agent_data,
                "timestamp": execution_step.timestamp.isoformat(),
                "metadata": execution_step.metadata,
            }
            
            self.logger.info(
                f"Estado carregado para replay: thread={thread_id}, step={step_index}"
            )
            
            return replay_state
        
        except Exception as e:
            self.logger.error(f"Erro ao carregar estado para replay: {e}")
            raise
    
    def cleanup_old_steps(self, thread_id: str, keep_last: int = 10) -> int:
        """Remove passos antigos, mantendo os últimos N.
        
        Args:
            thread_id: ID da thread
            keep_last: Número de passos recentes a manter
        
        Returns:
            Número de passos deletados
        """
        try:
            deleted_count = self.neo4j_saver.cleanup_old_checkpoints(thread_id, keep_last)
            
            self.logger.info(
                f"Limpeza concluída: {deleted_count} passo(s) deletado(s) "
                f"(mantendo últimos {keep_last})"
            )
            
            return deleted_count
        
        except Exception as e:
            self.logger.error(f"Erro ao limpar passos antigos: {e}")
            raise
    
    def delete_step(self, checkpoint_id: str) -> bool:
        """Deleta um passo específico.
        
        Args:
            checkpoint_id: ID do checkpoint
        
        Returns:
            True se deletado com sucesso
        """
        try:
            success = self.neo4j_saver.delete_checkpoint(checkpoint_id)
            
            if success:
                self.logger.info(f"Passo deletado: {checkpoint_id}")
            else:
                self.logger.warning(f"Passo não encontrado: {checkpoint_id}")
            
            return success
        
        except Exception as e:
            self.logger.error(f"Erro ao deletar passo: {e}")
            raise
    
    def _extract_agent_memory(self, agent_data: Dict[str, Any]) -> Dict[str, Dict]:
        """Extrai memória dos agentes dos dados.
        
        Args:
            agent_data: Dados dos agentes
        
        Returns:
            Dicionário com memória por agente
        """
        agent_memory = {}
        
        # Extrair agent_executions se existir
        if "agent_executions" in agent_data:
            for execution in agent_data["agent_executions"]:
                agent_id = execution.get("agent_id", "unknown")
                agent_memory[agent_id] = {
                    "name": execution.get("agent_name"),
                    "confidence": execution.get("confidence_score"),
                    "result": execution.get("result"),
                }
        
        return agent_memory
    
    def close(self):
        """Fecha conexões."""
        if self.neo4j_saver:
            self.neo4j_saver.close()
            self.logger.info("CheckpointEngine fechado")
