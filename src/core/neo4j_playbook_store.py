"""
Neo4j Playbook Store - Real Stats Implementation (Adaptive V2)

Gerencia persistência de playbooks, execuções e estatísticas reais.
Implementa atualização incremental (Welford's Algorithm) e controle de concorrência.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from dataclasses import dataclass, field
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class PlaybookSource:
    MANUAL = "MANUAL"
    LLM_GENERATED = "LLM_GENERATED"
    LEARNED = "LEARNED"

@dataclass
class Playbook:
    playbook_id: str
    title: str
    description: str
    pattern_type: str
    service_name: str
    status: str
    source: str
    steps: List[Dict[str, Any]]
    estimated_time_minutes: int
    automation_level: str
    risk_level: str
    prerequisites: List[str]
    success_criteria: List[str]
    rollback_procedure: str
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    executions_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

class PlaybookStatus:
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"

class Neo4jPlaybookStore:
    """Store para Playbooks e Execuções com agregação real de estatísticas."""
    
    def __init__(self, uri: str = "bolt://localhost:7687", auth: tuple = ("neo4j", "password")):
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_schema()
    
    def close(self):
        self.driver.close()
        
    def _init_schema(self):
        """Cria constraints e índices."""
        with self.driver.session() as session:
            # Constraints de unicidade
            session.run("CREATE CONSTRAINT playbook_id_unique IF NOT EXISTS FOR (p:Playbook) REQUIRE p.playbook_id IS UNIQUE")
            session.run("CREATE CONSTRAINT execution_id_unique IF NOT EXISTS FOR (e:PlaybookExecution) REQUIRE e.execution_id IS UNIQUE")
            
            # Índices para busca rápida
            session.run("CREATE INDEX playbook_status_idx IF NOT EXISTS FOR (p:Playbook) ON (p.status)")
            session.run("CREATE INDEX execution_timestamp_idx IF NOT EXISTS FOR (e:PlaybookExecution) ON (e.timestamp)")
            session.run("CREATE INDEX pattern_type_idx IF NOT EXISTS FOR (p:Pattern) ON (p.type)")

    def update_execution(self, execution_id: str, success: bool, duration: float, feedback: Optional[str] = None) -> bool:
        """Atualiza o resultado de uma execução e recalcula estatísticas do playbook.
        
        Usa atualização atômica e algoritmo de Welford para média e variância incremental.
        Garante consistência mesmo com concorrência.
        
        Args:
            execution_id: ID da execução
            success: Se foi bem sucedida
            duration: Duração em segundos
            feedback: Notas opcionais
            
        Returns:
            True se atualizado com sucesso
        """
        query = """
        MATCH (e:PlaybookExecution {execution_id: $execution_id})
        MATCH (e)-[:EXECUTED_BY]->(p:Playbook)
        
        // Atualizar execução
        SET e.success = $success,
            e.duration = $duration,
            e.feedback = $feedback,
            e.status = 'COMPLETED',
            e.completed_at = datetime()
        
        // Atualização Atômica Incremental (Welford's Algorithm)
        WITH p, e, $duration as x
        
        // 1. Contadores básicos
        SET p.total_executions = coalesce(p.total_executions, 0) + 1,
            p.success_count = coalesce(p.success_count, 0) + (CASE WHEN $success THEN 1 ELSE 0 END),
            p.failure_count = coalesce(p.failure_count, 0) + (CASE WHEN $success THEN 0 ELSE 1 END),
            p.last_executed_at = datetime()
            
        // 2. Média e Variância Incremental (Welford)
        // delta = x - mean
        // mean += delta / n
        // m2 += delta * (x - mean)
        WITH p, x, 
             coalesce(p.avg_duration, 0.0) as old_mean,
             coalesce(p.m2_duration, 0.0) as old_m2,
             p.total_executions as n
             
        WITH p, x, old_mean, old_m2, n,
             (x - old_mean) as delta
             
        WITH p, x, old_mean, old_m2, n, delta,
             (old_mean + delta / n) as new_mean
             
        SET p.avg_duration = new_mean,
            p.m2_duration = old_m2 + delta * (x - new_mean),
            p.success_rate = toFloat(p.success_count) / p.total_executions
            
        RETURN p.playbook_id as playbook_id, 
               p.success_rate as new_rate,
               p.avg_duration as new_avg,
               p.total_executions as total
        """
        
        try:
            with self.driver.session() as session:
                # Executa em transação implícita (autocommit) mas a query é atômica
                result = session.run(query, execution_id=execution_id, success=success, duration=duration, feedback=feedback)
                record = result.single()
                
                if record:
                    self.logger.info(
                        f"Stats updated for {record['playbook_id']}: "
                        f"Rate={record['new_rate']:.2f}, Avg={record['new_avg']:.2f}s, Total={record['total']}"
                    )
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Failed to update execution stats: {e}")
            return False

    def get_playbook_statistics(self, playbook_id: str) -> Dict[str, Any]:
        """Retorna estatísticas detalhadas de um playbook, incluindo desvio padrão."""
        query = """
        MATCH (p:Playbook {playbook_id: $playbook_id})
        RETURN p.total_executions as total,
               p.success_count as success,
               p.failure_count as failure,
               p.success_rate as rate,
               p.avg_duration as duration,
               p.m2_duration as m2,
               p.last_executed_at as last_run
        """
        with self.driver.session() as session:
            result = session.run(query, playbook_id=playbook_id)
            record = result.single()
            if record:
                data = dict(record)
                # Calcular desvio padrão se n > 1
                if data['total'] > 1 and data['m2'] is not None:
                    data['std_dev_duration'] = (data['m2'] / (data['total'] - 1)) ** 0.5
                else:
                    data['std_dev_duration'] = 0.0
                return data
            return {}

    def get_incident_trends(self, window_days: int = 7) -> Dict[str, Any]:
        """Calcula tendências reais de incidentes baseadas em execuções."""
        
        # 1. Volume total e taxa de sucesso na janela atual
        current_window_query = """
        MATCH (e:PlaybookExecution)
        WHERE e.timestamp >= datetime() - duration('P' + $days + 'D')
        RETURN count(e) as total,
               sum(CASE WHEN e.success THEN 1 ELSE 0 END) as success_count,
               avg(e.duration) as avg_duration
        """
        
        # 2. Volume na janela anterior (para cálculo de crescimento)
        previous_window_query = """
        MATCH (e:PlaybookExecution)
        WHERE e.timestamp >= datetime() - duration('P' + $double_days + 'D')
          AND e.timestamp < datetime() - duration('P' + $days + 'D')
        RETURN count(e) as total
        """
        
        # 3. Top serviços afetados
        top_services_query = """
        MATCH (e:PlaybookExecution)-[:TARGETS]->(s:Service)
        WHERE e.timestamp >= datetime() - duration('P' + $days + 'D')
        RETURN s.name as service, count(e) as incidents
        ORDER BY incidents DESC
        LIMIT 5
        """
        
        try:
            with self.driver.session() as session:
                curr = session.run(current_window_query, days=str(window_days)).single()
                prev = session.run(previous_window_query, days=str(window_days), double_days=str(window_days*2)).single()
                services = session.run(top_services_query, days=str(window_days)).data()
                
                current_total = curr['total'] if curr else 0
                prev_total = prev['total'] if prev else 0
                
                # Calcular Growth Rate
                if prev_total > 0:
                    growth_rate = (current_total - prev_total) / prev_total
                else:
                    growth_rate = 1.0 if current_total > 0 else 0.0
                
                return {
                    "current_window": {
                        "total_incidents": current_total,
                        "success_rate": (curr['success_count'] / current_total) if current_total > 0 else 0,
                        "avg_duration": curr['avg_duration']
                    },
                    "previous_window": {
                        "total_incidents": prev_total
                    },
                    "growth_rate": growth_rate,
                    "top_services": services
                }
        except Exception as e:
            self.logger.error(f"Failed to calculate trends: {e}")
            return {}

    # Métodos auxiliares para manter compatibilidade
    def get_playbook(self, playbook_id: str):
        query = "MATCH (p:Playbook {playbook_id: $id}) RETURN p"
        with self.driver.session() as session:
            result = session.run(query, id=playbook_id).single()
            return dict(result['p']) if result else None

    def store_playbook(self, playbook_data: Any):
        if hasattr(playbook_data, "__dataclass_fields__"):
            from dataclasses import asdict
            data = asdict(playbook_data)
        else:
            data = playbook_data.copy() if isinstance(playbook_data, dict) else playbook_data

        # Serialize nested structures for Neo4j compatibility
        for key in ["steps", "metadata", "prerequisites", "success_criteria"]:
            if key in data and (isinstance(data[key], (dict, list))):
                # Neo4j supports list of strings, but steps is list of dicts.
                # To be safe, we JSON dump the complex ones.
                if key == "steps" or key == "metadata":
                    data[key] = json.dumps(data[key])
                # prerequisites and success_criteria are usually list of strings, which Neo4j supports.
                # But if they contain objects, they will fail.

        query = """
        MERGE (p:Playbook {playbook_id: $data.playbook_id})
        SET p += $data, p.updated_at = datetime()
        """
        try:
            with self.driver.session() as session:
                session.run(query, data=data)
            return True
        except Exception as e:
            logger.error(f"Failed to store playbook: {e}")
            return False
