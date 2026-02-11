"""
Distributed Event Deduplicator - Deduplicação de Eventos em Escala
Implementa lógica de deduplicação distribuída usando Redis.
Resolve os problemas de thread-safety e multi-instância (Kubernetes).
"""

import logging
import json
import hashlib
import os
from typing import Optional, Tuple, Dict
from datetime import datetime, timezone
from enum import Enum

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from src.deduplication.event_deduplicator import DeduplicationAction

logger = logging.getLogger(__name__)

class DistributedEventDeduplicator:
    """
    Deduplicador distribuído usando Redis.
    
    Vantagens:
    1. Thread-safe e Async-safe (Redis é atômico).
    2. Funciona em múltiplas instâncias (Kubernetes).
    3. TTL nativo do Redis.
    4. Lock distribuído para evitar re-execuções.
    """
    
    def __init__(
        self, 
        redis_url: Optional[str] = None,
        ttl_minutes: int = 30,
        prefix: str = "strads:dedup:"
    ):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.ttl_minutes = ttl_minutes
        self.prefix = prefix
        self._redis = None
        
        if REDIS_AVAILABLE:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
                logger.info(f"[DISTRIBUTED_DEDUP] Connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.warning(f"[DISTRIBUTED_DEDUP] Failed to connect to Redis: {e}")
                self._redis = None
        else:
            logger.warning("[DISTRIBUTED_DEDUP] Redis package not installed")

    def generate_deduplication_key(
        self,
        source_id: str,
        event_type: Optional[str] = None,
        source_system: Optional[str] = None,
        severity: Optional[str] = None
    ) -> str:
        """
        Gera chave de deduplicação rica (Alert Signature).
        Inclui severidade conforme sugerido pelo ChatGPT.
        """
        key_parts = [source_id]
        if event_type: key_parts.append(event_type)
        if source_system: key_parts.append(source_system)
        if severity: key_parts.append(severity)
        
        key_string = "|".join(key_parts)
        hash_hex = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        return f"{self.prefix}{hash_hex}"

    def check_duplicate(
        self,
        source_id: str,
        event_data: Dict,
        event_type: Optional[str] = None,
        source_system: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Tuple[DeduplicationAction, Optional[str]]:
        """
        Verifica duplicata usando Redis de forma atômica.
        """
        if not self._redis:
            logger.error("[DISTRIBUTED_DEDUP] Redis not available, skipping dedup")
            return DeduplicationAction.NEW_EXECUTION, None

        dedup_key = self.generate_deduplication_key(source_id, event_type, source_system, severity)
        
        # Tenta obter dados da execução existente
        existing_data = self._redis.get(dedup_key)
        
        if existing_data:
            try:
                data = json.loads(existing_data)
                execution_id = data.get("execution_id")
                
                # Atualiza contagem e last_seen de forma atômica (opcionalmente)
                data["event_count"] = data.get("event_count", 1) + 1
                data["last_seen"] = datetime.now(timezone.utc).isoformat()
                
                # Salva de volta com o mesmo TTL restante ou renova
                self._redis.setex(
                    dedup_key, 
                    self.ttl_minutes * 60, 
                    json.dumps(data)
                )
                
                logger.info(f"[DISTRIBUTED_DEDUP] Duplicate detected: {dedup_key} -> {execution_id}")
                return DeduplicationAction.UPDATE_EXISTING, execution_id
            except Exception as e:
                logger.error(f"[DISTRIBUTED_DEDUP] Error parsing existing data: {e}")
        
        return DeduplicationAction.NEW_EXECUTION, None

    def register_execution(
        self,
        source_id: str,
        execution_id: str,
        event_data: Dict,
        event_type: Optional[str] = None,
        source_system: Optional[str] = None,
        severity: Optional[str] = None
    ) -> bool:
        """
        Registra uma nova execução no Redis com TTL.
        """
        if not self._redis:
            return False

        dedup_key = self.generate_deduplication_key(source_id, event_type, source_system, severity)
        
        data = {
            "execution_id": execution_id,
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "event_count": 1,
            "source_id": source_id
        }
        
        try:
            # SETEX define valor e expiração atomicamente
            self._redis.setex(
                dedup_key,
                self.ttl_minutes * 60,
                json.dumps(data)
            )
            logger.info(f"[DISTRIBUTED_DEDUP] Registered execution: {dedup_key} -> {execution_id}")
            return True
        except Exception as e:
            logger.error(f"[DISTRIBUTED_DEDUP] Failed to register execution: {e}")
            return False

    def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """
        Implementa um lock distribuído simples (SETNX).
        Evita que duas instâncias iniciem o mesmo swarm simultaneamente.
        """
        if not self._redis:
            return True # Fallback perigoso, mas evita travar o sistema
            
        lock_key = f"lock:{lock_name}"
        # nx=True faz o SET apenas se a chave não existir (SETNX)
        return bool(self._redis.set(lock_key, "locked", ex=timeout, nx=True))

    def release_lock(self, lock_name: str):
        """Libera o lock distribuído."""
        if self._redis:
            self._redis.delete(f"lock:{lock_name}")
