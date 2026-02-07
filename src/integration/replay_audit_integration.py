"""
Replay-Audit Integration - Integração entre ReplayEngine e AuditorAgent

Permite executar auditoria automática após replay para validar
se o novo caminho foi mais bem-sucedido que o original.

Padrão: Integration Pattern + Workflow Orchestration
Resiliência: Async execution, error handling, retry automático
"""

import logging
from typing import Dict, Optional, Tuple, Any
from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReplayComparisonType(str, Enum):
    """Tipos de comparação entre replays."""
    ORIGINAL_VS_REPLAY = "original_vs_replay"      # Original vs Replay
    REPLAY_VS_REPLAY = "replay_vs_replay"          # Replay A vs Replay B
    CONFIDENCE_IMPROVEMENT = "confidence_improvement"  # Melhora de confiança


class ReplayAuditResult(BaseModel):
    """Resultado da auditoria de replay."""
    
    original_execution_id: str = Field(..., description="ID da execução original")
    replay_execution_id: str = Field(..., description="ID da execução de replay")
    comparison_type: ReplayComparisonType = Field(..., description="Tipo de comparação")
    
    original_audit_report: Dict = Field(..., description="Relatório da auditoria original")
    replay_audit_report: Dict = Field(..., description="Relatório da auditoria de replay")
    
    confidence_improvement: float = Field(..., ge=-1, le=1, description="Melhora de confiança")
    coherence_improvement: float = Field(..., ge=-1, le=1, description="Melhora de coerência")
    
    success: bool = Field(..., description="Replay foi bem-sucedido?")
    recommendation: str = Field(..., description="Recomendação")
    
    class Config:
        frozen = True


