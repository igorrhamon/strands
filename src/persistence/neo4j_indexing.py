"""
Neo4j Indexing - Gerenciamento Automático de Índices

Cria índices automaticamente ao iniciar a aplicação para otimizar buscas.
Segue best practices de Neo4j para performance em produção.

Padrão: Initialization Pattern (inspiração Flyway, Alembic)
Resiliência: Idempotente, sem falha se índice já existe
"""

import logging
from typing import List, Dict, Optional
from neo4j import Driver

logger = logging.getLogger(__name__)


class Neo4jIndexManager:
    """Gerenciador de índices do Neo4j.
    
    Responsabilidades:
    1. Criar índices automaticamente
    2. Verificar existência de índices
    3. Otimizar queries críticas
    4. Manter histórico de índices
    """
    
    def __init__(self, driver: Driver):
        """Inicializa o gerenciador.
        
        Args:
            driver: Driver do Neo4j
        """
        self.driver = driver
        self.logger = logging.getLogger("neo4j_index_manager")
    
    def initialize_indexes(self) -> Dict[str, bool]:
        """Cria todos os índices necessários.
        
        Retorna:
            Dicionário com status de cada índice
        """
        indexes = [
            # ExecutionThread indexes
            {
                "name": "idx_execution_thread_id",
                "label": "ExecutionThread",
                "property": "thread_id",
                "description": "Busca rápida de threads por ID",
            },
            # ExecutionStep indexes
            {
                "name": "idx_execution_step_id",
                "label": "ExecutionStep",
                "property": "step_id",
                "description": "Busca rápida de passos por ID",
            },
            {
                "name": "idx_execution_step_index",
                "label": "ExecutionStep",
                "property": "step_index",
                "description": "Busca rápida de passos por índice",
            },
            {
                "name": "idx_execution_step_timestamp",
                "label": "ExecutionStep",
                "property": "created_at",
                "description": "Busca rápida de passos por timestamp",
            },
            # Checkpoint indexes
            {
                "name": "idx_checkpoint_id",
                "label": "Checkpoint",
                "property": "checkpoint_id",
                "description": "Busca rápida de checkpoints por ID",
            },
            {
                "name": "idx_checkpoint_thread_step",
                "label": "Checkpoint",
                "properties": ["thread_id", "step"],
                "description": "Busca rápida de checkpoints por thread e step",
            },
            {
                "name": "idx_checkpoint_timestamp",
                "label": "Checkpoint",
                "property": "created_at",
                "description": "Busca rápida de checkpoints por timestamp",
            },
            # AgentMemory indexes
            {
                "name": "idx_agent_memory_id",
                "label": "AgentMemory",
                "property": "agent_id",
                "description": "Busca rápida de memória por agente",
            },
            {
                "name": "idx_agent_memory_timestamp",
                "label": "AgentMemory",
                "property": "timestamp",
                "description": "Busca rápida de memória por timestamp",
            },
            # Decision indexes
            {
                "name": "idx_decision_id",
                "label": "Decision",
                "property": "decision_id",
                "description": "Busca rápida de decisões por ID",
            },
            {
                "name": "idx_decision_timestamp",
                "label": "Decision",
                "property": "timestamp",
                "description": "Busca rápida de decisões por timestamp",
            },
            {
                "name": "idx_decision_state",
                "label": "Decision",
                "property": "state",
                "description": "Busca rápida de decisões por estado",
            },
        ]
        
        results = {}
        
        for index_config in indexes:
            try:
                success = self._create_index(index_config)
                results[index_config["name"]] = success
                
                if success:
                    self.logger.info(
                        f"Índice criado: {index_config['name']} "
                        f"({index_config['description']})"
                    )
                else:
                    self.logger.info(
                        f"Índice já existe: {index_config['name']}"
                    )
            
            except Exception as e:
                self.logger.error(
                    f"Erro ao criar índice {index_config['name']}: {e}"
                )
                results[index_config["name"]] = False
        
        return results
    
    def _create_index(self, index_config: Dict) -> bool:
        """Cria um índice específico.
        
        Args:
            index_config: Configuração do índice
        
        Returns:
            True se criado, False se já existe
        """
        label = index_config["label"]
        
        # Suportar índices simples e compostos
        if "property" in index_config:
            properties = [index_config["property"]]
        else:
            properties = index_config.get("properties", [])
        
        if not properties:
            raise ValueError(f"Índice {index_config['name']} sem propriedades")
        
        # Construir query
        properties_str = ", ".join([f"n.{prop}" for prop in properties])
        query = f"CREATE INDEX {index_config['name']} FOR (n:{label}) ON ({properties_str})"
        
        with self.driver.session() as session:
            try:
                session.run(query)
                return True
            except Exception as e:
                # Verificar se é erro de índice já existente
                if "already exists" in str(e) or "already indexed" in str(e):
                    return False
                raise
    
    def list_indexes(self) -> List[Dict]:
        """Lista todos os índices.
        
        Returns:
            Lista de índices
        """
        query = "SHOW INDEXES"
        
        with self.driver.session() as session:
            result = session.run(query)
            indexes = [dict(record) for record in result]
            return indexes
    
    def get_index_stats(self) -> Dict[str, Dict]:
        """Obtém estatísticas dos índices.
        
        Returns:
            Dicionário com estatísticas
        """
        query = """
        SHOW INDEXES YIELD name, labelsOrTypes, properties, state, type
        RETURN {
            name: name,
            labels: labelsOrTypes,
            properties: properties,
            state: state,
            type: type
        } as index
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            stats = {}
            
            for record in result:
                index = record["index"]
                stats[index["name"]] = index
            
            return stats
    
    def rebuild_index(self, index_name: str) -> bool:
        """Reconstrói um índice.
        
        Args:
            index_name: Nome do índice
        
        Returns:
            True se reconstruído com sucesso
        """
        query = f"CALL db.index.fulltext.rebuild('{index_name}')"
        
        with self.driver.session() as session:
            try:
                session.run(query)
                self.logger.info(f"Índice reconstruído: {index_name}")
                return True
            except Exception as e:
                self.logger.error(f"Erro ao reconstruir índice {index_name}: {e}")
                return False
    
    def drop_index(self, index_name: str) -> bool:
        """Remove um índice.
        
        Args:
            index_name: Nome do índice
        
        Returns:
            True se removido com sucesso
        """
        query = f"DROP INDEX {index_name}"
        
        with self.driver.session() as session:
            try:
                session.run(query)
                self.logger.info(f"Índice removido: {index_name}")
                return True
            except Exception as e:
                self.logger.error(f"Erro ao remover índice {index_name}: {e}")
                return False
    
    def analyze_query_performance(self, query: str) -> Dict:
        """Analisa performance de uma query.
        
        Args:
            query: Query a analisar
        
        Returns:
            Estatísticas de performance
        """
        explain_query = f"EXPLAIN {query}"
        
        with self.driver.session() as session:
            result = session.run(explain_query)
            plan = result.plan
            
            return {
                "query": query,
                "operators": plan.get("operatorTypes", []),
                "arguments": plan.get("arguments", {}),
            }
