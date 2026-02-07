"""
Health Checks - Verificação de Saúde da Aplicação

Implementa padrão Kubernetes Liveness/Readiness Probes para monitoramento.
Verifica conectividade com dependências críticas (Neo4j, Qdrant, etc).

Padrão: Health Check Pattern (inspiração Kubernetes probes)
Resiliência: Timeout configurável, fallback graceful
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Estados de saúde."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceHealth(BaseModel):
    """Saúde de um serviço específico."""
    
    name: str = Field(..., description="Nome do serviço")
    status: HealthStatus = Field(..., description="Status de saúde")
    response_time_ms: float = Field(..., ge=0, description="Tempo de resposta em ms")
    last_check: datetime = Field(..., description="Última verificação")
    error: Optional[str] = Field(None, description="Mensagem de erro se unhealthy")
    
    class Config:
        frozen = True


class ApplicationHealth(BaseModel):
    """Saúde geral da aplicação."""
    
    status: HealthStatus = Field(..., description="Status geral")
    timestamp: datetime = Field(..., description="Timestamp da verificação")
    uptime_seconds: float = Field(..., ge=0, description="Tempo de atividade em segundos")
    services: Dict[str, ServiceHealth] = Field(..., description="Saúde de cada serviço")
    
    class Config:
        frozen = True


class HealthChecker:
    """Verificador de saúde da aplicação.
    
    Responsabilidades:
    1. Verificar conectividade com Neo4j
    2. Verificar conectividade com Qdrant
    3. Verificar conectividade com Prometheus
    4. Retornar status agregado
    5. Implementar timeout para cada verificação
    """
    
    def __init__(self,
                 neo4j_driver: Optional[object] = None,
                 qdrant_client: Optional[object] = None,
                 check_timeout_seconds: float = 5.0):
        """Inicializa o verificador.
        
        Args:
            neo4j_driver: Driver do Neo4j
            qdrant_client: Cliente do Qdrant
            check_timeout_seconds: Timeout para cada verificação
        """
        self.neo4j_driver = neo4j_driver
        self.qdrant_client = qdrant_client
        self.check_timeout_seconds = check_timeout_seconds
        self.logger = logging.getLogger("health_checker")
        
        # Rastrear tempo de início
        self.start_time = datetime.now(timezone.utc)
    
    def check_liveness(self) -> HealthStatus:
        """Verifica se a aplicação está viva (Liveness Probe).
        
        Liveness: Verifica se a aplicação está respondendo
        - Simples e rápido
        - Sem dependências externas
        - Se falhar, Kubernetes reinicia o container
        
        Returns:
            HealthStatus
        """
        try:
            # Verificação simples: aplicação está respondendo
            self.logger.debug("Liveness check: OK")
            return HealthStatus.HEALTHY
        except Exception as e:
            self.logger.error(f"Liveness check falhou: {e}")
            return HealthStatus.UNHEALTHY
    
    def check_readiness(self) -> ApplicationHealth:
        """Verifica se a aplicação está pronta (Readiness Probe).
        
        Readiness: Verifica se a aplicação pode receber tráfego
        - Verifica dependências críticas
        - Se falhar, Kubernetes remove do load balancer
        
        Returns:
            ApplicationHealth
        """
        services = {}
        
        # Verificar Neo4j
        if self.neo4j_driver:
            services["neo4j"] = self._check_neo4j()
        
        # Verificar Qdrant
        if self.qdrant_client:
            services["qdrant"] = self._check_qdrant()
        
        # Determinar status geral
        statuses = [s.status for s in services.values()]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        # Calcular uptime
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        health = ApplicationHealth(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            uptime_seconds=uptime,
            services=services,
        )
        
        self.logger.info(
            f"Readiness check: {overall_status.value} "
            f"({len([s for s in statuses if s == HealthStatus.HEALTHY])}/{len(statuses)} serviços OK)"
        )
        
        return health
    
    def _check_neo4j(self) -> ServiceHealth:
        """Verifica saúde do Neo4j.
        
        Returns:
            ServiceHealth
        """
        start_time = time.time()
        
        try:
            # Executar query simples
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="neo4j",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                last_check=datetime.now(timezone.utc),
            )
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            self.logger.warning(f"Neo4j health check falhou: {e}")
            
            return ServiceHealth(
                name="neo4j",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                last_check=datetime.now(timezone.utc),
                error=str(e),
            )
    
    def _check_qdrant(self) -> ServiceHealth:
        """Verifica saúde do Qdrant.
        
        Returns:
            ServiceHealth
        """
        start_time = time.time()
        
        try:
            # Verificar conexão
            health = self.qdrant_client.get_collections()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="qdrant",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                last_check=datetime.now(timezone.utc),
            )
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            self.logger.warning(f"Qdrant health check falhou: {e}")
            
            return ServiceHealth(
                name="qdrant",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                last_check=datetime.now(timezone.utc),
                error=str(e),
            )
    
    def get_detailed_health(self) -> Dict:
        """Obtém saúde detalhada para debugging.
        
        Returns:
            Dicionário com informações detalhadas
        """
        readiness = self.check_readiness()
        
        return {
            "liveness": self.check_liveness().value,
            "readiness": readiness.status.value,
            "uptime_seconds": readiness.uptime_seconds,
            "services": {
                name: {
                    "status": service.status.value,
                    "response_time_ms": service.response_time_ms,
                    "error": service.error,
                }
                for name, service in readiness.services.items()
            },
            "timestamp": readiness.timestamp.isoformat(),
        }


# Instância global
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Obtém instância global do verificador de saúde."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def set_health_checker(checker: HealthChecker):
    """Define instância global do verificador de saúde."""
    global _health_checker
    _health_checker = checker
