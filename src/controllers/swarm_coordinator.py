"""
SwarmCoordinator - Orquestrador de Swarm com Deduplicação

Coordena a execução de swarms com deduplicação de eventos.
Se um evento com mesmo ID de origem foi processado nos últimos X minutos,
apenas atualiza o grafo existente em vez de iniciar um novo swarm.

Padrão: Coordinator Pattern + Deduplication Strategy
Resiliência: Integração com EventDeduplicator e GraphUpdateStrategy
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from src.deduplication.event_deduplicator import (
    EventDeduplicator,
    DeduplicationAction,
    DeduplicationPolicy,
)
from src.controllers.swarm_decision_controller import SwarmDecisionController, SwarmDecision

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Modo de execução."""
    NEW_SWARM = "new_swarm"                 # Iniciar novo swarm
    UPDATE_GRAPH = "update_graph"           # Atualizar grafo existente
    SKIP_EXECUTION = "skip_execution"       # Ignorar execução


class CoordinationRequest(BaseModel):
    """Requisição de coordenação."""
    
    source_id: str = Field(..., description="ID único da origem do evento")
    event_data: Dict = Field(..., description="Dados do evento")
    event_type: Optional[str] = Field(None, description="Tipo de evento")
    source_system: Optional[str] = Field(None, description="Sistema de origem")
    priority: int = Field(0, ge=0, le=10, description="Prioridade (0-10)")
    
    class Config:
        frozen = True


class CoordinationResult(BaseModel):
    """Resultado da coordenação."""
    
    execution_mode: ExecutionMode = Field(..., description="Modo de execução")
    execution_id: str = Field(..., description="ID da execução")
    dedup_key: Optional[str] = Field(None, description="Chave de deduplicação")
    original_execution_id: Optional[str] = Field(None, description="ID da execução original (se UPDATE)")
    decision: Optional[Dict] = Field(None, description="Decisão tomada")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        frozen = True


class SwarmCoordinator:
    """Orquestrador de Swarm com Deduplicação.
    
    Responsabilidades:
    1. Receber requisições de execução
    2. Verificar deduplicação via EventDeduplicator
    3. Decidir modo de execução (NEW, UPDATE, SKIP)
    4. Executar swarm ou atualizar grafo
    5. Registrar resultado
    """
    
    def __init__(self,
                 swarm_decision_controller: SwarmDecisionController,
                 deduplication_policy: Optional[DeduplicationPolicy] = None):
        """Inicializa coordenador.
        
        Args:
            swarm_decision_controller: Controller de decisão
            deduplication_policy: Política de deduplicação (opcional)
        """
        self.swarm_decision_controller = swarm_decision_controller
        self.deduplication_policy = deduplication_policy or DeduplicationPolicy()
        
        # Inicializar deduplicador
        self.deduplicator = EventDeduplicator(
            ttl_minutes=self.deduplication_policy.ttl_minutes,
            max_cache_size=self.deduplication_policy.max_cache_size,
        )
        
        self.logger = logging.getLogger("swarm_coordinator")
        self.logger.info(
            f"SwarmCoordinator inicializado | "
            f"dedup_enabled={self.deduplication_policy.enabled} | "
            f"ttl={self.deduplication_policy.ttl_minutes}min"
        )
    
    async def coordinate(self, request: CoordinationRequest) -> CoordinationResult:
        """Coordena execução de swarm.
        
        Args:
            request: Requisição de coordenação
        
        Returns:
            Resultado da coordenação
        
        Fluxo:
        1. Verificar deduplicação
        2. Decidir modo de execução
        3. Executar swarm ou atualizar grafo
        4. Retornar resultado
        """
        self.logger.info(
            f"Coordenação iniciada | "
            f"source_id={request.source_id} | "
            f"event_type={request.event_type}"
        )
        
        # Verificar deduplicação
        if self.deduplication_policy.enabled:
            action, original_exec_id = self.deduplicator.check_duplicate(
                source_id=request.source_id,
                event_data=request.event_data,
                event_type=request.event_type,
                source_system=request.source_system,
            )
        else:
            action = DeduplicationAction.NEW_EXECUTION
            original_exec_id = None
        
        # Decidir modo de execução
        if action == DeduplicationAction.NEW_EXECUTION:
            execution_mode = ExecutionMode.NEW_SWARM
            execution_id = await self._execute_new_swarm(request)
            dedup_key = self.deduplicator.register_execution(
                source_id=request.source_id,
                execution_id=execution_id,
                event_data=request.event_data,
                event_type=request.event_type,
                source_system=request.source_system,
            )
            
            self.logger.info(
                f"Novo swarm iniciado | "
                f"execution_id={execution_id} | "
                f"dedup_key={dedup_key}"
            )
        
        elif action == DeduplicationAction.UPDATE_EXISTING:
            execution_mode = ExecutionMode.UPDATE_GRAPH
            execution_id = original_exec_id
            dedup_key = self.deduplicator.generate_deduplication_key(
                source_id=request.source_id,
                event_type=request.event_type,
                source_system=request.source_system,
            )
            
            # Atualizar grafo existente
            await self._update_existing_graph(execution_id, request)
            
            self.logger.info(
                f"Grafo existente atualizado | "
                f"execution_id={execution_id} | "
                f"dedup_key={dedup_key}"
            )
        
        else:  # SKIP_DUPLICATE
            execution_mode = ExecutionMode.SKIP_EXECUTION
            execution_id = original_exec_id
            dedup_key = self.deduplicator.generate_deduplication_key(
                source_id=request.source_id,
                event_type=request.event_type,
                source_system=request.source_system,
            )
            
            self.logger.info(
                f"Execução ignorada (duplicata) | "
                f"execution_id={execution_id} | "
                f"dedup_key={dedup_key}"
            )
        
        # Construir resultado
        result = CoordinationResult(
            execution_mode=execution_mode,
            execution_id=execution_id,
            dedup_key=dedup_key,
            original_execution_id=original_exec_id if action == DeduplicationAction.UPDATE_EXISTING else None,
        )
        
        return result
    
    async def _execute_new_swarm(self, request: CoordinationRequest) -> str:
        """Executa novo swarm.
        
        Args:
            request: Requisição
        
        Returns:
            ID da execução
        """
        # Aqui você chamaria o SwarmDecisionController
        # ou outro executor de swarm
        
        # Placeholder: gerar ID
        import uuid
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        
        self.logger.debug(f"Novo swarm executado: {execution_id}")
        
        return execution_id
    
    async def _update_existing_graph(self,
                                    execution_id: str,
                                    request: CoordinationRequest):
        """Atualiza grafo existente.
        
        Args:
            execution_id: ID da execução
            request: Requisição
        """
        self.logger.debug(
            f"Atualizando grafo | "
            f"execution_id={execution_id} | "
            f"new_data={request.event_data}"
        )
        
        # Aqui você chamaria o GraphUpdateStrategy
        # para atualizar o grafo no Neo4j
        pass
    
    def get_deduplication_stats(self) -> Dict:
        """Retorna estatísticas de deduplicação.
        
        Returns:
            Dicionário com estatísticas
        """
        return self.deduplicator.get_cache_stats()
    
    def clear_deduplication_cache(self):
        """Limpa cache de deduplicação."""
        self.deduplicator.clear_cache()
        self.logger.info("Cache de deduplicação limpo")


