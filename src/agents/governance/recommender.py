"""
Recommender Agent - Análise Avançada de Recomendações

Analisa candidatos de decisão para propor ações técnicas específicas,
refinar avaliações de risco e validar níveis de automação.

Responsabilidades:
1. Refinar recomendações com planos de ação específicos
2. Avaliar risco com base em padrões conhecidos
3. Validar níveis de automação baseado em risco
4. Incorporar insights de incidentes similares
5. Gerar playbooks de remediação
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime, timezone

from src.models.decision import DecisionCandidate, AutomationLevel, DecisionStatus

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Níveis de risco para uma decisão."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    MINIMAL = "MINIMAL"


class RemediationPlaybook:
    """Representa um playbook de remediação com passos específicos."""
    
    def __init__(
        self,
        name: str,
        description: str,
        steps: List[str],
        risk_level: RiskLevel,
        estimated_time_minutes: int,
        requires_manual_approval: bool
    ):
        self.name = name
        self.description = description
        self.steps = steps
        self.risk_level = risk_level
        self.estimated_time_minutes = estimated_time_minutes
        self.requires_manual_approval = requires_manual_approval
    
    def to_dict(self) -> Dict:
        """Converte playbook para dicionário."""
        return {
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "risk_level": self.risk_level.value,
            "estimated_time_minutes": self.estimated_time_minutes,
            "requires_manual_approval": self.requires_manual_approval
        }


class RecommenderAgent:
    """
    Agente responsável por analisar candidatos de decisão e propor ações técnicas específicas.
    
    Funcionalidades:
    - Refinar recomendações com planos de ação detalhados
    - Avaliar risco com base em padrões conhecidos
    - Validar níveis de automação baseado em risco
    - Incorporar insights de incidentes similares
    - Gerar playbooks de remediação
    """
    
    agent_id = "recommender"
    
    # Mapeamento de padrões para playbooks
    PLAYBOOK_TEMPLATES = {
        "cpu": RemediationPlaybook(
            name="CPU Saturation Playbook",
            description="Remediação para saturação de CPU",
            steps=[
                "1. Verificar limites de CPU via 'kubectl describe pod'",
                "2. Analisar processos com maior consumo de CPU",
                "3. Considerar aumentar requests de CPU",
                "4. Avaliar escala horizontal (mais replicas)",
                "5. Otimizar código se necessário",
                "6. Monitorar recuperação"
            ],
            risk_level=RiskLevel.HIGH,
            estimated_time_minutes=15,
            requires_manual_approval=True
        ),
        "memory": RemediationPlaybook(
            name="Memory Leak Playbook",
            description="Remediação para vazamento de memória",
            steps=[
                "1. Verificar tendência de memória via Prometheus",
                "2. Analisar heap dumps se disponível",
                "3. Aumentar limites de memória temporariamente",
                "4. Escalar horizontalmente se necessário",
                "5. Investigar possível memory leak no código",
                "6. Considerar restart periódico como workaround",
                "7. Monitorar após correção"
            ],
            risk_level=RiskLevel.CRITICAL,
            estimated_time_minutes=30,
            requires_manual_approval=True
        ),
        "restart": RemediationPlaybook(
            name="Pod Restart Loop Playbook",
            description="Remediação para restart contínuo de pods",
            steps=[
                "1. Coletar logs do pod para erros de startup",
                "2. Verificar configuração de liveness/readiness probes",
                "3. Analisar dependências externas (DB, APIs)",
                "4. Verificar variáveis de ambiente",
                "5. Considerar aumentar startup timeout",
                "6. Revisar mudanças recentes de deployment",
                "7. Considerar rollback se recente"
            ],
            risk_level=RiskLevel.HIGH,
            estimated_time_minutes=20,
            requires_manual_approval=True
        ),
        "latency": RemediationPlaybook(
            name="High Latency Playbook",
            description="Remediação para latência alta",
            steps=[
                "1. Identificar serviço downstream com latência alta",
                "2. Verificar políticas de rede",
                "3. Analisar endpoints de serviço",
                "4. Verificar timeouts de conexão",
                "5. Considerar cache se apropriado",
                "6. Escalar serviço downstream se necessário",
                "7. Monitorar P95/P99 latency"
            ],
            risk_level=RiskLevel.MEDIUM,
            estimated_time_minutes=25,
            requires_manual_approval=False
        ),
        "error_rate": RemediationPlaybook(
            name="High Error Rate Playbook",
            description="Remediação para taxa de erro alta",
            steps=[
                "1. Analisar tipos de erro nos logs",
                "2. Verificar disponibilidade de dependências",
                "3. Analisar métricas de sucesso/falha",
                "4. Implementar retry logic se apropriado",
                "5. Considerar circuit breaker",
                "6. Escalar serviço se necessário",
                "7. Monitorar taxa de erro"
            ],
            risk_level=RiskLevel.MEDIUM,
            estimated_time_minutes=20,
            requires_manual_approval=False
        )
    }
    
    def __init__(self):
        """Inicializa o RecommenderAgent."""
        self.detected_playbooks: List[RemediationPlaybook] = []
    
    def refine_recommendation(self, candidate: DecisionCandidate) -> DecisionCandidate:
        """
        Refina o candidato de decisão com planos de ação específicos.
        
        Args:
            candidate: Candidato de decisão a refinar
            
        Returns:
            Candidato de decisão refinado com ações específicas
        """
        logger.info(f"[{self.agent_id}] Refinando recomendação para {candidate.decision_id}")
        
        # Limpar playbooks detectados anteriormente
        self.detected_playbooks = []
        
        # Analisar hipótese e gerar ações específicas
        self._analyze_hypothesis_and_generate_actions(candidate)
        
        # Avaliar risco
        risk_level = self._assess_risk(candidate)
        
        # Validar nível de automação baseado em risco
        self._validate_automation_level(candidate, risk_level)
        
        # Incorporar insights de incidentes similares
        self._incorporate_similar_incidents(candidate)
        
        # Gerar playbook consolidado
        self._generate_consolidated_playbook(candidate)
        
        logger.info(f"[{self.agent_id}] Recomendação refinada com {len(candidate.suggested_actions)} ações")
        
        return candidate
    
    def _analyze_hypothesis_and_generate_actions(self, candidate: DecisionCandidate) -> None:
        """
        Analisa a hipótese principal e gera ações técnicas específicas.
        
        Args:
            candidate: Candidato de decisão
        """
        hypothesis_lower = candidate.primary_hypothesis.lower()
        
        # Analisar padrões de CPU
        if "cpu" in hypothesis_lower:
            self._handle_cpu_issue(candidate)
        
        # Analisar padrões de memória
        elif "memory" in hypothesis_lower or "oom" in hypothesis_lower:
            self._handle_memory_issue(candidate)
        
        # Analisar padrões de restart
        elif "crashloopbackoff" in hypothesis_lower or "restarting" in hypothesis_lower:
            self._handle_restart_issue(candidate)
        
        # Analisar padrões de latência
        elif "timeout" in hypothesis_lower or "latency" in hypothesis_lower:
            self._handle_latency_issue(candidate)
        
        # Analisar padrões de taxa de erro
        elif "error" in hypothesis_lower or "failed" in hypothesis_lower:
            self._handle_error_rate_issue(candidate)
        
        # Padrão genérico
        else:
            self._handle_generic_issue(candidate)
    
    def _handle_cpu_issue(self, candidate: DecisionCandidate) -> None:
        """Trata problema de CPU."""
        playbook = self.PLAYBOOK_TEMPLATES["cpu"]
        self.detected_playbooks.append(playbook)
        
        candidate.risk_assessment = "CPU saturation detected. Standard CPU saturation playbook applies."
        candidate.suggested_actions.extend(playbook.steps)
        candidate.selected_action = "Increase CPU requests and monitor"
    
    def _handle_memory_issue(self, candidate: DecisionCandidate) -> None:
        """Trata problema de memória."""
        playbook = self.PLAYBOOK_TEMPLATES["memory"]
        self.detected_playbooks.append(playbook)
        
        candidate.risk_assessment = "Memory leak or high memory usage detected. Critical risk of OOMKilled."
        candidate.suggested_actions.extend(playbook.steps)
        candidate.selected_action = "Increase memory limits and investigate leak"
    
    def _handle_restart_issue(self, candidate: DecisionCandidate) -> None:
        """Trata problema de restart contínuo."""
        playbook = self.PLAYBOOK_TEMPLATES["restart"]
        self.detected_playbooks.append(playbook)
        
        candidate.risk_assessment = "Service instability with restart loop detected."
        candidate.suggested_actions.extend(playbook.steps)
        candidate.selected_action = "Investigate startup errors and fix root cause"
    
    def _handle_latency_issue(self, candidate: DecisionCandidate) -> None:
        """Trata problema de latência."""
        playbook = self.PLAYBOOK_TEMPLATES["latency"]
        self.detected_playbooks.append(playbook)
        
        candidate.risk_assessment = "Performance degradation with high latency detected."
        candidate.suggested_actions.extend(playbook.steps)
        candidate.selected_action = "Investigate downstream dependencies"
    
    def _handle_error_rate_issue(self, candidate: DecisionCandidate) -> None:
        """Trata problema de taxa de erro."""
        playbook = self.PLAYBOOK_TEMPLATES["error_rate"]
        self.detected_playbooks.append(playbook)
        
        candidate.risk_assessment = "High error rate detected in application."
        candidate.suggested_actions.extend(playbook.steps)
        candidate.selected_action = "Analyze error logs and implement mitigation"
    
    def _handle_generic_issue(self, candidate: DecisionCandidate) -> None:
        """Trata problema genérico."""
        candidate.risk_assessment = "Generic issue detected. Manual investigation required."
        candidate.suggested_actions.append("Collect diagnostic information")
        candidate.suggested_actions.append("Review application logs")
        candidate.suggested_actions.append("Check system metrics")
        candidate.selected_action = "Manual review and investigation"
    
    def _assess_risk(self, candidate: DecisionCandidate) -> RiskLevel:
        """
        Avalia o nível de risco da decisão.
        
        Args:
            candidate: Candidato de decisão
            
        Returns:
            Nível de risco detectado
        """
        risk_keywords = {
            RiskLevel.CRITICAL: ["critical", "oommemory", "data loss", "security"],
            RiskLevel.HIGH: ["high", "cpu", "memory", "restart", "crash"],
            RiskLevel.MEDIUM: ["medium", "latency", "error rate", "degradation"],
            RiskLevel.LOW: ["low", "warning", "info"],
            RiskLevel.MINIMAL: ["minimal", "informational"]
        }
        
        hypothesis_lower = candidate.primary_hypothesis.lower()
        
        for risk_level, keywords in risk_keywords.items():
            if any(keyword in hypothesis_lower for keyword in keywords):
                return risk_level
        
        return RiskLevel.MEDIUM
    
    def _validate_automation_level(self, candidate: DecisionCandidate, risk_level: RiskLevel) -> None:
        """
        Valida e ajusta nível de automação baseado em risco.
        
        Args:
            candidate: Candidato de decisão
            risk_level: Nível de risco detectado
        """
        # Forçar MANUAL para risco CRITICAL ou HIGH
        if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            if candidate.automation_level != AutomationLevel.MANUAL:
                logger.warning(
                    f"Downgrading automation level to MANUAL due to {risk_level.value} Risk "
                    f"for {candidate.decision_id}"
                )
                candidate.automation_level = AutomationLevel.MANUAL
                candidate.summary += f" (Automation downgraded due to {risk_level.value} Risk)"
        
        # Permitir ASSISTED para risco MEDIUM
        elif risk_level == RiskLevel.MEDIUM:
            if candidate.automation_level == AutomationLevel.FULL:
                logger.info(f"Downgrading automation level to ASSISTED for {candidate.decision_id}")
                candidate.automation_level = AutomationLevel.ASSISTED
        
        # Permitir FULL para risco LOW ou MINIMAL
        # (sem mudança necessária)
    
    def _incorporate_similar_incidents(self, candidate: DecisionCandidate) -> None:
        """
        Incorpora insights de incidentes similares.
        
        Args:
            candidate: Candidato de decisão
        """
        if "similar incident" in candidate.summary.lower():
            candidate.risk_assessment += " Recurrent issue pattern detected - consider permanent fix."
            candidate.suggested_actions.insert(0, "Review similar incident history for patterns")
    
    def _generate_consolidated_playbook(self, candidate: DecisionCandidate) -> None:
        """
        Gera playbook consolidado baseado em padrões detectados.
        
        Args:
            candidate: Candidato de decisão
        """
        if not self.detected_playbooks:
            return
        
        # Usar playbook mais relevante (primeiro detectado)
        primary_playbook = self.detected_playbooks[0]
        
        # Adicionar informações do playbook ao candidato
        candidate.supporting_evidence.append(
            f"Playbook: {primary_playbook.name} (Est. {primary_playbook.estimated_time_minutes} min)"
        )
        
        # Atualizar automação se playbook requer aprovação manual
        if primary_playbook.requires_manual_approval:
            candidate.automation_level = AutomationLevel.MANUAL
        
        logger.info(
            f"[{self.agent_id}] Playbook selecionado: {primary_playbook.name} "
            f"(Risco: {primary_playbook.risk_level.value})"
        )
    
    def get_playbook_for_hypothesis(self, hypothesis: str) -> Optional[RemediationPlaybook]:
        """
        Retorna playbook apropriado para uma hipótese.
        
        Args:
            hypothesis: Hipótese a analisar
            
        Returns:
            Playbook apropriado ou None
        """
        hypothesis_lower = hypothesis.lower()
        
        for pattern, playbook in self.PLAYBOOK_TEMPLATES.items():
            if pattern in hypothesis_lower:
                return playbook
        
        return None
    
    def get_all_playbooks(self) -> Dict[str, Dict]:
        """
        Retorna todos os playbooks disponíveis.
        
        Returns:
            Dicionário com todos os playbooks
        """
        return {
            pattern: playbook.to_dict()
            for pattern, playbook in self.PLAYBOOK_TEMPLATES.items()
        }
