"""
Neo4j Persistence Layer - Armazenar padrões de correlação e histórico

Implementa persistência em Neo4j para:
- Padrões de correlação detectados
- Histórico de correlações
- Relacionamentos entre alertas e padrões
- Análise de tendências
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
import json
from enum import Enum

try:
    from neo4j import GraphDatabase, Session, Transaction
except ImportError:
    GraphDatabase = None
    Session = None
    Transaction = None

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Tipos de padrão de correlação."""
    LOG_METRIC = "LOG_METRIC_CORRELATION"
    METRIC_METRIC = "METRIC_METRIC_CORRELATION"
    TEMPORAL = "TEMPORAL_CORRELATION"
    TRACE_EVENT = "TRACE_EVENT_CORRELATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class CorrelationPattern:
    """Padrão de correlação armazenado."""
    pattern_id: str
    pattern_type: PatternType
    service_name: str
    confidence: float
    correlation_coefficient: float
    p_value: float
    lag_offset: int
    significance: str
    description: str
    first_detected: datetime
    last_detected: datetime
    occurrences: int
    metadata: Dict[str, Any]


@dataclass
class CorrelationEvent:
    """Evento de correlação detectada."""
    event_id: str
    pattern_id: str
    alert_fingerprint: str
    timestamp: datetime
    confidence: float
    evidence_count: int
    suggested_actions: int
    metadata: Dict[str, Any]


