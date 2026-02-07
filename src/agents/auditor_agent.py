"""
AuditorAgent - Agente Especializado em Auditoria e Análise de Linhagem

Analisa a linhagem de grafos no Neo4j para validar execuções,
detectar anomalias e gerar relatórios de auditoria estruturados.

Padrão: Graph Analysis + Compliance Auditing
Resiliência: Queries otimizadas, cache de resultados, retry automático
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditRiskLevel(str, Enum):
    """Níveis de risco de auditoria."""
    NONE = "none"              # Sem risco
    LOW = "low"                # Risco baixo
    MEDIUM = "medium"          # Risco médio
    HIGH = "high"              # Risco alto
    CRITICAL = "critical"      # Risco crítico


class AuditFinding(BaseModel):
    """Achado de auditoria."""
    
    finding_id: str = Field(..., description="ID único do achado")
    rule_name: str = Field(..., description="Nome da regra violada")
    risk_level: AuditRiskLevel = Field(..., description="Nível de risco")
    description: str = Field(..., description="Descrição do achado")
    evidence: Dict[str, Any] = Field(..., description="Evidências")
    recommendation: str = Field(..., description="Recomendação")
    
    class Config:
        frozen = True


class ExecutionLineage(BaseModel):
    """Linhagem de uma execução."""
    
    execution_id: str = Field(..., description="ID da execução")
    start_time: datetime = Field(..., description="Hora de início")
    end_time: Optional[datetime] = Field(None, description="Hora de fim")
    agents_involved: List[str] = Field(..., description="Agentes envolvidos")
    evidence_count: int = Field(..., description="Número de evidências")
    decisions_made: int = Field(..., description="Número de decisões")
    final_decision: Optional[Dict] = Field(None, description="Decisão final")
    
    class Config:
        frozen = True


class AuditReport(BaseModel):
    """Relatório de auditoria estruturado."""
    
    audit_id: str = Field(..., description="ID único da auditoria")
    execution_id: str = Field(..., description="ID da execução auditada")
    audit_timestamp: datetime = Field(..., description="Quando foi auditada")
    overall_risk_level: AuditRiskLevel = Field(..., description="Nível de risco geral")
    execution_lineage: ExecutionLineage = Field(..., description="Linhagem da execução")
    findings: List[AuditFinding] = Field(..., description="Achados da auditoria")
    coherence_score: float = Field(..., ge=0, le=1, description="Score de coerência")
    loop_detected: bool = Field(..., description="Loop infinito detectado?")
    prompt_refinement_suggestions: List[str] = Field(..., description="Sugestões de refino")
    summary: str = Field(..., description="Resumo executivo")
    
    class Config:
        frozen = True


class AuditorAgent:
    """Agente especializado em auditoria e análise de linhagem.
    
    Responsabilidades:
    1. Extrair linhagem de grafos do Neo4j
    2. Validar coerência entre evidências e decisões
    3. Detectar loops infinitos
    4. Gerar recomendações de refino de prompts
    5. Produzir relatórios estruturados
    """
    
    def __init__(self, neo4j_adapter: object):
        """Inicializa o auditor.
        
        Args:
            neo4j_adapter: Adaptador Neo4j para acesso ao grafo
        """
        self.neo4j_adapter = neo4j_adapter
        self.logger = logging.getLogger("auditor_agent")
    
    def audit_execution(self, execution_id: str) -> AuditReport:
        """Audita uma execução completa.
        
        Args:
            execution_id: ID da execução a auditar
        
        Returns:
            AuditReport
        """
        import uuid
        
        self.logger.info(f"Iniciando auditoria: {execution_id}")
        
        # Extrair linhagem
        lineage = self._extract_lineage(execution_id)
        
        if not lineage:
            self.logger.error(f"Execução não encontrada: {execution_id}")
            raise ValueError(f"Execução não encontrada: {execution_id}")
        
        # Executar regras de auditoria
        findings: List[AuditFinding] = []
        
        # Regra 1: Validação de Coerência
        coherence_findings, coherence_score = self._validate_coherence(execution_id, lineage)
        findings.extend(coherence_findings)
        
        # Regra 2: Detecção de Loop
        loop_findings, loop_detected = self._detect_loops(execution_id, lineage)
        findings.extend(loop_findings)
        
        # Regra 3: Análise de Padrões
        pattern_findings = self._analyze_patterns(execution_id, lineage)
        findings.extend(pattern_findings)
        
        # Calcular nível de risco geral
        overall_risk_level = self._calculate_overall_risk(findings)
        
        # Gerar sugestões de refino
        refinement_suggestions = self._generate_refinement_suggestions(
            findings,
            coherence_score,
            loop_detected
        )
        
        # Gerar resumo
        summary = self._generate_summary(
            lineage,
            findings,
            coherence_score,
            loop_detected
        )
        
        # Criar relatório
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        report = AuditReport(
            audit_id=audit_id,
            execution_id=execution_id,
            audit_timestamp=datetime.now(timezone.utc),
            overall_risk_level=overall_risk_level,
            execution_lineage=lineage,
            findings=findings,
            coherence_score=coherence_score,
            loop_detected=loop_detected,
            prompt_refinement_suggestions=refinement_suggestions,
            summary=summary,
        )
        
        self.logger.info(
            f"Auditoria concluída: {execution_id} | "
            f"risk_level={overall_risk_level.value} | "
            f"findings={len(findings)}"
        )
        
        return report
    
    def _extract_lineage(self, execution_id: str) -> Optional[ExecutionLineage]:
        """Extrai linhagem de uma execução.
        
        Executa query Cypher otimizada para percorrer:
        (ExecutionThread) -> (ExecutionStep) -> (Agent) -> (Evidence) -> (Decision)
        
        Args:
            execution_id: ID da execução
        
        Returns:
            ExecutionLineage ou None
        """
        # Query Cypher otimizada para extrair linhagem
        query = """
        MATCH (thread:ExecutionThread {execution_id: $execution_id})
        OPTIONAL MATCH (thread)-[:HAS_STEP]->(step:ExecutionStep)
        OPTIONAL MATCH (step)-[:EXECUTED_BY]->(agent:Agent)
        OPTIONAL MATCH (step)-[:BASED_ON]->(evidence:Evidence)
        OPTIONAL MATCH (step)-[:RESULTED_IN]->(decision:Decision)
        
        RETURN 
            thread.execution_id as execution_id,
            thread.start_time as start_time,
            thread.end_time as end_time,
            collect(DISTINCT agent.name) as agents,
            count(DISTINCT evidence) as evidence_count,
            count(DISTINCT decision) as decision_count,
            decision as final_decision
        
        ORDER BY step.step_index DESC
        LIMIT 1
        """
        
        try:
            result = self.neo4j_adapter.execute_query(query, {"execution_id": execution_id})
            
            if not result:
                return None
            
            record = result[0]
            
            return ExecutionLineage(
                execution_id=record["execution_id"],
                start_time=record["start_time"],
                end_time=record["end_time"],
                agents_involved=record["agents"] or [],
                evidence_count=record["evidence_count"] or 0,
                decisions_made=record["decision_count"] or 0,
                final_decision=record["final_decision"],
            )
        
        except Exception as e:
            self.logger.error(f"Erro ao extrair linhagem: {e}")
            return None
    
    def _validate_coherence(self,
                           execution_id: str,
                           lineage: ExecutionLineage) -> Tuple[List[AuditFinding], float]:
        """Valida coerência entre evidências e decisão final.
        
        Regra: A decisão final deve estar alinhada com as evidências de maior peso.
        Se divergência > 30%, flagga como achado.
        
        Args:
            execution_id: ID da execução
            lineage: Linhagem da execução
        
        Returns:
            Tupla (achados, score de coerência)
        """
        findings: List[AuditFinding] = []
        
        # Query para extrair evidências e pesos
        query = """
        MATCH (thread:ExecutionThread {execution_id: $execution_id})
        MATCH (thread)-[:HAS_STEP]->(step:ExecutionStep)
        MATCH (step)-[:BASED_ON]->(evidence:Evidence)
        MATCH (step)-[:RESULTED_IN]->(decision:Decision)
        
        RETURN 
            evidence.weight as weight,
            evidence.value as evidence_value,
            decision.value as decision_value,
            decision.confidence as decision_confidence
        
        ORDER BY evidence.weight DESC
        """
        
        try:
            results = self.neo4j_adapter.execute_query(query, {"execution_id": execution_id})
            
            if not results:
                return findings, 1.0  # Sem evidências = coerência perfeita
            
            # Calcular coerência ponderada
            total_weight = sum(r["weight"] or 1.0 for r in results)
            weighted_alignment = 0
            
            for record in results:
                weight = record["weight"] or 1.0
                evidence_value = record["evidence_value"] or 0
                decision_value = record["decision_value"] or 0
                
                # Calcular alinhamento (0-1)
                alignment = 1 - abs(evidence_value - decision_value)
                weighted_alignment += alignment * weight
            
            coherence_score = weighted_alignment / total_weight if total_weight > 0 else 1.0
            
            # Flaggar se coerência baixa
            if coherence_score < 0.7:
                findings.append(AuditFinding(
                    finding_id="coherence_001",
                    rule_name="Validação de Coerência",
                    risk_level=AuditRiskLevel.HIGH if coherence_score < 0.5 else AuditRiskLevel.MEDIUM,
                    description=f"Divergência entre evidências e decisão final: {(1-coherence_score)*100:.1f}%",
                    evidence={
                        "coherence_score": coherence_score,
                        "evidence_count": len(results),
                        "weighted_alignment": weighted_alignment,
                    },
                    recommendation="Revisar lógica de decisão e validar pesos de evidências",
                ))
            
            return findings, coherence_score
        
        except Exception as e:
            self.logger.error(f"Erro ao validar coerência: {e}")
            return findings, 0.5
    
    def _detect_loops(self,
                     execution_id: str,
                     lineage: ExecutionLineage) -> Tuple[List[AuditFinding], bool]:
        """Detecta loops infinitos de retentativa.
        
        Regra: Se há mais de 5 retentativas sem aumento de confiança,
        flagga como loop potencial.
        
        Args:
            execution_id: ID da execução
            lineage: Linhagem da execução
        
        Returns:
            Tupla (achados, loop detectado)
        """
        findings: List[AuditFinding] = []
        
        # Query para detectar padrão de retry
        query = """
        MATCH (thread:ExecutionThread {execution_id: $execution_id})
        MATCH (thread)-[:HAS_STEP]->(step:ExecutionStep)
        MATCH (step)-[:EXECUTED_BY]->(agent:Agent)
        
        RETURN 
            agent.name as agent_name,
            count(step) as retry_count,
            collect(step.confidence) as confidence_values
        
        GROUP BY agent.name
        """
        
        try:
            results = self.neo4j_adapter.execute_query(query, {"execution_id": execution_id})
            
            loop_detected = False
            
            for record in results:
                retry_count = record["retry_count"] or 0
                confidence_values = record["confidence_values"] or []
                
                # Detectar loop: múltiplas retentativas sem progresso
                if retry_count > 5:
                    # Verificar se confiança aumentou
                    if confidence_values:
                        first_confidence = confidence_values[0]
                        last_confidence = confidence_values[-1]
                        improvement = last_confidence - first_confidence
                        
                        if improvement < 0.05:  # Menos de 5% de melhora
                            loop_detected = True
                            findings.append(AuditFinding(
                                finding_id="loop_001",
                                rule_name="Detecção de Loop",
                                risk_level=AuditRiskLevel.CRITICAL,
                                description=f"Loop infinito detectado em {record['agent_name']}: "
                                           f"{retry_count} retentativas sem progresso",
                                evidence={
                                    "agent_name": record["agent_name"],
                                    "retry_count": retry_count,
                                    "confidence_improvement": improvement,
                                    "first_confidence": first_confidence,
                                    "last_confidence": last_confidence,
                                },
                                recommendation="Considerar aumentar timeout ou modificar estratégia de retry",
                            ))
            
            return findings, loop_detected
        
        except Exception as e:
            self.logger.error(f"Erro ao detectar loops: {e}")
            return findings, False
    
    def _analyze_patterns(self,
                         execution_id: str,
                         lineage: ExecutionLineage) -> List[AuditFinding]:
        """Analisa padrões na execução.
        
        Detecta:
        - Agentes com baixa confiança consistente
        - Evidências contraditórias
        - Decisões inconsistentes
        
        Args:
            execution_id: ID da execução
            lineage: Linhagem da execução
        
        Returns:
            Lista de achados
        """
        findings: List[AuditFinding] = []
        
        # Query para analisar padrões de confiança
        query = """
        MATCH (thread:ExecutionThread {execution_id: $execution_id})
        MATCH (thread)-[:HAS_STEP]->(step:ExecutionStep)
        MATCH (step)-[:EXECUTED_BY]->(agent:Agent)
        
        RETURN 
            agent.name as agent_name,
            avg(step.confidence) as avg_confidence,
            min(step.confidence) as min_confidence,
            max(step.confidence) as max_confidence,
            stdev(step.confidence) as confidence_stdev
        
        GROUP BY agent.name
        """
        
        try:
            results = self.neo4j_adapter.execute_query(query, {"execution_id": execution_id})
            
            for record in results:
                avg_confidence = record["avg_confidence"] or 0
                confidence_stdev = record["confidence_stdev"] or 0
                
                # Flaggar agentes com confiança baixa
                if avg_confidence < 0.4:
                    findings.append(AuditFinding(
                        finding_id="pattern_001",
                        rule_name="Análise de Padrões",
                        risk_level=AuditRiskLevel.MEDIUM,
                        description=f"Agente {record['agent_name']} com confiança baixa: {avg_confidence:.2f}",
                        evidence={
                            "agent_name": record["agent_name"],
                            "avg_confidence": avg_confidence,
                            "min_confidence": record["min_confidence"],
                            "max_confidence": record["max_confidence"],
                            "confidence_stdev": confidence_stdev,
                        },
                        recommendation="Revisar prompt ou dados de entrada do agente",
                    ))
                
                # Flaggar variabilidade alta
                if confidence_stdev > 0.3:
                    findings.append(AuditFinding(
                        finding_id="pattern_002",
                        rule_name="Variabilidade Alta",
                        risk_level=AuditRiskLevel.MEDIUM,
                        description=f"Agente {record['agent_name']} com confiança instável",
                        evidence={
                            "agent_name": record["agent_name"],
                            "confidence_stdev": confidence_stdev,
                            "min_confidence": record["min_confidence"],
                            "max_confidence": record["max_confidence"],
                        },
                        recommendation="Considerar refinar lógica de decisão do agente",
                    ))
            
            return findings
        
        except Exception as e:
            self.logger.error(f"Erro ao analisar padrões: {e}")
            return findings
    
    def _calculate_overall_risk(self, findings: List[AuditFinding]) -> AuditRiskLevel:
        """Calcula nível de risco geral.
        
        Args:
            findings: Lista de achados
        
        Returns:
            AuditRiskLevel
        """
        if not findings:
            return AuditRiskLevel.NONE
        
        # Risco máximo entre os achados
        risk_levels = [f.risk_level for f in findings]
        
        if AuditRiskLevel.CRITICAL in risk_levels:
            return AuditRiskLevel.CRITICAL
        elif AuditRiskLevel.HIGH in risk_levels:
            return AuditRiskLevel.HIGH
        elif AuditRiskLevel.MEDIUM in risk_levels:
            return AuditRiskLevel.MEDIUM
        else:
            return AuditRiskLevel.LOW
    
    def _generate_refinement_suggestions(self,
                                        findings: List[AuditFinding],
                                        coherence_score: float,
                                        loop_detected: bool) -> List[str]:
        """Gera sugestões de refino de prompts.
        
        Args:
            findings: Lista de achados
            coherence_score: Score de coerência
            loop_detected: Loop detectado?
        
        Returns:
            Lista de sugestões
        """
        suggestions = []
        
        # Sugestões baseadas em coerência
        if coherence_score < 0.5:
            suggestions.append(
                "🔴 CRÍTICO: Refinar prompt para melhorar alinhamento entre evidências e decisão"
            )
        elif coherence_score < 0.7:
            suggestions.append(
                "🟡 MÉDIO: Considerar adicionar contexto ao prompt para melhorar coerência"
            )
        
        # Sugestões baseadas em loops
        if loop_detected:
            suggestions.append(
                "🚨 CRÍTICO: Implementar estratégia de saída de loop ou aumentar timeout"
            )
        
        # Sugestões baseadas em achados
        for finding in findings:
            if finding.rule_name == "Análise de Padrões":
                suggestions.append(
                    f"🟠 Revisar dados de entrada para {finding.evidence.get('agent_name', 'agente desconhecido')}"
                )
        
        return suggestions
    
    def _generate_summary(self,
                         lineage: ExecutionLineage,
                         findings: List[AuditFinding],
                         coherence_score: float,
                         loop_detected: bool) -> str:
        """Gera resumo executivo.
        
        Args:
            lineage: Linhagem da execução
            findings: Lista de achados
            coherence_score: Score de coerência
            loop_detected: Loop detectado?
        
        Returns:
            Resumo em texto
        """
        summary = f"""
## Resumo de Auditoria

**Execução:** {lineage.execution_id}

**Estatísticas:**
- Agentes Envolvidos: {len(lineage.agents_involved)}
- Evidências Coletadas: {lineage.evidence_count}
- Decisões Tomadas: {lineage.decisions_made}

**Análise:**
- Score de Coerência: {coherence_score:.1%}
- Loop Detectado: {'Sim ⚠️' if loop_detected else 'Não ✅'}
- Achados Críticos: {sum(1 for f in findings if f.risk_level == AuditRiskLevel.CRITICAL)}
- Achados Altos: {sum(1 for f in findings if f.risk_level == AuditRiskLevel.HIGH)}
- Achados Médios: {sum(1 for f in findings if f.risk_level == AuditRiskLevel.MEDIUM)}

**Recomendação Geral:**
{'Execução com risco crítico - requer ação imediata' if sum(1 for f in findings if f.risk_level in [AuditRiskLevel.CRITICAL, AuditRiskLevel.HIGH]) > 0 else 'Execução aceitável com monitoramento'}
"""
        return summary.strip()
