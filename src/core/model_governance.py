"""
Model Governance - Versioning, Auditability, Decision Tracking

Implementa rastreabilidade completa de modelos de correlação e decisões.
"""

import json
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)


class ModelVersion(str, Enum):
    """Versões de modelo de correlação."""
    V1_BASIC = "1.0.0"                    # Pearson básico
    V1_1_LAG_DETECTION = "1.1.0"          # Com detecção de lag
    V2_BAYESIAN = "2.0.0"                 # Com confiança Bayesiana
    V2_1_ADAPTIVE = "2.1.0"               # Com threshold adaptativo


@dataclass
class ModelConfig:
    """Configuração de modelo de correlação."""
    version: ModelVersion
    correlation_method: str                # "pearson", "spearman", "kendall"
    max_lag: int
    normalize: bool
    min_sample_size: int
    significance_threshold: float          # p-value threshold
    confidence_threshold: float            # confidence score threshold
    use_bayesian: bool
    use_detrending: bool
    anomaly_detection_enabled: bool
    
    def to_dict(self) -> dict:
        return {
            "version": self.version.value,
            "correlation_method": self.correlation_method,
            "max_lag": self.max_lag,
            "normalize": self.normalize,
            "min_sample_size": self.min_sample_size,
            "significance_threshold": self.significance_threshold,
            "confidence_threshold": self.confidence_threshold,
            "use_bayesian": self.use_bayesian,
            "use_detrending": self.use_detrending,
            "anomaly_detection_enabled": self.anomaly_detection_enabled
        }
    
    def get_hash(self) -> str:
        """Calcula hash da configuração."""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()


class DecisionAuditLog:
    """Log de auditoria de decisão."""
    
    def __init__(
        self,
        decision_id: str,
        agent_id: str,
        model_version: ModelVersion,
        model_config_hash: str,
        alert_fingerprint: str,
        hypothesis: str,
        confidence: float,
        correlation_type: str,
        evidence_count: int,
        suggested_actions: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.decision_id = decision_id
        self.agent_id = agent_id
        self.model_version = model_version
        self.model_config_hash = model_config_hash
        self.alert_fingerprint = alert_fingerprint
        self.hypothesis = hypothesis
        self.confidence = confidence
        self.correlation_type = correlation_type
        self.evidence_count = evidence_count
        self.suggested_actions = suggested_actions
        self.timestamp = datetime.now(timezone.utc)
        self.metadata = metadata or {}
        self.execution_time_ms = 0.0
        self.status = "PENDING"  # PENDING, APPROVED, REJECTED, EXECUTED
        self.status_history: List[Dict[str, Any]] = []
    
    def update_status(self, new_status: str, reason: Optional[str] = None):
        """Atualiza status da decisão."""
        self.status = new_status
        self.status_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": new_status,
            "reason": reason
        })
    
    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "model_version": self.model_version.value,
            "model_config_hash": self.model_config_hash,
            "alert_fingerprint": self.alert_fingerprint,
            "hypothesis": self.hypothesis,
            "confidence": self.confidence,
            "correlation_type": self.correlation_type,
            "evidence_count": self.evidence_count,
            "suggested_actions": self.suggested_actions,
            "timestamp": self.timestamp.isoformat(),
            "execution_time_ms": self.execution_time_ms,
            "status": self.status,
            "status_history": self.status_history,
            "metadata": self.metadata
        }