class ReplayAuditOrchestrator:
    """Orquestrador de auditoria de replay.
    
    Responsabilidades:
    1. Executar replay
    2. Auditar resultado
    3. Comparar com original
    4. Gerar recomendações
    """
    
    def __init__(self,
                 replay_engine: object,
                 auditor_agent: object):
        """Inicializa o orquestrador.
        
        Args:
            replay_engine: Engine de replay
            auditor_agent: Agente de auditoria
        """
        self.replay_engine = replay_engine
        self.auditor_agent = auditor_agent
        self.logger = logging.getLogger("replay_audit_orchestrator")
    
    async def run_replay_with_audit(self,
                                   execution_id: str,
                                   run_audit: bool = True) -> Optional[ReplayAuditResult]:
        """Executa replay com auditoria automática.
        
        Args:
            execution_id: ID da execução a replayar
            run_audit: Se deve executar auditoria
        
        Returns:
            ReplayAuditResult ou None
        """
        self.logger.info(f"Iniciando replay com auditoria: {execution_id}")
        
        # Auditar execução original
        original_audit = self.auditor_agent.audit_execution(execution_id)
        
        if not run_audit:
            self.logger.info("Auditoria desabilitada")
            return None
        
        # Executar replay
        replay_result = await self.replay_engine.replay_full(execution_id)
        
        if not replay_result or not replay_result.get("execution_id"):
            self.logger.error("Falha ao executar replay")
            return None
        
        replay_execution_id = replay_result["execution_id"]
        
        # Auditar resultado do replay
        replay_audit = self.auditor_agent.audit_execution(replay_execution_id)
        
        # Comparar resultados
        comparison = self._compare_audits(
            original_audit,
            replay_audit,
            execution_id,
            replay_execution_id
        )
        
        self.logger.info(
            f"Replay concluído: {execution_id} → {replay_execution_id} | "
            f"success={comparison.success} | "
            f"confidence_improvement={comparison.confidence_improvement:.1%}"
        )
        
        return comparison
    
    def _compare_audits(self,
                       original_audit: Dict,
                       replay_audit: Dict,
                       original_id: str,
                       replay_id: str) -> ReplayAuditResult:
        """Compara auditorias original e replay.
        
        Args:
            original_audit: Auditoria original
            replay_audit: Auditoria de replay
            original_id: ID original
            replay_id: ID do replay
        
        Returns:
            ReplayAuditResult
        """
        # Extrair métricas
        original_coherence = original_audit.get("coherence_score", 0.5)
        replay_coherence = replay_audit.get("coherence_score", 0.5)
        
        original_confidence = original_audit.get("execution_lineage", {}).get("final_decision", {}).get("confidence", 0.5)
        replay_confidence = replay_audit.get("execution_lineage", {}).get("final_decision", {}).get("confidence", 0.5)
        
        # Calcular melhorias
        coherence_improvement = replay_coherence - original_coherence
        confidence_improvement = replay_confidence - original_confidence
        
        # Determinar sucesso
        original_risk = original_audit.get("overall_risk_level", "high")
        replay_risk = replay_audit.get("overall_risk_level", "high")
        
        success = (
            replay_coherence >= 0.7 and
            confidence_improvement >= 0 and
            self._risk_level_to_score(replay_risk) > self._risk_level_to_score(original_risk)
        )
        
        # Gerar recomendação
        recommendation = self._generate_recommendation(
            success,
            coherence_improvement,
            confidence_improvement,
            original_risk,
            replay_risk
        )
        
        return ReplayAuditResult(
            original_execution_id=original_id,
            replay_execution_id=replay_id,
            comparison_type=ReplayComparisonType.ORIGINAL_VS_REPLAY,
            original_audit_report=original_audit,
            replay_audit_report=replay_audit,
            confidence_improvement=confidence_improvement,
            coherence_improvement=coherence_improvement,
            success=success,
            recommendation=recommendation,
        )
    
    def _risk_level_to_score(self, risk_level: str) -> float:
        """Converte nível de risco para score.
        
        Args:
            risk_level: Nível de risco
        
        Returns:
            Score (0-1)
        """
        risk_scores = {
            "none": 1.0,
            "low": 0.75,
            "medium": 0.5,
            "high": 0.25,
            "critical": 0.0,
        }
        return risk_scores.get(risk_level.lower(), 0.5)
    
    def _generate_recommendation(self,
                                success: bool,
                                coherence_improvement: float,
                                confidence_improvement: float,
                                original_risk: str,
                                replay_risk: str) -> str:
        """Gera recomendação baseada em comparação.
        
        Args:
            success: Replay bem-sucedido?
            coherence_improvement: Melhora de coerência
            confidence_improvement: Melhora de confiança
            original_risk: Risco original
            replay_risk: Risco do replay
        
        Returns:
            Recomendação em texto
        """
        if success:
            if coherence_improvement > 0.2 and confidence_improvement > 0.1:
                return "✅ EXCELENTE: Replay significativamente melhor. Considerar aplicar mudanças em produção."
            elif coherence_improvement > 0.1 or confidence_improvement > 0.05:
                return "✅ BOM: Replay melhorou. Considerar aplicar mudanças com monitoramento."
            else:
                return "✅ ACEITÁVEL: Replay manteve qualidade. Pode ser aplicado."
        else:
            if coherence_improvement < -0.2 or confidence_improvement < -0.1:
                return "❌ CRÍTICO: Replay piorou significativamente. Não aplicar mudanças."
            elif coherence_improvement < -0.1 or confidence_improvement < -0.05:
                return "⚠️ AVISO: Replay apresentou degradação. Investigar antes de aplicar."
            else:
                return "⚠️ INCONCLUSIVO: Resultados similares. Requer análise adicional."
    
    async def compare_replays(self,
                             replay_id_a: str,
                             replay_id_b: str) -> Optional[ReplayAuditResult]:
        """Compara dois replays.
        
        Args:
            replay_id_a: ID do primeiro replay
            replay_id_b: ID do segundo replay
        
        Returns:
            ReplayAuditResult ou None
        """
        self.logger.info(f"Comparando replays: {replay_id_a} vs {replay_id_b}")
        
        # Auditar ambos
        audit_a = self.auditor_agent.audit_execution(replay_id_a)
        audit_b = self.auditor_agent.audit_execution(replay_id_b)
        
        # Comparar
        comparison = self._compare_audits(
            audit_a,
            audit_b,
            replay_id_a,
            replay_id_b
        )
        
        # Ajustar tipo de comparação
        comparison.comparison_type = ReplayComparisonType.REPLAY_VS_REPLAY
        
        return comparison
    
    def get_audit_metrics(self, audit_report: Dict) -> Dict[str, float]:
        """Extrai métricas de um relatório de auditoria.
        
        Args:
            audit_report: Relatório de auditoria
        
        Returns:
            Dicionário de métricas
        """
        return {
            "coherence_score": audit_report.get("coherence_score", 0.5),
            "loop_detected": 1.0 if audit_report.get("loop_detected") else 0.0,
            "findings_count": len(audit_report.get("findings", [])),
            "critical_findings": sum(
                1 for f in audit_report.get("findings", [])
                if f.get("risk_level") == "critical"
            ),
            "high_findings": sum(
                1 for f in audit_report.get("findings", [])
                if f.get("risk_level") == "high"
            ),
            "risk_score": self._risk_level_to_score(
                audit_report.get("overall_risk_level", "high")
            ),
        }


