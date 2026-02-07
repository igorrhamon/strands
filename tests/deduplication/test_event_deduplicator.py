"""
Testes - Event Deduplicator

Testa lógica de deduplicação de eventos.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock

from src.deduplication.event_deduplicator import (
    EventDeduplicator,
    DeduplicationAction,
    DeduplicationPolicy,
    DeduplicationEntry,
)
from src.controllers.swarm_coordinator import (
    SwarmCoordinator,
    CoordinationRequest,
    ExecutionMode,
)


class TestEventDeduplicator:
    """Testes para EventDeduplicator."""
    
    @pytest.fixture
    def deduplicator(self):
        """Cria deduplicador."""
        return EventDeduplicator(ttl_minutes=30, max_cache_size=1000)
    
    def test_generate_deduplication_key(self, deduplicator):
        """Testa geração de chave de deduplicação."""
        key1 = deduplicator.generate_deduplication_key("alert_123")
        key2 = deduplicator.generate_deduplication_key("alert_123")
        key3 = deduplicator.generate_deduplication_key("alert_456")
        
        # Mesma origem → mesma chave
        assert key1 == key2
        
        # Origem diferente → chave diferente
        assert key1 != key3
        
        # Formato correto
        assert key1.startswith("dedup_")
        assert len(key1) == 21  # "dedup_" + 16 caracteres
    
    def test_generate_deduplication_key_with_type_and_system(self, deduplicator):
        """Testa geração de chave com tipo e sistema."""
        key1 = deduplicator.generate_deduplication_key(
            "alert_123",
            event_type="security_alert",
            source_system="prometheus"
        )
        
        key2 = deduplicator.generate_deduplication_key(
            "alert_123",
            event_type="security_alert",
            source_system="prometheus"
        )
        
        # Mesmos parâmetros → mesma chave
        assert key1 == key2
    
    def test_check_duplicate_new_event(self, deduplicator):
        """Testa detecção de novo evento."""
        action, original_exec_id = deduplicator.check_duplicate(
            source_id="alert_123",
            event_data={"severity": "high"}
        )
        
        assert action == DeduplicationAction.NEW_EXECUTION
        assert original_exec_id is None
    
    def test_check_duplicate_duplicate_event(self, deduplicator):
        """Testa detecção de evento duplicado."""
        # Primeiro evento
        action1, _ = deduplicator.check_duplicate(
            source_id="alert_123",
            event_data={"severity": "high"}
        )
        assert action1 == DeduplicationAction.NEW_EXECUTION
        
        # Registrar execução
        deduplicator.register_execution(
            source_id="alert_123",
            execution_id="exec_123",
            event_data={"severity": "high"}
        )
        
        # Segundo evento (duplicado)
        action2, original_exec_id = deduplicator.check_duplicate(
            source_id="alert_123",
            event_data={"severity": "high"}
        )
        
        assert action2 == DeduplicationAction.UPDATE_EXISTING
        assert original_exec_id == "exec_123"
    
    def test_register_execution(self, deduplicator):
        """Testa registro de execução."""
        dedup_key = deduplicator.register_execution(
            source_id="alert_123",
            execution_id="exec_123",
            event_data={"severity": "high"}
        )
        
        assert dedup_key.startswith("dedup_")
        assert dedup_key in deduplicator.cache
        
        entry = deduplicator.cache[dedup_key]
        assert entry.execution_id == "exec_123"
        assert entry.event_count == 1
    
    def test_update_entry(self, deduplicator):
        """Testa atualização de entrada."""
        dedup_key = deduplicator.register_execution(
            source_id="alert_123",
            execution_id="exec_123",
            event_data={"severity": "high"}
        )
        
        # Atualizar entrada
        result = deduplicator.update_entry(
            dedup_key=dedup_key,
            event_data={"severity": "critical"}
        )
        
        assert result is True
        entry = deduplicator.cache[dedup_key]
        assert entry.event_count == 2
        assert entry.original_event["severity"] == "critical"
    
    def test_get_entry(self, deduplicator):
        """Testa obtenção de entrada."""
        dedup_key = deduplicator.register_execution(
            source_id="alert_123",
            execution_id="exec_123",
            event_data={"severity": "high"}
        )
        
        entry = deduplicator.get_entry(dedup_key)
        
        assert entry is not None
        assert entry.execution_id == "exec_123"
    
    def test_cache_expiration(self, deduplicator):
        """Testa expiração de cache."""
        # Registrar com TTL curto
        deduplicator.ttl_minutes = 1
        
        dedup_key = deduplicator.register_execution(
            source_id="alert_123",
            execution_id="exec_123",
            event_data={"severity": "high"}
        )
        
        # Simular passagem de tempo
        entry = deduplicator.cache[dedup_key]
        entry.last_seen = datetime.now(timezone.utc) - timedelta(minutes=2)
        
        # Verificar duplicação (deve expirar)
        action, _ = deduplicator.check_duplicate(
            source_id="alert_123",
            event_data={"severity": "high"}
        )
        
        assert action == DeduplicationAction.NEW_EXECUTION
    
    def test_cache_stats(self, deduplicator):
        """Testa estatísticas de cache."""
        # Registrar múltiplos eventos
        for i in range(3):
            deduplicator.register_execution(
                source_id=f"alert_{i}",
                execution_id=f"exec_{i}",
                event_data={"severity": "high"}
            )
        
        # Simular duplicatas
        for i in range(2):
            deduplicator.check_duplicate(
                source_id=f"alert_{i}",
                event_data={"severity": "high"}
            )
        
        stats = deduplicator.get_cache_stats()
        
        assert stats["cache_size"] == 3
        assert stats["unique_sources"] == 3
        assert stats["duplicate_events"] == 2
    
    def test_cache_eviction(self, deduplicator):
        """Testa evicção de cache."""
        # Definir limite pequeno
        deduplicator.max_cache_size = 3
        
        # Registrar 4 eventos
        for i in range(4):
            deduplicator.register_execution(
                source_id=f"alert_{i}",
                execution_id=f"exec_{i}",
                event_data={"severity": "high"}
            )
        
        # Cache deve ter no máximo 3 entradas
        assert len(deduplicator.cache) <= 3
    
    def test_clear_cache(self, deduplicator):
        """Testa limpeza de cache."""
        # Registrar eventos
        for i in range(5):
            deduplicator.register_execution(
                source_id=f"alert_{i}",
                execution_id=f"exec_{i}",
                event_data={"severity": "high"}
            )
        
        assert len(deduplicator.cache) > 0
        
        # Limpar
        deduplicator.clear_cache()
        
        assert len(deduplicator.cache) == 0


class TestSwarmCoordinator:
    """Testes para SwarmCoordinator."""
    
    @pytest.fixture
    def mock_controller(self):
        """Cria mock do controller."""
        return Mock()
    
    @pytest.fixture
    def coordinator(self, mock_controller):
        """Cria coordenador."""
        policy = DeduplicationPolicy(enabled=True, ttl_minutes=30)
        return SwarmCoordinator(mock_controller, policy)
    
    @pytest.mark.asyncio
    async def test_coordinate_new_swarm(self, coordinator):
        """Testa coordenação de novo swarm."""
        request = CoordinationRequest(
            source_id="alert_123",
            event_data={"severity": "high"},
            event_type="security_alert"
        )
        
        result = await coordinator.coordinate(request)
        
        assert result.execution_mode == ExecutionMode.NEW_SWARM
        assert result.execution_id is not None
        assert result.dedup_key is not None
    
    @pytest.mark.asyncio
    async def test_coordinate_update_graph(self, coordinator):
        """Testa coordenação de atualização de grafo."""
        request1 = CoordinationRequest(
            source_id="alert_123",
            event_data={"severity": "high"},
            event_type="security_alert"
        )
        
        # Primeiro evento
        result1 = await coordinator.coordinate(request1)
        assert result1.execution_mode == ExecutionMode.NEW_SWARM
        
        # Segundo evento (duplicado)
        request2 = CoordinationRequest(
            source_id="alert_123",
            event_data={"severity": "critical"},
            event_type="security_alert"
        )
        
        result2 = await coordinator.coordinate(request2)
        
        assert result2.execution_mode == ExecutionMode.UPDATE_GRAPH
        assert result2.execution_id == result1.execution_id
        assert result2.original_execution_id == result1.execution_id
    
    @pytest.mark.asyncio
    async def test_coordinate_deduplication_disabled(self, mock_controller):
        """Testa coordenação com deduplicação desabilitada."""
        policy = DeduplicationPolicy(enabled=False)
        coordinator = SwarmCoordinator(mock_controller, policy)
        
        request1 = CoordinationRequest(
            source_id="alert_123",
            event_data={"severity": "high"}
        )
        
        request2 = CoordinationRequest(
            source_id="alert_123",
            event_data={"severity": "high"}
        )
        
        result1 = await coordinator.coordinate(request1)
        result2 = await coordinator.coordinate(request2)
        
        # Ambos devem ser NEW_SWARM
        assert result1.execution_mode == ExecutionMode.NEW_SWARM
        assert result2.execution_mode == ExecutionMode.NEW_SWARM
    
    def test_get_deduplication_stats(self, coordinator):
        """Testa obtenção de estatísticas."""
        # Registrar eventos
        for i in range(3):
            coordinator.deduplicator.register_execution(
                source_id=f"alert_{i}",
                execution_id=f"exec_{i}",
                event_data={"severity": "high"}
            )
        
        stats = coordinator.get_deduplication_stats()
        
        assert stats["cache_size"] == 3
        assert stats["unique_sources"] == 3
    
    def test_clear_deduplication_cache(self, coordinator):
        """Testa limpeza de cache."""
        # Registrar eventos
        coordinator.deduplicator.register_execution(
            source_id="alert_123",
            execution_id="exec_123",
            event_data={"severity": "high"}
        )
        
        assert len(coordinator.deduplicator.cache) > 0
        
        # Limpar
        coordinator.clear_deduplication_cache()
        
        assert len(coordinator.deduplicator.cache) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
