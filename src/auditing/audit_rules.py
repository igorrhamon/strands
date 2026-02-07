"""
Audit Rules - Regras de Auditoria Avançadas

Implementa regras de validação, conformidade e detecção de anomalias
para análise de execuções no Strands.

Padrão: Rule Engine + Compliance Framework
Resiliência: Regras compostas, caching, retry automático
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RuleStatus(str, Enum):
    """Status de uma regra."""
    PASSED = "passed"              # Passou
    WARNING = "warning"            # Aviso
    FAILED = "failed"              # Falhou


class RuleSeverity(str, Enum):
    """Severidade de uma regra."""
    INFO = "info"                  # Informativo
    WARNING = "warning"            # Aviso
    ERROR = "error"                # Erro
    CRITICAL = "critical"          # Crítico


@dataclass
class RuleResult:
    """Resultado da execução de uma regra."""
    
    rule_id: str
    rule_name: str
    status: RuleStatus
    severity: RuleSeverity
    message: str
    details: Dict[str, Any]
    timestamp: datetime


class AuditRule:
    """Classe base para regras de auditoria."""
    
    def __init__(self,
                 rule_id: str,
                 rule_name: str,
                 severity: RuleSeverity,
                 description: str):
        """Inicializa uma regra.
        
        Args:
            rule_id: ID único da regra
            rule_name: Nome da regra
            severity: Severidade
            description: Descrição
        """
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.severity = severity
        self.description = description
        self.logger = logging.getLogger(f"audit_rule_{rule_id}")
    
    def execute(self, context: Dict[str, Any]) -> RuleResult:
        """Executa a regra.
        
        Args:
            context: Contexto da auditoria
        
        Returns:
            RuleResult
        """
        raise NotImplementedError


class CoherenceValidationRule(AuditRule):
    """Regra: Validação de Coerência.
    
    Valida se a decisão final está alinhada com as evidências.
    Threshold: 70% de alinhamento mínimo.
    """
    
    def __init__(self, threshold: float = 0.7):
        """Inicializa a regra.
        
        Args:
            threshold: Threshold de alinhamento
        """
        super().__init__(
            rule_id="coherence_001",
            rule_name="Validação de Coerência",
            severity=RuleSeverity.ERROR,
            description="Valida alinhamento entre evidências e decisão final"
        )
        self.threshold = threshold
    
    def execute(self, context: Dict[str, Any]) -> RuleResult:
        """Executa a regra.
        
        Args:
            context: Contexto contendo coherence_score
        
        Returns:
            RuleResult
        """
        coherence_score = context.get("coherence_score", 0.5)
        
        if coherence_score >= self.threshold:
            status = RuleStatus.PASSED
            message = f"Coerência aceitável: {coherence_score:.1%}"
        elif coherence_score >= 0.5:
            status = RuleStatus.WARNING
            message = f"Coerência baixa: {coherence_score:.1%} (esperado >= {self.threshold:.1%})"
        else:
            status = RuleStatus.FAILED
            message = f"Coerência crítica: {coherence_score:.1%}"
        
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            status=status,
            severity=self.severity,
            message=message,
            details={
                "coherence_score": coherence_score,
                "threshold": self.threshold,
                "divergence": 1 - coherence_score,
            },
            timestamp=datetime.now(timezone.utc),
        )


class InfiniteLoopDetectionRule(AuditRule):
    """Regra: Detecção de Loop Infinito.
    
    Detecta se há múltiplas retentativas sem progresso.
    Threshold: > 5 retentativas com < 5% de melhora.
    """
    
    def __init__(self,
                 max_retries: int = 5,
                 min_improvement: float = 0.05):
        """Inicializa a regra.
        
        Args:
            max_retries: Máximo de retentativas
            min_improvement: Melhora mínima esperada
        """
        super().__init__(
            rule_id="loop_001",
            rule_name="Detecção de Loop Infinito",
            severity=RuleSeverity.CRITICAL,
            description="Detecta loops infinitos de retentativa"
        )
        self.max_retries = max_retries
        self.min_improvement = min_improvement
    
    def execute(self, context: Dict[str, Any]) -> RuleResult:
        """Executa a regra.
        
        Args:
            context: Contexto contendo retry_count e confidence_improvement
        
        Returns:
            RuleResult
        """
        retry_count = context.get("retry_count", 0)
        confidence_improvement = context.get("confidence_improvement", 0)
        
        if retry_count <= self.max_retries or confidence_improvement >= self.min_improvement:
            status = RuleStatus.PASSED
            message = f"Sem loop detectado: {retry_count} retentativas com {confidence_improvement:.1%} melhora"
        else:
            status = RuleStatus.FAILED
            message = f"Loop infinito detectado: {retry_count} retentativas com apenas {confidence_improvement:.1%} melhora"
        
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            status=status,
            severity=self.severity,
            message=message,
            details={
                "retry_count": retry_count,
                "max_retries": self.max_retries,
                "confidence_improvement": confidence_improvement,
                "min_improvement": self.min_improvement,
            },
            timestamp=datetime.now(timezone.utc),
        )


class AgentConfidenceRule(AuditRule):
    """Regra: Confiança de Agente.
    
    Valida se agentes mantêm confiança mínima.
    Threshold: 40% de confiança mínima.
    """
    
    def __init__(self, min_confidence: float = 0.4):
        """Inicializa a regra.
        
        Args:
            min_confidence: Confiança mínima
        """
        super().__init__(
            rule_id="agent_confidence_001",
            rule_name="Confiança de Agente",
            severity=RuleSeverity.WARNING,
            description="Valida confiança mínima de agentes"
        )
        self.min_confidence = min_confidence
    
    def execute(self, context: Dict[str, Any]) -> RuleResult:
        """Executa a regra.
        
        Args:
            context: Contexto contendo agent_confidences
        
        Returns:
            RuleResult
        """
        agent_confidences = context.get("agent_confidences", {})
        
        low_confidence_agents = {
            name: conf for name, conf in agent_confidences.items()
            if conf < self.min_confidence
        }
        
        if not low_confidence_agents:
            status = RuleStatus.PASSED
            message = "Todos os agentes com confiança aceitável"
        else:
            status = RuleStatus.WARNING
            message = f"{len(low_confidence_agents)} agentes com confiança baixa"
        
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            status=status,
            severity=self.severity,
            message=message,
            details={
                "low_confidence_agents": low_confidence_agents,
                "min_confidence": self.min_confidence,
            },
            timestamp=datetime.now(timezone.utc),
        )


class EvidenceConsistencyRule(AuditRule):
    """Regra: Consistência de Evidências.
    
    Valida se evidências não são contraditórias.
    Threshold: < 30% de contradição.
    """
    
    def __init__(self, contradiction_threshold: float = 0.3):
        """Inicializa a regra.
        
        Args:
            contradiction_threshold: Threshold de contradição
        """
        super().__init__(
            rule_id="evidence_consistency_001",
            rule_name="Consistência de Evidências",
            severity=RuleSeverity.WARNING,
            description="Valida consistência entre evidências"
        )
        self.contradiction_threshold = contradiction_threshold
    
    def execute(self, context: Dict[str, Any]) -> RuleResult:
        """Executa a regra.
        
        Args:
            context: Contexto contendo contradiction_rate
        
        Returns:
            RuleResult
        """
        contradiction_rate = context.get("contradiction_rate", 0)
        
        if contradiction_rate <= self.contradiction_threshold:
            status = RuleStatus.PASSED
            message = f"Evidências consistentes: {contradiction_rate:.1%} de contradição"
        else:
            status = RuleStatus.WARNING
            message = f"Evidências inconsistentes: {contradiction_rate:.1%} de contradição"
        
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            status=status,
            severity=self.severity,
            message=message,
            details={
                "contradiction_rate": contradiction_rate,
                "threshold": self.contradiction_threshold,
            },
            timestamp=datetime.now(timezone.utc),
        )


class DecisionTimelinessRule(AuditRule):
    """Regra: Oportunidade de Decisão.
    
    Valida se decisão foi tomada em tempo hábil.
    Threshold: < 5 segundos.
    """
    
    def __init__(self, max_duration_seconds: float = 5.0):
        """Inicializa a regra.
        
        Args:
            max_duration_seconds: Duração máxima
        """
        super().__init__(
            rule_id="decision_timeliness_001",
            rule_name="Oportunidade de Decisão",
            severity=RuleSeverity.WARNING,
            description="Valida se decisão foi tomada em tempo hábil"
        )
        self.max_duration_seconds = max_duration_seconds
    
    def execute(self, context: Dict[str, Any]) -> RuleResult:
        """Executa a regra.
        
        Args:
            context: Contexto contendo decision_duration_seconds
        
        Returns:
            RuleResult
        """
        duration = context.get("decision_duration_seconds", 0)
        
        if duration <= self.max_duration_seconds:
            status = RuleStatus.PASSED
            message = f"Decisão oportuna: {duration:.2f}s"
        else:
            status = RuleStatus.WARNING
            message = f"Decisão atrasada: {duration:.2f}s (esperado <= {self.max_duration_seconds}s)"
        
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            status=status,
            severity=self.severity,
            message=message,
            details={
                "duration_seconds": duration,
                "max_duration_seconds": self.max_duration_seconds,
            },
            timestamp=datetime.now(timezone.utc),
        )


class AuditRuleEngine:
    """Motor de regras de auditoria.
    
    Responsabilidades:
    1. Registrar regras
    2. Executar regras
    3. Agregar resultados
    4. Gerar relatório
    """
    
    def __init__(self):
        """Inicializa o motor."""
        self.logger = logging.getLogger("audit_rule_engine")
        self.rules: Dict[str, AuditRule] = {}
        self._register_default_rules()
    
    def _register_default_rules(self):
        """Registra regras padrão."""
        self.register_rule(CoherenceValidationRule())
        self.register_rule(InfiniteLoopDetectionRule())
        self.register_rule(AgentConfidenceRule())
        self.register_rule(EvidenceConsistencyRule())
        self.register_rule(DecisionTimelinessRule())
    
    def register_rule(self, rule: AuditRule):
        """Registra uma regra.
        
        Args:
            rule: Regra a registrar
        """
        self.rules[rule.rule_id] = rule
        self.logger.debug(f"Regra registrada: {rule.rule_id}")
    
    def execute_all(self, context: Dict[str, Any]) -> List[RuleResult]:
        """Executa todas as regras.
        
        Args:
            context: Contexto da auditoria
        
        Returns:
            Lista de resultados
        """
        results = []
        
        for rule_id, rule in self.rules.items():
            try:
                result = rule.execute(context)
                results.append(result)
                
                self.logger.debug(
                    f"Regra executada: {rule_id} | "
                    f"status={result.status.value} | "
                    f"severity={result.severity.value}"
                )
            
            except Exception as e:
                self.logger.error(f"Erro ao executar regra {rule_id}: {e}")
        
        return results
    
    def get_results_by_status(self,
                             results: List[RuleResult],
                             status: RuleStatus) -> List[RuleResult]:
        """Filtra resultados por status.
        
        Args:
            results: Lista de resultados
            status: Status a filtrar
        
        Returns:
            Resultados filtrados
        """
        return [r for r in results if r.status == status]
    
    def get_results_by_severity(self,
                               results: List[RuleResult],
                               severity: RuleSeverity) -> List[RuleResult]:
        """Filtra resultados por severidade.
        
        Args:
            results: Lista de resultados
            severity: Severidade a filtrar
        
        Returns:
            Resultados filtrados
        """
        return [r for r in results if r.severity == severity]
    
    def generate_summary(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Gera sumário dos resultados.
        
        Args:
            results: Lista de resultados
        
        Returns:
            Sumário
        """
        return {
            "total_rules": len(results),
            "passed": len(self.get_results_by_status(results, RuleStatus.PASSED)),
            "warnings": len(self.get_results_by_status(results, RuleStatus.WARNING)),
            "failed": len(self.get_results_by_status(results, RuleStatus.FAILED)),
            "critical_issues": len(self.get_results_by_severity(results, RuleSeverity.CRITICAL)),
            "errors": len(self.get_results_by_severity(results, RuleSeverity.ERROR)),
        }