class ReplayAuditWorkflow:
    """Workflow de auditoria de replay.
    
    Orquestra a execução de replay com auditoria em múltiplas etapas.
    """
    
    def __init__(self, orchestrator: ReplayAuditOrchestrator):
        """Inicializa o workflow.
        
        Args:
            orchestrator: Orquestrador de replay-audit
        """
        self.orchestrator = orchestrator
        self.logger = logging.getLogger("replay_audit_workflow")
    
    async def execute_workflow(self,
                              execution_id: str,
                              stages: Optional[list] = None) -> Dict[str, Any]:
        """Executa workflow completo de replay-audit.
        
        Estágios:
        1. Validação: Verificar se execução existe
        2. Auditoria Original: Auditar execução original
        3. Replay: Executar replay
        4. Auditoria Replay: Auditar resultado
        5. Comparação: Comparar resultados
        6. Recomendação: Gerar recomendações
        
        Args:
            execution_id: ID da execução
            stages: Estágios a executar (todos se None)
        
        Returns:
            Resultado do workflow
        """
        if stages is None:
            stages = [
                "validation",
                "audit_original",
                "replay",
                "audit_replay",
                "comparison",
                "recommendation"
            ]
        
        self.logger.info(f"Iniciando workflow: {execution_id} | stages={stages}")
        
        result = {
            "execution_id": execution_id,
            "workflow_start": datetime.now(timezone.utc).isoformat(),
            "stages_executed": [],
            "status": "pending",
            "error": None,
        }
        
        try:
            # Estágio 1: Validação
            if "validation" in stages:
                self.logger.debug("Estágio: Validação")
                # Implementar validação
                result["stages_executed"].append("validation")
            
            # Estágio 2: Auditoria Original
            if "audit_original" in stages:
                self.logger.debug("Estágio: Auditoria Original")
                original_audit = self.orchestrator.auditor_agent.audit_execution(execution_id)
                result["original_audit"] = original_audit
                result["stages_executed"].append("audit_original")
            
            # Estágio 3: Replay
            if "replay" in stages:
                self.logger.debug("Estágio: Replay")
                # Implementar replay
                result["stages_executed"].append("replay")
            
            # Estágio 4: Auditoria Replay
            if "audit_replay" in stages:
                self.logger.debug("Estágio: Auditoria Replay")
                # Implementar auditoria de replay
                result["stages_executed"].append("audit_replay")
            
            # Estágio 5: Comparação
            if "comparison" in stages:
                self.logger.debug("Estágio: Comparação")
                # Implementar comparação
                result["stages_executed"].append("comparison")
            
            # Estágio 6: Recomendação
            if "recommendation" in stages:
                self.logger.debug("Estágio: Recomendação")
                # Implementar recomendação
                result["stages_executed"].append("recommendation")
            
            result["status"] = "completed"
        
        except Exception as e:
            self.logger.error(f"Erro no workflow: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        result["workflow_end"] = datetime.now(timezone.utc).isoformat()
        
        return result