class Neo4jPersistence:
    """
    Camada de persistência em Neo4j para padrões de correlação.
    """
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j"
    ):
        """
        Inicializa conexão com Neo4j.
        
        Args:
            uri: URI do servidor Neo4j
            username: Usuário Neo4j
            password: Senha Neo4j
            database: Nome do banco de dados
        """
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
            logger.warning("neo4j package not installed. Persistence disabled.")
            self.connected = False
            return
        
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                encrypted=False
            )
            
            # Testar conexão
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            
            self.connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")
            self._create_indexes()
        
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.connected = False
    
    def _create_indexes(self):
        """Cria índices para melhor performance."""
        if not self.connected:
            return
        
        queries = [
            "CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.pattern_id)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.service_name)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.pattern_type)",
            "CREATE INDEX IF NOT EXISTS FOR (e:CorrelationEvent) ON (e.event_id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:CorrelationEvent) ON (e.pattern_id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:CorrelationEvent) ON (e.timestamp)",
            "CREATE INDEX IF NOT EXISTS FOR (a:Alert) ON (a.fingerprint)",
        ]
        
        try:
            with self.driver.session(database=self.database) as session:
                for query in queries:
                    session.run(query)
            logger.info("Neo4j indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    def store_pattern(self, pattern: CorrelationPattern) -> bool:
        """
        Armazena padrão de correlação no Neo4j.
        
        Args:
            pattern: Padrão a armazenar
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.connected:
            logger.warning("Neo4j not connected. Pattern not stored.")
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MERGE (p:Pattern {pattern_id: $pattern_id})
                SET 
                    p.pattern_type = $pattern_type,
                    p.service_name = $service_name,
                    p.confidence = $confidence,
                    p.correlation_coefficient = $correlation_coefficient,
                    p.p_value = $p_value,
                    p.lag_offset = $lag_offset,
                    p.significance = $significance,
                    p.description = $description,
                    p.first_detected = $first_detected,
                    p.last_detected = $last_detected,
                    p.occurrences = $occurrences,
                    p.metadata = $metadata,
                    p.updated_at = datetime()
                RETURN p
                """
                
                session.run(
                    query,
                    pattern_id=pattern.pattern_id,
                    pattern_type=pattern.pattern_type.value,
                    service_name=pattern.service_name,
                    confidence=pattern.confidence,
                    correlation_coefficient=pattern.correlation_coefficient,
                    p_value=pattern.p_value,
                    lag_offset=pattern.lag_offset,
                    significance=pattern.significance,
                    description=pattern.description,
                    first_detected=pattern.first_detected.isoformat(),
                    last_detected=pattern.last_detected.isoformat(),
                    occurrences=pattern.occurrences,
                    metadata=json.dumps(pattern.metadata)
                )
            
            logger.info(f"Pattern stored: {pattern.pattern_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error storing pattern: {e}")
            return False
    
    def store_event(self, event: CorrelationEvent) -> bool:
        """
        Armazena evento de correlação.
        
        Args:
            event: Evento a armazenar
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.connected:
            logger.warning("Neo4j not connected. Event not stored.")
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                # Criar evento
                event_query = """
                CREATE (e:CorrelationEvent {
                    event_id: $event_id,
                    pattern_id: $pattern_id,
                    alert_fingerprint: $alert_fingerprint,
                    timestamp: $timestamp,
                    confidence: $confidence,
                    evidence_count: $evidence_count,
                    suggested_actions: $suggested_actions,
                    metadata: $metadata
                })
                RETURN e
                """
                
                session.run(
                    event_query,
                    event_id=event.event_id,
                    pattern_id=event.pattern_id,
                    alert_fingerprint=event.alert_fingerprint,
                    timestamp=event.timestamp.isoformat(),
                    confidence=event.confidence,
                    evidence_count=event.evidence_count,
                    suggested_actions=event.suggested_actions,
                    metadata=json.dumps(event.metadata)
                )
                
                # Relacionar evento com padrão
                link_query = """
                MATCH (e:CorrelationEvent {event_id: $event_id})
                MATCH (p:Pattern {pattern_id: $pattern_id})
                CREATE (e)-[:DETECTED_PATTERN]->(p)
                RETURN e, p
                """
                
                session.run(
                    link_query,
                    event_id=event.event_id,
                    pattern_id=event.pattern_id
                )
                
                # Relacionar evento com alerta
                alert_query = """
                MATCH (e:CorrelationEvent {event_id: $event_id})
                MERGE (a:Alert {fingerprint: $alert_fingerprint})
                CREATE (e)-[:TRIGGERED_BY]->(a)
                RETURN e, a
                """
                
                session.run(
                    alert_query,
                    event_id=event.event_id,
                    alert_fingerprint=event.alert_fingerprint
                )
            
            logger.info(f"Event stored: {event.event_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error storing event: {e}")
            return False
    
    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera padrão do Neo4j.
        
        Args:
            pattern_id: ID do padrão
        
        Returns:
            Dados do padrão ou None
        """
        if not self.connected:
            return None
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Pattern {pattern_id: $pattern_id})
                RETURN p
                """
                
                result = session.run(query, pattern_id=pattern_id)
                record = result.single()
                
                if record:
                    return dict(record["p"])
                return None
        
        except Exception as e:
            logger.error(f"Error retrieving pattern: {e}")
            return None
    
    def get_patterns_by_service(
        self,
        service_name: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Recupera padrões de um serviço.
        
        Args:
            service_name: Nome do serviço
            limit: Limite de resultados
        
        Returns:
            Lista de padrões
        """
        if not self.connected:
            return []
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Pattern {service_name: $service_name})
                RETURN p
                ORDER BY p.last_detected DESC
                LIMIT $limit
                """
                
                result = session.run(
                    query,
                    service_name=service_name,
                    limit=limit
                )
                
                return [dict(record["p"]) for record in result]
        
        except Exception as e:
            logger.error(f"Error retrieving patterns: {e}")
            return []
    
    def get_patterns_by_type(
        self,
        pattern_type: PatternType,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Recupera padrões por tipo.
        
        Args:
            pattern_type: Tipo de padrão
            limit: Limite de resultados
        
        Returns:
            Lista de padrões
        """
        if not self.connected:
            return []
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (p:Pattern {pattern_type: $pattern_type})
                RETURN p
                ORDER BY p.confidence DESC
                LIMIT $limit
                """
                
                result = session.run(
                    query,
                    pattern_type=pattern_type.value,
                    limit=limit
                )
                
                return [dict(record["p"]) for record in result]
        
        except Exception as e:
            logger.error(f"Error retrieving patterns by type: {e}")
            return []
    
    def get_correlation_history(
        self,
        pattern_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Recupera histórico de correlações de um padrão.
        
        Args:
            pattern_id: ID do padrão
            days: Número de dias para retroceder
        
        Returns:
            Lista de eventos de correlação
        """
        if not self.connected:
            return []
        
        try:
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (e:CorrelationEvent)-[:DETECTED_PATTERN]->(p:Pattern {pattern_id: $pattern_id})
                WHERE e.timestamp >= $cutoff_date
                RETURN e
                ORDER BY e.timestamp DESC
                """
                
                result = session.run(
                    query,
                    pattern_id=pattern_id,
                    cutoff_date=cutoff_date
                )
                
                return [dict(record["e"]) for record in result]
        
        except Exception as e:
            logger.error(f"Error retrieving correlation history: {e}")
            return []
    
    def get_alert_correlations(
        self,
        alert_fingerprint: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Recupera todas as correlações de um alerta.
        
        Args:
            alert_fingerprint: Fingerprint do alerta
            limit: Limite de resultados
        
        Returns:
            Lista de eventos de correlação
        """
        if not self.connected:
            return []
        
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (e:CorrelationEvent)-[:TRIGGERED_BY]->(a:Alert {fingerprint: $alert_fingerprint})
                RETURN e
                ORDER BY e.timestamp DESC
                LIMIT $limit
                """
                
                result = session.run(
                    query,
                    alert_fingerprint=alert_fingerprint,
                    limit=limit
                )
                
                return [dict(record["e"]) for record in result]
        
        except Exception as e:
            logger.error(f"Error retrieving alert correlations: {e}")
            return []
    
    def get_pattern_statistics(
        self,
        service_name: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calcula estatísticas de padrões.
        
        Args:
            service_name: Filtrar por serviço (opcional)
            days: Número de dias
        
        Returns:
            Dicionário com estatísticas
        """
        if not self.connected:
            return {}
        
        try:
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            with self.driver.session(database=self.database) as session:
                # Contar padrões
                if service_name:
                    pattern_query = """
                    MATCH (p:Pattern {service_name: $service_name})
                    RETURN COUNT(p) as count
                    """
                    pattern_result = session.run(
                        pattern_query,
                        service_name=service_name
                    ).single()
                else:
                    pattern_query = """
                    MATCH (p:Pattern)
                    RETURN COUNT(p) as count
                    """
                    pattern_result = session.run(pattern_query).single()
                
                # Contar eventos
                if service_name:
                    event_query = """
                    MATCH (e:CorrelationEvent)-[:DETECTED_PATTERN]->(p:Pattern {service_name: $service_name})
                    WHERE e.timestamp >= $cutoff_date
                    RETURN COUNT(e) as count, AVG(e.confidence) as avg_confidence
                    """
                    event_result = session.run(
                        event_query,
                        service_name=service_name,
                        cutoff_date=cutoff_date
                    ).single()
                else:
                    event_query = """
                    MATCH (e:CorrelationEvent)
                    WHERE e.timestamp >= $cutoff_date
                    RETURN COUNT(e) as count, AVG(e.confidence) as avg_confidence
                    """
                    event_result = session.run(
                        event_query,
                        cutoff_date=cutoff_date
                    ).single()
                
                return {
                    "total_patterns": pattern_result["count"],
                    "events_last_n_days": event_result["count"],
                    "avg_confidence": event_result["avg_confidence"] or 0.0,
                    "period_days": days,
                    "service_name": service_name
                }
        
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {}
    
    def close(self):
        """Fecha conexão com Neo4j."""
        if self.driver:
            self.driver.close()
            self.connected = False
            logger.info("Neo4j connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