class ModelGovernance:
    """Gerencia versioning e auditoria de modelos."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.current_model_version = ModelVersion.V2_BAYESIAN
        self.model_configs: Dict[str, ModelConfig] = {}
        self.decision_logs: List[DecisionAuditLog] = []
        self.model_performance: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
        # Inicializar configurações padrão
        self._initialize_default_configs()
    
    def _initialize_default_configs(self):
        """Inicializa configurações padrão para cada versão."""
        self.model_configs[ModelVersion.V1_BASIC.value] = ModelConfig(
            version=ModelVersion.V1_BASIC,
            correlation_method="pearson",
            max_lag=0,
            normalize=True,
            min_sample_size=20,
            significance_threshold=0.05,
            confidence_threshold=0.7,
            use_bayesian=False,
            use_detrending=False,
            anomaly_detection_enabled=False
        )
        
        self.model_configs[ModelVersion.V1_1_LAG_DETECTION.value] = ModelConfig(
            version=ModelVersion.V1_1_LAG_DETECTION,
            correlation_method="pearson",
            max_lag=5,
            normalize=True,
            min_sample_size=20,
            significance_threshold=0.05,
            confidence_threshold=0.7,
            use_bayesian=False,
            use_detrending=False,
            anomaly_detection_enabled=True
        )
        
        self.model_configs[ModelVersion.V2_BAYESIAN.value] = ModelConfig(
            version=ModelVersion.V2_BAYESIAN,
            correlation_method="pearson",
            max_lag=5,
            normalize=True,
            min_sample_size=20,
            significance_threshold=0.05,
            confidence_threshold=0.65,
            use_bayesian=True,
            use_detrending=True,
            anomaly_detection_enabled=True
        )
        
        self.model_configs[ModelVersion.V2_1_ADAPTIVE.value] = ModelConfig(
            version=ModelVersion.V2_1_ADAPTIVE,
            correlation_method="pearson",
            max_lag=5,
            normalize=True,
            min_sample_size=20,
            significance_threshold=0.05,
            confidence_threshold=0.60,
            use_bayesian=True,
            use_detrending=True,
            anomaly_detection_enabled=True
        )
    
    def get_current_config(self) -> ModelConfig:
        """Retorna configuração atual."""
        return self.model_configs[self.current_model_version.value]
    
    def switch_model_version(self, new_version: ModelVersion):
        """Muda versão de modelo."""
        with self._lock:
            old_version = self.current_model_version
            self.current_model_version = new_version
            
            logger.info(
                f"[{self.agent_id}] Model version switched from {old_version.value} to {new_version.value}"
            )
    
    def log_decision(
        self,
        decision_id: str,
        alert_fingerprint: str,
        hypothesis: str,
        confidence: float,
        correlation_type: str,
        evidence_count: int,
        suggested_actions: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DecisionAuditLog:
        """Registra decisão no log de auditoria."""
        config = self.get_current_config()
        config_hash = config.get_hash()
        
        audit_log = DecisionAuditLog(
            decision_id=decision_id,
            agent_id=self.agent_id,
            model_version=self.current_model_version,
            model_config_hash=config_hash,
            alert_fingerprint=alert_fingerprint,
            hypothesis=hypothesis,
            confidence=confidence,
            correlation_type=correlation_type,
            evidence_count=evidence_count,
            suggested_actions=suggested_actions,
            metadata=metadata
        )
        
        with self._lock:
            self.decision_logs.append(audit_log)
        
        logger.info(f"Decision logged: {decision_id} (confidence: {confidence:.2f})")
        
        return audit_log
    
    def update_decision_status(
        self,
        decision_id: str,
        new_status: str,
        reason: Optional[str] = None
    ):
        """Atualiza status de decisão."""
        with self._lock:
            for log in self.decision_logs:
                if log.decision_id == decision_id:
                    log.update_status(new_status, reason)
                    logger.info(f"Decision {decision_id} status updated to {new_status}")
                    return
        
        logger.warning(f"Decision {decision_id} not found in audit log")
    
    def record_execution_time(self, decision_id: str, execution_time_ms: float):
        """Registra tempo de execução."""
        with self._lock:
            for log in self.decision_logs:
                if log.decision_id == decision_id:
                    log.execution_time_ms = execution_time_ms
                    return
    
    def get_decision_audit_trail(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Retorna trilha de auditoria de decisão."""
        with self._lock:
            for log in self.decision_logs:
                if log.decision_id == decision_id:
                    return log.to_dict()
        
        return None
    
    def get_model_performance_metrics(self) -> dict:
        """Calcula métricas de desempenho do modelo."""
        with self._lock:
            if not self.decision_logs:
                return {}
            
            total_decisions = len(self.decision_logs)
            approved = sum(1 for log in self.decision_logs if log.status == "APPROVED")
            rejected = sum(1 for log in self.decision_logs if log.status == "REJECTED")
            executed = sum(1 for log in self.decision_logs if log.status == "EXECUTED")
            
            avg_confidence = sum(log.confidence for log in self.decision_logs) / total_decisions
            avg_execution_time = sum(log.execution_time_ms for log in self.decision_logs) / total_decisions
            
            # Agrupar por tipo de correlação
            by_type = {}
            for log in self.decision_logs:
                if log.correlation_type not in by_type:
                    by_type[log.correlation_type] = {
                        "count": 0,
                        "avg_confidence": 0,
                        "success_rate": 0
                    }
                by_type[log.correlation_type]["count"] += 1
            
            return {
                "total_decisions": total_decisions,
                "approved": approved,
                "rejected": rejected,
                "executed": executed,
                "approval_rate": approved / total_decisions if total_decisions > 0 else 0,
                "execution_rate": executed / total_decisions if total_decisions > 0 else 0,
                "avg_confidence": avg_confidence,
                "avg_execution_time_ms": avg_execution_time,
                "by_correlation_type": by_type
            }
    
    def export_audit_trail(self) -> dict:
        """Exporta trilha de auditoria completa."""
        with self._lock:
            return {
                "agent_id": self.agent_id,
                "current_model_version": self.current_model_version.value,
                "current_config": self.get_current_config().to_dict(),
                "total_decisions": len(self.decision_logs),
                "performance_metrics": self.get_model_performance_metrics(),
                "decisions": [log.to_dict() for log in self.decision_logs[-100:]]  # Últimas 100
            }
