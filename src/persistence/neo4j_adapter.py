"""
Neo4j Adapter - Persistência de Checkpoints para ReplayEngine

Implementa padrão similar a LangGraph's checkpoint saver.
Salva estado de execução em pontos críticos para permitir retentativa
após falhas.

Inspiração: Temporal.io's workflow state management
"""

import os
import logging
import time
from functools import wraps
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
from uuid import UUID

from neo4j import GraphDatabase, Driver, Session
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    """Decorator de retry com backoff exponencial (inspiração Temporal.io).
    
    Args:
        max_retries: Número máximo de tentativas
        initial_delay: Delay inicial em segundos
        backoff_factor: Fator multiplicativo para backoff exponencial
    
    Returns:
        Função decoradora
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Tentativa {attempt + 1}/{max_retries} falhou em {func.__name__}: {e}. "
                            f"Aguardando {delay}s antes de retry..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"Todas as {max_retries} tentativas falharam em {func.__name__}: {e}")
            
            raise last_exception
        
        return wrapper
    return decorator


class CheckpointState(BaseModel):
    """Representa um checkpoint de estado.
    
    Armazena snapshot completo do estado da execução em um ponto específico.
    """
    
    checkpoint_id: str = Field(..., description="ID único do checkpoint")
    thread_id: str = Field(..., description="ID da thread/sessão de execução")
    step: int = Field(..., ge=0, description="Número do passo na execução")
    state_data: Dict[str, Any] = Field(default_factory=dict, description="Dados do estado")
    agent_memory: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Snapshot da memória de cada agente"
    )
    decision_context: Optional[Dict[str, Any]] = Field(
        None, 
        description="Contexto de decisão naquele momento"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = False


class Neo4jCheckpointSaver:
    """Saver de checkpoints usando Neo4j.
    
    Responsabilidades:
    1. Salvar checkpoint em ponto crítico
    2. Carregar checkpoint para retentativa
    3. Gerenciar histórico de checkpoints
    4. Limpar checkpoints antigos
    """
    
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, 
                 password: Optional[str] = None):
        """Inicializa adaptador Neo4j.
        
        Args:
            uri: URI do Neo4j (default: env NEO4J_URI)
            user: Usuário (default: env NEO4J_USER)
            password: Senha (default: env NEO4J_PASSWORD)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "strands123")
        self._driver: Optional[Driver] = None
        self.logger = logging.getLogger("neo4j_checkpoint_saver")
    
    def connect(self):
        """Estabelece conexão com Neo4j."""
        if not self._driver:
            try:
                self._driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                    encrypted=False,  # Ajustar conforme necessário
                )
                self._verify_connectivity()
                self.logger.info(f"Conectado ao Neo4j em {self.uri}")
            except Exception as e:
                self.logger.error(f"Falha ao conectar ao Neo4j: {e}")
                raise
    
    def _verify_connectivity(self):
        """Verifica se conexão está ativa."""
        if self._driver:
            try:
                self._driver.verify_connectivity()
            except Exception as e:
                self.logger.error(f"Verificação de conectividade falhou: {e}")
                raise
    
    def close(self):
        """Fecha conexão com Neo4j."""
        if self._driver:
            self._driver.close()
            self._driver = None
            self.logger.info("Conexão com Neo4j fechada")
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def save_checkpoint(self, checkpoint: CheckpointState) -> str:
        """Salva checkpoint no Neo4j.
        
        Cria estrutura:
            (:ExecutionThread)-[:HAS_CHECKPOINT]->(:Checkpoint)
            (:Checkpoint)-[:SNAPSHOT_AGENT_MEMORY]->(:AgentMemory)
        
        Args:
            checkpoint: Checkpoint a salvar
        
        Returns:
            ID do checkpoint salvo
        
        Raises:
            Exception: Se falha ao salvar após retries
        """
        if not self._driver:
            self.connect()
        
        query = """
        MERGE (thread:ExecutionThread {thread_id: $thread_id})
        CREATE (checkpoint:Checkpoint {
            checkpoint_id: $checkpoint_id,
            step: $step,
            state_data: $state_data,
            decision_context: $decision_context,
            created_at: $created_at,
            metadata: $metadata
        })
        CREATE (thread)-[:HAS_CHECKPOINT {order: $step}]->(checkpoint)
        RETURN checkpoint.checkpoint_id as checkpoint_id
        """
        
        params = {
            "thread_id": checkpoint.thread_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "step": checkpoint.step,
            "state_data": checkpoint.state_data,
            "decision_context": checkpoint.decision_context or {},
            "created_at": checkpoint.created_at.isoformat(),
            "metadata": checkpoint.metadata,
        }
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                
                if record:
                    checkpoint_id = record["checkpoint_id"]
                    self.logger.info(
                        f"Checkpoint salvo: {checkpoint_id} (thread: {checkpoint.thread_id}, "
                        f"step: {checkpoint.step})"
                    )
                    
                    # Salvar memória dos agentes
                    self._save_agent_memory(checkpoint)
                    
                    return checkpoint_id
                else:
                    raise RuntimeError("Falha ao salvar checkpoint")
        
        except Exception as e:
            self.logger.error(f"Erro ao salvar checkpoint: {e}")
            raise
    
    def _save_agent_memory(self, checkpoint: CheckpointState):
        """Salva snapshot da memória dos agentes.
        
        Args:
            checkpoint: Checkpoint contendo memória dos agentes
        """
        if not checkpoint.agent_memory:
            return
        
        query = """
        MATCH (checkpoint:Checkpoint {checkpoint_id: $checkpoint_id})
        UNWIND $agent_memories as agent_mem
        CREATE (memory:AgentMemory {
            agent_id: agent_mem.agent_id,
            memory_data: agent_mem.memory_data,
            timestamp: $timestamp
        })
        CREATE (checkpoint)-[:SNAPSHOT_AGENT_MEMORY]->(memory)
        """
        
        agent_memories = [
            {
                "agent_id": agent_id,
                "memory_data": memory_data,
            }
            for agent_id, memory_data in checkpoint.agent_memory.items()
        ]
        
        params = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "agent_memories": agent_memories,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            with self._driver.session() as session:
                session.run(query, params)
                self.logger.debug(
                    f"Memória de {len(checkpoint.agent_memory)} agente(s) salva"
                )
        except Exception as e:
            self.logger.warning(f"Falha ao salvar memória dos agentes: {e}")
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def load_checkpoint(self, thread_id: str, step: int) -> Optional[CheckpointState]:
        """Carrega checkpoint para retentativa.
        
        Args:
            thread_id: ID da thread
            step: Número do passo
        
        Returns:
            CheckpointState ou None se não encontrado
        """
        if not self._driver:
            self.connect()
        
        query = """
        MATCH (thread:ExecutionThread {thread_id: $thread_id})
        MATCH (thread)-[:HAS_CHECKPOINT {order: $step}]->(checkpoint:Checkpoint)
        OPTIONAL MATCH (checkpoint)-[:SNAPSHOT_AGENT_MEMORY]->(memory:AgentMemory)
        RETURN checkpoint, collect(memory) as agent_memories
        """
        
        params = {
            "thread_id": thread_id,
            "step": step,
        }
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                
                if not record:
                    self.logger.warning(
                        f"Checkpoint não encontrado: thread={thread_id}, step={step}"
                    )
                    return None
                
                checkpoint_node = record["checkpoint"]
                agent_memories = record["agent_memories"]
                
                # Reconstruir checkpoint
                agent_memory = {}
                for memory_node in agent_memories:
                    agent_id = memory_node["agent_id"]
                    agent_memory[agent_id] = memory_node["memory_data"]
                
                checkpoint = CheckpointState(
                    checkpoint_id=checkpoint_node["checkpoint_id"],
                    thread_id=thread_id,
                    step=step,
                    state_data=checkpoint_node["state_data"],
                    agent_memory=agent_memory,
                    decision_context=checkpoint_node.get("decision_context"),
                    metadata=checkpoint_node.get("metadata", {}),
                )
                
                self.logger.info(
                    f"Checkpoint carregado: {checkpoint.checkpoint_id} "
                    f"(thread: {thread_id}, step: {step})"
                )
                
                return checkpoint
        
        except Exception as e:
            self.logger.error(f"Erro ao carregar checkpoint: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def list_checkpoints(self, thread_id: str) -> List[CheckpointState]:
        """Lista todos os checkpoints de uma thread.
        
        Args:
            thread_id: ID da thread
        
        Returns:
            Lista de checkpoints ordenados por step
        """
        if not self._driver:
            self.connect()
        
        query = """
        MATCH (thread:ExecutionThread {thread_id: $thread_id})
        MATCH (thread)-[:HAS_CHECKPOINT]->(checkpoint:Checkpoint)
        RETURN checkpoint
        ORDER BY checkpoint.step ASC
        """
        
        params = {"thread_id": thread_id}
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                
                checkpoints = []
                for record in result:
                    node = record["checkpoint"]
                    checkpoint = CheckpointState(
                        checkpoint_id=node["checkpoint_id"],
                        thread_id=thread_id,
                        step=node["step"],
                        state_data=node["state_data"],
                        decision_context=node.get("decision_context"),
                        metadata=node.get("metadata", {}),
                    )
                    checkpoints.append(checkpoint)
                
                self.logger.info(f"Listados {len(checkpoints)} checkpoint(s) para thread {thread_id}")
                
                return checkpoints
        
        except Exception as e:
            self.logger.error(f"Erro ao listar checkpoints: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Deleta um checkpoint.
        
        Args:
            checkpoint_id: ID do checkpoint
        
        Returns:
            True se deletado com sucesso
        """
        if not self._driver:
            self.connect()
        
        query = """
        MATCH (checkpoint:Checkpoint {checkpoint_id: $checkpoint_id})
        OPTIONAL MATCH (checkpoint)-[r:SNAPSHOT_AGENT_MEMORY]->(memory:AgentMemory)
        DELETE r, memory, checkpoint
        RETURN count(checkpoint) as deleted
        """
        
        params = {"checkpoint_id": checkpoint_id}
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                
                if record and record["deleted"] > 0:
                    self.logger.info(f"Checkpoint deletado: {checkpoint_id}")
                    return True
                else:
                    self.logger.warning(f"Checkpoint não encontrado: {checkpoint_id}")
                    return False
        
        except Exception as e:
            self.logger.error(f"Erro ao deletar checkpoint: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def cleanup_old_checkpoints(self, thread_id: str, keep_last: int = 10) -> int:
        """Remove checkpoints antigos, mantendo os últimos N.
        
        Args:
            thread_id: ID da thread
            keep_last: Número de checkpoints recentes a manter
        
        Returns:
            Número de checkpoints deletados
        """
        if not self._driver:
            self.connect()
        
        query = """
        MATCH (thread:ExecutionThread {thread_id: $thread_id})
        MATCH (thread)-[:HAS_CHECKPOINT]->(checkpoint:Checkpoint)
        WITH checkpoint
        ORDER BY checkpoint.step DESC
        SKIP $keep_last
        OPTIONAL MATCH (checkpoint)-[r:SNAPSHOT_AGENT_MEMORY]->(memory:AgentMemory)
        DELETE r, memory, checkpoint
        RETURN count(checkpoint) as deleted
        """
        
        params = {
            "thread_id": thread_id,
            "keep_last": keep_last,
        }
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                deleted_count = record["deleted"] if record else 0
                
                self.logger.info(
                    f"Limpeza de checkpoints concluída: {deleted_count} deletado(s) "
                    f"(mantendo últimos {keep_last})"
                )
                
                return deleted_count
        
        except Exception as e:
            self.logger.error(f"Erro ao limpar checkpoints antigos: {e}")
            raise


    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def persist_execution_step(self, thread_id: str, step_index: int, 
                               agent_data: Dict[str, Any]) -> str:
        """Persiste um passo de execução com dados de agentes.
        
        Cria estrutura:
            (:ExecutionThread)-[:HAS_STEP]->(:ExecutionStep)
        
        Args:
            thread_id: ID da thread
            step_index: Índice do passo
            agent_data: Dados dos agentes (JSON serializado)
        
        Returns:
            ID do passo persistido
        
        Raises:
            Exception: Se falha ao persistir após retries
        """
        if not self._driver:
            self.connect()
        
        step_id = f"step_{thread_id}_{step_index}"
        
        query = """
        MERGE (thread:ExecutionThread {thread_id: $thread_id})
        CREATE (step:ExecutionStep {
            step_id: $step_id,
            step_index: $step_index,
            agent_data: $agent_data,
            created_at: $created_at
        })
        CREATE (thread)-[:HAS_STEP {order: $step_index}]->(step)
        RETURN step.step_id as step_id
        """
        
        params = {
            "thread_id": thread_id,
            "step_id": step_id,
            "step_index": step_index,
            "agent_data": agent_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                
                if record:
                    persisted_step_id = record["step_id"]
                    self.logger.info(
                        f"Passo de execução persistido: {persisted_step_id} "
                        f"(thread: {thread_id}, step: {step_index})"
                    )
                    return persisted_step_id
                else:
                    raise RuntimeError("Falha ao persistir passo de execução")
        
        except Exception as e:
            self.logger.error(f"Erro ao persistir passo de execução: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def load_execution_step(self, thread_id: str, step_index: int) -> Optional[Dict]:
        """Carrega um passo de execução.
        
        Args:
            thread_id: ID da thread
            step_index: Índice do passo
        
        Returns:
            Dicionário com dados do passo ou None
        """
        if not self._driver:
            self.connect()
        
        query = """
        MATCH (thread:ExecutionThread {thread_id: $thread_id})
        MATCH (thread)-[:HAS_STEP {order: $step_index}]->(step:ExecutionStep)
        RETURN step
        """
        
        params = {
            "thread_id": thread_id,
            "step_index": step_index,
        }
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                
                if not record:
                    self.logger.warning(
                        f"Passo não encontrado: thread={thread_id}, step={step_index}"
                    )
                    return None
                
                step_node = record["step"]
                
                step_data = {
                    "step_id": step_node["step_id"],
                    "step_index": step_node["step_index"],
                    "agent_data": step_node["agent_data"],
                    "created_at": step_node["created_at"],
                }
                
                self.logger.info(
                    f"Passo carregado: {step_data['step_id']} "
                    f"(thread: {thread_id}, step: {step_index})"
                )
                
                return step_data
        
        except Exception as e:
            self.logger.error(f"Erro ao carregar passo de execução: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def list_execution_steps(self, thread_id: str) -> List[Dict]:
        """Lista todos os passos de uma thread.
        
        Args:
            thread_id: ID da thread
        
        Returns:
            Lista de passos ordenados por step_index
        """
        if not self._driver:
            self.connect()
        
        query = """
        MATCH (thread:ExecutionThread {thread_id: $thread_id})
        MATCH (thread)-[:HAS_STEP]->(step:ExecutionStep)
        RETURN step
        ORDER BY step.step_index ASC
        """
        
        params = {"thread_id": thread_id}
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                
                steps = []
                for record in result:
                    step_node = record["step"]
                    step_data = {
                        "step_id": step_node["step_id"],
                        "step_index": step_node["step_index"],
                        "agent_data": step_node["agent_data"],
                        "created_at": step_node["created_at"],
                    }
                    steps.append(step_data)
                
                self.logger.info(f"Listados {len(steps)} passo(s) da thread {thread_id}")
                
                return steps
        
        except Exception as e:
            self.logger.error(f"Erro ao listar passos de execução: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def save_agent_memory(self, thread_id: str, step_index: int, 
                         agent_memories: Dict[str, Dict]) -> bool:
        """Salva memória de agentes para um passo.
        
        Args:
            thread_id: ID da thread
            step_index: Índice do passo
            agent_memories: Dicionário com memória por agente
        
        Returns:
            True se salvo com sucesso
        """
        if not self._driver:
            self.connect()
        
        query = """
        MATCH (thread:ExecutionThread {thread_id: $thread_id})
        MATCH (thread)-[:HAS_STEP {order: $step_index}]->(step:ExecutionStep)
        UNWIND $agent_memories as agent_mem
        CREATE (memory:AgentMemory {
            agent_id: agent_mem.agent_id,
            memory_data: agent_mem.memory_data,
            timestamp: $timestamp
        })
        CREATE (step)-[:HAS_AGENT_MEMORY]->(memory)
        """
        
        agent_memories_list = [
            {
                "agent_id": agent_id,
                "memory_data": memory_data,
            }
            for agent_id, memory_data in agent_memories.items()
        ]
        
        params = {
            "thread_id": thread_id,
            "step_index": step_index,
            "agent_memories": agent_memories_list,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            with self._driver.session() as session:
                session.run(query, params)
                self.logger.info(
                    f"Memória de {len(agent_memories)} agente(s) salva "
                    f"(thread: {thread_id}, step: {step_index})"
                )
                return True
        
        except Exception as e:
            self.logger.warning(f"Falha ao salvar memória de agentes: {e}")
            # Não falhar completamente, apenas log
            return False