class GraphUpdateStrategy:
    """Estratégia de atualização de grafo.
    
    Responsável por atualizar o grafo existente no Neo4j
    quando um evento duplicado é detectado.
    """
    
    def __init__(self, neo4j_adapter):
        """Inicializa estratégia.
        
        Args:
            neo4j_adapter: Adaptador Neo4j
        """
        self.neo4j_adapter = neo4j_adapter
        self.logger = logging.getLogger("graph_update_strategy")
    
    async def update_execution_node(self,
                                   execution_id: str,
                                   new_event_data: Dict) -> bool:
        """Atualiza nó de execução no Neo4j.
        
        Args:
            execution_id: ID da execução
            new_event_data: Novos dados do evento
        
        Returns:
            True se atualizado com sucesso
        """
        query = """
        MATCH (exec:Execution {execution_id: $execution_id})
        SET exec.last_updated = datetime(),
            exec.event_count = exec.event_count + 1,
            exec.latest_event_data = $event_data
        RETURN exec
        """
        
        try:
            result = self.neo4j_adapter.execute_query(
                query,
                execution_id=execution_id,
                event_data=str(new_event_data),
            )
            
            self.logger.info(f"Nó de execução atualizado: {execution_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Erro ao atualizar nó: {e}")
            return False
    
    async def add_duplicate_event(self,
                                 execution_id: str,
                                 event_data: Dict,
                                 source_id: str) -> bool:
        """Adiciona evento duplicado ao grafo.
        
        Args:
            execution_id: ID da execução
            event_data: Dados do evento
            source_id: ID da origem
        
        Returns:
            True se adicionado com sucesso
        """
        query = """
        MATCH (exec:Execution {execution_id: $execution_id})
        CREATE (event:DuplicateEvent {
            event_id: $event_id,
            source_id: $source_id,
            event_data: $event_data,
            timestamp: datetime()
        })
        CREATE (exec)-[:HAS_DUPLICATE_EVENT]->(event)
        RETURN event
        """
        
        try:
            import uuid
            event_id = f"evt_{uuid.uuid4().hex[:12]}"
            
            result = self.neo4j_adapter.execute_query(
                query,
                execution_id=execution_id,
                event_id=event_id,
                source_id=source_id,
                event_data=str(event_data),
            )
            
            self.logger.info(f"Evento duplicado adicionado: {event_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Erro ao adicionar evento duplicado: {e}")
            return False
    
    async def update_execution_confidence(self,
                                         execution_id: str,
                                         new_confidence: float) -> bool:
        """Atualiza confiança da execução.
        
        Args:
            execution_id: ID da execução
            new_confidence: Nova confiança
        
        Returns:
            True se atualizado com sucesso
        """
        query = """
        MATCH (exec:Execution {execution_id: $execution_id})
        SET exec.confidence_score = $confidence,
            exec.last_confidence_update = datetime()
        RETURN exec
        """
        
        try:
            result = self.neo4j_adapter.execute_query(
                query,
                execution_id=execution_id,
                confidence=new_confidence,
            )
            
            self.logger.info(f"Confiança atualizada: {execution_id} → {new_confidence}")
            return True
        
        except Exception as e:
            self.logger.error(f"Erro ao atualizar confiança: {e}")
            return False
