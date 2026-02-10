"""
Neo4j Playbook Store - Armazenar e curar Playbooks de Remediação

Implementa persistência de playbooks com workflow de curação:
- Playbooks gerados (PENDING_REVIEW)
- Playbooks aprovados (ACTIVE)
- Playbooks executados (EXECUTED)
- Feedback de execução
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import json

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

logger = logging.getLogger(__name__)


class PlaybookStatus(str, Enum):
    """Status de um playbook."""
    DRAFT = "DRAFT"                          # Rascunho (não testado)
    PENDING_REVIEW = "PENDING_REVIEW"        # Aguardando revisão humana
    ACTIVE = "ACTIVE"                        # Aprovado e ativo
    DEPRECATED = "DEPRECATED"                # Descontinuado
    ARCHIVED = "ARCHIVED"                    # Arquivado


class PlaybookSource(str, Enum):
    """Origem do playbook."""
    HUMAN_WRITTEN = "HUMAN_WRITTEN"          # Escrito por humano
    LLM_GENERATED = "LLM_GENERATED"          # Gerado por LLM
    HYBRID = "HYBRID"                        # Híbrido (LLM + humano)


@dataclass
class Playbook:
    """Playbook de remediação."""
    playbook_id: str
    title: str
    description: str
    pattern_type: str                        # LOG_METRIC, METRIC_METRIC, etc
    service_name: str
    status: PlaybookStatus
    source: PlaybookSource
    steps: List[Dict[str, Any]]              # Lista de passos
    estimated_time_minutes: int
    automation_level: str                    # MANUAL, ASSISTED, FULL
    risk_level: str                          # MINIMAL, LOW, MEDIUM, HIGH, CRITICAL
    prerequisites: List[str]
    success_criteria: List[str]
    rollback_procedure: str
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: Optional[str]
    approved_at: Optional[datetime]
    approved_by: Optional[str]
    executions_count: int
    success_count: int
    failure_count: int
    metadata: Dict[str, Any]


@dataclass
class PlaybookExecution:
    """Execução de um playbook."""
    execution_id: str
    playbook_id: str
    alert_fingerprint: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str                              # RUNNING, SUCCESS, FAILURE, PARTIAL
    duration_seconds: float
    steps_executed: int
    steps_total: int
    error_message: Optional[str]
    feedback: Optional[str]
    metadata: Dict[str, Any]


class Neo4jPlaybookStore:
    """
    Armazena e gerencia playbooks com workflow de curação.
    """
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j"
    ):
        """Inicializa store de playbooks."""
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        self.connected = False
        
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Inicializa conexão com Neo4j."""
        if GraphDatabase is None:
            logger.warning("neo4j package not installed. Playbook store disabled.")
            self.connected = False
            return
        
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                encrypted=False
            )
            
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            
            self.connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")
            self._create_indexes()
        
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.connected = False
    
    def _create_indexes(self):
        """Cria índices para playbooks."""
        if not self.connected:
            return
        
        queries = [
            "CREATE INDEX IF NOT EXISTS FOR (p:Playbook) ON (p.playbook_id)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Playbook) ON (p.pattern_type)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Playbook) ON (p.service_name)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Playbook) ON (p.status)",
            "CREATE INDEX IF NOT EXISTS FOR (e:PlaybookExecution) ON (e.execution_id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:PlaybookExecution) ON (e.playbook_id)",
        ]
        
        try:
            with self.driver.session(database=self.database) as session:
                for query in queries:
                    session.run(query)
            logger.info("Playbook indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    def store_playbook(self, playbook: Playbook) -> bool:
        """Armazena playbook no Neo4j."""
        if not self.connected:
            logger.warning("Neo4j not connected. Playbook not stored.")
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MERGE (p:Playbook {playbook_id: $playbook_id})
                SET 
                    p.title = $title,
                    p.description = $description,
                    p.pattern_type = $pattern_type,
                    p.service_name = $service_name,
                    p.status = $status,
                    p.source = $source,
                    p.steps = $steps,
                    p.estimated_time_minutes = $estimated_time_minutes,
                    p.automation_level = $automation_level,
                    p.risk_level = $risk_level,
                    p.prerequisites = $prerequisites,
                    p.success_criteria = $success_criteria,
                    p.rollback_procedure = $rollback_procedure,
                    p.created_at = $created_at,
                    p.created_by = $created_by,
                    p.updated_at = $updated_at,
                    p.updated_by = $updated_by,
                    p.approved_at = $approved_at,
                    p.approved_by = $approved_by,
                    p.executions_count = $executions_count,
                    p.success_count = $success_count,
                    p.failure_count = $failure_count,
                    p.metadata = $metadata
                RETURN p
                """
                
                session.run(
                    query,
                    playbook_id=playbook.playbook_id,
                    title=playbook.title,
                    description=playbook.description,
                    pattern_type=playbook.pattern_type,
                    service_name=playbook.service_name,
                    status=playbook.status.value,
                    source=playbook.source.value,
                    steps=json.dumps(playbook.steps),
                    estimated_time_minutes=playbook.estimated_time_minutes,
                    automation_level=playbook.automation_level,
                    risk_level=playbook.risk_level,
                    prerequisites=playbook.prerequisites,
                    success_criteria=playbook.success_criteria,
                    rollback_procedure=playbook.rollback_procedure,
                    created_at=playbook.created_at.isoformat(),
                    created_by=playbook.created_by,
                    updated_at=playbook.updated_at.isoformat(),
                    updated_by=playbook.updated_by,
                    approved_at=playbook.approved_at.isoformat() if playbook.approved_at else None,
                    approved_by=playbook.approved_by,
                    executions_count=playbook.executions_count,
                    success_count=playbook.success_count,
                    failure_count=playbook.failure_count,
                    metadata=json.dumps(playbook.metadata)
                )
            
            logger.info(f"Playbook stored: {playbook.playbook_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error storing playbook: {e}")
            return False
    
    def get_playbook(self, playbook_id: str) -> Optional[Dict[str, Any]]:
        """Recupera playbook por ID."""
        if not self.connected:
            return None
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Playbook {playbook_id: $playbook_id})
                RETURN p
                """
                
                result = session.run(query, playbook_id=playbook_id)
                record = result.single()
                
                if record:
                    return dict(record["p"])
                return None
        
        except Exception as e:
            logger.error(f"Error retrieving playbook: {e}")
            return None
    
    def get_active_playbooks_for_pattern(
        self,
        pattern_type: str,
        service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Recupera playbooks ativos para um padrão."""
        if not self.connected:
            return []
        
        try:
            with self.driver.session(database=self.database) as session:
                if service_name:
                    query = """
                    MATCH (p:Playbook {
                        pattern_type: $pattern_type,
                        service_name: $service_name,
                        status: 'ACTIVE'
                    })
                    RETURN p
                    ORDER BY p.success_count DESC
                    """
                    
                    result = session.run(
                        query,
                        pattern_type=pattern_type,
                        service_name=service_name
                    )
                else:
                    query = """
                    MATCH (p:Playbook {
                        pattern_type: $pattern_type,
                        status: 'ACTIVE'
                    })
                    RETURN p
                    ORDER BY p.success_count DESC
                    """
                    
                    result = session.run(query, pattern_type=pattern_type)
                
                return [dict(record["p"]) for record in result]
        
        except Exception as e:
            logger.error(f"Error retrieving playbooks: {e}")
            return []
    
    def get_pending_review_playbooks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Recupera playbooks aguardando revisão."""
        if not self.connected:
            return []
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Playbook {status: 'PENDING_REVIEW'})
                RETURN p
                ORDER BY p.created_at DESC
                LIMIT $limit
                """
                
                result = session.run(query, limit=limit)
                return [dict(record["p"]) for record in result]
        
        except Exception as e:
            logger.error(f"Error retrieving pending playbooks: {e}")
            return []
    
    def approve_playbook(
        self,
        playbook_id: str,
        approved_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """Aprova um playbook."""
        if not self.connected:
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Playbook {playbook_id: $playbook_id})
                SET 
                    p.status = 'ACTIVE',
                    p.approved_at = datetime(),
                    p.approved_by = $approved_by,
                    p.metadata.approval_notes = $notes
                RETURN p
                """
                
                session.run(
                    query,
                    playbook_id=playbook_id,
                    approved_by=approved_by,
                    notes=notes
                )
            
            logger.info(f"Playbook approved: {playbook_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error approving playbook: {e}")
            return False
    
    def reject_playbook(
        self,
        playbook_id: str,
        rejected_by: str,
        reason: str
    ) -> bool:
        """Rejeita um playbook."""
        if not self.connected:
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Playbook {playbook_id: $playbook_id})
                SET 
                    p.status = 'ARCHIVED',
                    p.metadata.rejection_reason = $reason,
                    p.metadata.rejected_by = $rejected_by,
                    p.metadata.rejected_at = datetime()
                RETURN p
                """
                
                session.run(
                    query,
                    playbook_id=playbook_id,
                    rejected_by=rejected_by,
                    reason=reason
                )
            
            logger.info(f"Playbook rejected: {playbook_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error rejecting playbook: {e}")
            return False
    
    def record_execution(self, execution: PlaybookExecution) -> bool:
        """Registra execução de playbook."""
        if not self.connected:
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                # Criar nó de execução
                exec_query = """
                CREATE (e:PlaybookExecution {
                    execution_id: $execution_id,
                    playbook_id: $playbook_id,
                    alert_fingerprint: $alert_fingerprint,
                    started_at: $started_at,
                    completed_at: $completed_at,
                    status: $status,
                    duration_seconds: $duration_seconds,
                    steps_executed: $steps_executed,
                    steps_total: $steps_total,
                    error_message: $error_message,
                    feedback: $feedback,
                    metadata: $metadata
                })
                RETURN e
                """
                
                session.run(
                    exec_query,
                    execution_id=execution.execution_id,
                    playbook_id=execution.playbook_id,
                    alert_fingerprint=execution.alert_fingerprint,
                    started_at=execution.started_at.isoformat(),
                    completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
                    status=execution.status,
                    duration_seconds=execution.duration_seconds,
                    steps_executed=execution.steps_executed,
                    steps_total=execution.steps_total,
                    error_message=execution.error_message,
                    feedback=execution.feedback,
                    metadata=json.dumps(execution.metadata)
                )
                
                # Atualizar estatísticas do playbook
                if execution.status == "SUCCESS":
                    stats_query = """
                    MATCH (p:Playbook {playbook_id: $playbook_id})
                    SET 
                        p.executions_count = p.executions_count + 1,
                        p.success_count = p.success_count + 1
                    RETURN p
                    """
                elif execution.status == "FAILURE":
                    stats_query = """
                    MATCH (p:Playbook {playbook_id: $playbook_id})
                    SET 
                        p.executions_count = p.executions_count + 1,
                        p.failure_count = p.failure_count + 1
                    RETURN p
                    """
                else:
                    stats_query = """
                    MATCH (p:Playbook {playbook_id: $playbook_id})
                    SET p.executions_count = p.executions_count + 1
                    RETURN p
                    """
                
                session.run(stats_query, playbook_id=execution.playbook_id)
            
            logger.info(f"Execution recorded: {execution.execution_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error recording execution: {e}")
            return False
    
    def get_playbook_statistics(self, playbook_id: str) -> Dict[str, Any]:
        """Calcula estatísticas de um playbook."""
        if not self.connected:
            return {}
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Playbook {playbook_id: $playbook_id})
                OPTIONAL MATCH (e:PlaybookExecution {playbook_id: $playbook_id})
                RETURN 
                    p.executions_count as total_executions,
                    p.success_count as successes,
                    p.failure_count as failures,
                    COUNT(e) as recorded_executions,
                    AVG(CASE WHEN e.status = 'SUCCESS' THEN e.duration_seconds ELSE NULL END) as avg_success_time,
                    AVG(CASE WHEN e.status = 'FAILURE' THEN e.duration_seconds ELSE NULL END) as avg_failure_time
                """
                
                result = session.run(query, playbook_id=playbook_id).single()
                
                if result:
                    total = result["total_executions"] or 0
                    successes = result["successes"] or 0
                    
                    return {
                        "playbook_id": playbook_id,
                        "total_executions": total,
                        "successes": successes,
                        "failures": result["failures"] or 0,
                        "success_rate": (successes / total * 100) if total > 0 else 0,
                        "avg_success_time": result["avg_success_time"] or 0,
                        "avg_failure_time": result["avg_failure_time"] or 0
                    }
                
                return {}
        
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {}
    
    def close(self):
        """Fecha conexão."""
        if self.driver:
            self.driver.close()
            self.connected = False
            logger.info("Neo4j connection closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
