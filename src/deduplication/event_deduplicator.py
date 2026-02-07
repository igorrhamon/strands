"""
Event Deduplicator - Deduplicação de Eventos

Implementa lógica de deduplicação baseada em deduplication_key e intervalo de tempo.
Se um evento com mesmo ID de origem foi processado nos últimos X minutos,
apenas atualiza o grafo existente em vez de iniciar um novo swarm.

Padrão: Cache Pattern + Time-Window Deduplication
Resiliência: Thread-safe, async-safe, TTL automático
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DeduplicationAction(str, Enum):
    """Ações de deduplicação."""
    NEW_EXECUTION = "new_execution"          # Novo evento, iniciar swarm
    UPDATE_EXISTING = "update_existing"      # Evento duplicado, atualizar grafo
    SKIP_DUPLICATE = "skip_duplicate"        # Evento duplicado, ignorar


@dataclass
class DeduplicationEntry:
    """Entrada no cache de deduplicação."""
    
    deduplication_key: str = Field(..., description="Chave de deduplicação")
    execution_id: str = Field(..., description="ID da execução original")
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_count: int = field(default=1)
    original_event: Dict = field(default_factory=dict)
    
    def is_expired(self, ttl_minutes: int) -> bool:
        """Verifica se entrada expirou.
        
        Args:
            ttl_minutes: TTL em minutos
        
        Returns:
            True se expirada
        """
        expiry = self.last_seen + timedelta(minutes=ttl_minutes)
        return datetime.now(timezone.utc) > expiry


class EventDeduplicator:
    """Deduplicador de eventos com cache e TTL.
    
    Responsabilidades:
    1. Gerar deduplication_key baseado em source_id
    2. Verificar se evento foi visto nos últimos X minutos
    3. Retornar ação apropriada (NEW, UPDATE, SKIP)
    4. Manter cache com limpeza automática
    """
    
    def __init__(self, ttl_minutes: int = 30, max_cache_size: int = 10000):
        """Inicializa deduplicador.
        
        Args:
            ttl_minutes: TTL em minutos (padrão 30)
            max_cache_size: Tamanho máximo do cache (padrão 10000)
        """
        self.ttl_minutes = ttl_minutes
        self.max_cache_size = max_cache_size
        self.cache: Dict[str, DeduplicationEntry] = {}
        self.logger = logging.getLogger("event_deduplicator")
    
    def generate_deduplication_key(self,
                                  source_id: str,
                                  event_type: Optional[str] = None,
                                  source_system: Optional[str] = None) -> str:
        """Gera deduplication_key baseado em source_id.
        
        Args:
            source_id: ID único da origem do evento
            event_type: Tipo de evento (opcional)
            source_system: Sistema de origem (opcional)
        
        Returns:
            Deduplication key (hash)
        
        Exemplo:
            source_id = "alert_12345"
            event_type = "security_alert"
            source_system = "prometheus"
            → key = "dedup_abc123def456"
        """
        # Construir string para hash
        key_parts = [source_id]
        
        if event_type:
            key_parts.append(event_type)
        
        if source_system:
            key_parts.append(source_system)
        
        key_string = "|".join(key_parts)
        
        # Gerar hash
        hash_obj = hashlib.sha256(key_string.encode())
        hash_hex = hash_obj.hexdigest()[:16]
        
        dedup_key = f"dedup_{hash_hex}"
        
        self.logger.debug(f"Dedup key gerada: {dedup_key} (source: {source_id})")
        
        return dedup_key
    
    def check_duplicate(self,
                       source_id: str,
                       event_data: Dict,
                       event_type: Optional[str] = None,
                       source_system: Optional[str] = None) -> Tuple[DeduplicationAction, Optional[str]]:
        """Verifica se evento é duplicado.
        
        Args:
            source_id: ID único da origem
            event_data: Dados do evento
            event_type: Tipo de evento (opcional)
            source_system: Sistema de origem (opcional)
        
        Returns:
            Tupla (ação, execution_id_original)
        
        Exemplo:
            action, original_exec_id = deduplicator.check_duplicate(
                source_id="alert_12345",
                event_data={"severity": "high"},
                event_type="security_alert"
            )
            
            if action == DeduplicationAction.NEW_EXECUTION:
                # Iniciar novo swarm
                new_exec_id = coordinator.execute_swarm(event_data)
            elif action == DeduplicationAction.UPDATE_EXISTING:
                # Atualizar grafo existente
                graph_updater.update(original_exec_id, event_data)
            else:  # SKIP_DUPLICATE
                # Ignorar evento
                pass
        """
        # Gerar dedup key
        dedup_key = self.generate_deduplication_key(source_id, event_type, source_system)
        
        # Limpar cache expirado
        self._cleanup_expired_entries()
        
        # Verificar se existe no cache
        if dedup_key in self.cache:
            entry = self.cache[dedup_key]
            
            # Verificar se ainda está dentro do TTL
            if not entry.is_expired(self.ttl_minutes):
                # Evento duplicado - atualizar entrada
                entry.last_seen = datetime.now(timezone.utc)
                entry.event_count += 1
                
                self.logger.info(
                    f"Evento duplicado detectado: {dedup_key} | "
                    f"occurrences={entry.event_count} | "
                    f"original_exec={entry.execution_id}"
                )
                
                return (DeduplicationAction.UPDATE_EXISTING, entry.execution_id)
            else:
                # Entrada expirada - tratar como novo evento
                self.logger.info(f"Entrada de dedup expirada: {dedup_key}")
                del self.cache[dedup_key]
        
        # Novo evento
        self.logger.info(f"Novo evento: {dedup_key} (source: {source_id})")
        
        return (DeduplicationAction.NEW_EXECUTION, None)
    
    def register_execution(self,
                          source_id: str,
                          execution_id: str,
                          event_data: Dict,
                          event_type: Optional[str] = None,
                          source_system: Optional[str] = None) -> str:
        """Registra execução no cache de deduplicação.
        
        Args:
            source_id: ID único da origem
            execution_id: ID da execução criada
            event_data: Dados do evento
            event_type: Tipo de evento (opcional)
            source_system: Sistema de origem (opcional)
        
        Returns:
            Deduplication key
        """
        dedup_key = self.generate_deduplication_key(source_id, event_type, source_system)
        
        # Criar entrada
        entry = DeduplicationEntry(
            deduplication_key=dedup_key,
            execution_id=execution_id,
            original_event=event_data,
        )
        
        # Adicionar ao cache
        self.cache[dedup_key] = entry
        
        # Verificar limite de cache
        if len(self.cache) > self.max_cache_size:
            self._evict_oldest_entry()
        
        self.logger.info(
            f"Execução registrada: {dedup_key} → {execution_id} | "
            f"cache_size={len(self.cache)}"
        )
        
        return dedup_key
    
    def get_entry(self, dedup_key: str) -> Optional[DeduplicationEntry]:
        """Obtém entrada do cache.
        
        Args:
            dedup_key: Chave de deduplicação
        
        Returns:
            DeduplicationEntry ou None
        """
        return self.cache.get(dedup_key)
    
    def update_entry(self,
                    dedup_key: str,
                    event_data: Dict) -> bool:
        """Atualiza entrada com novos dados.
        
        Args:
            dedup_key: Chave de deduplicação
            event_data: Novos dados do evento
        
        Returns:
            True se atualizado, False se não encontrado
        """
        if dedup_key not in self.cache:
            self.logger.warning(f"Entrada não encontrada: {dedup_key}")
            return False
        
        entry = self.cache[dedup_key]
        entry.last_seen = datetime.now(timezone.utc)
        entry.event_count += 1
        entry.original_event = event_data
        
        self.logger.info(f"Entrada atualizada: {dedup_key} | count={entry.event_count}")
        
        return True
    
    def _cleanup_expired_entries(self):
        """Remove entradas expiradas do cache."""
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired(self.ttl_minutes)
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self.logger.debug(f"Limpeza de cache: {len(expired_keys)} entradas removidas")
    
    def _evict_oldest_entry(self):
        """Remove entrada mais antiga do cache."""
        if not self.cache:
            return
        
        oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].last_seen)
        del self.cache[oldest_key]
        
        self.logger.debug(f"Evicção de cache: {oldest_key} removida")
    
    def get_cache_stats(self) -> Dict:
        """Retorna estatísticas do cache.
        
        Returns:
            Dicionário com estatísticas
        """
        self._cleanup_expired_entries()
        
        total_events = sum(entry.event_count for entry in self.cache.values())
        duplicates = total_events - len(self.cache)
        
        return {
            "cache_size": len(self.cache),
            "max_cache_size": self.max_cache_size,
            "total_events_seen": total_events,
            "unique_sources": len(self.cache),
            "duplicate_events": duplicates,
            "deduplication_rate": (duplicates / total_events * 100) if total_events > 0 else 0,
            "ttl_minutes": self.ttl_minutes,
        }
    
    def clear_cache(self):
        """Limpa todo o cache."""
        self.cache.clear()
        self.logger.info("Cache de deduplicação limpo")


class DeduplicationPolicy(BaseModel):
    """Política de deduplicação."""
    
    enabled: bool = Field(True, description="Deduplicação habilitada?")
    ttl_minutes: int = Field(30, ge=1, le=1440, description="TTL em minutos")
    max_cache_size: int = Field(10000, ge=100, le=100000, description="Tamanho máximo do cache")
    action_on_duplicate: DeduplicationAction = Field(
        DeduplicationAction.UPDATE_EXISTING,
        description="Ação padrão em duplicatas"
    )
    
    class Config:
        frozen = True


class DeduplicationMetrics(BaseModel):
    """Métricas de deduplicação."""
    
    total_events_processed: int = Field(0, description="Total de eventos processados")
    duplicate_events_detected: int = Field(0, description="Eventos duplicados detectados")
    new_executions_created: int = Field(0, description="Novas execuções criadas")
    existing_executions_updated: int = Field(0, description="Execuções existentes atualizadas")
    duplicate_events_skipped: int = Field(0, description="Eventos duplicados ignorados")
    deduplication_rate: float = Field(0.0, ge=0.0, le=100.0, description="Taxa de deduplicação %")
    average_cache_size: float = Field(0.0, description="Tamanho médio do cache")
    
    class Config:
        frozen = True
