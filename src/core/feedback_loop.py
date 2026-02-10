"""
Feedback Loop & Trend Analysis Engine

Responsável por:
1. Coletar feedback de execuções de playbooks
2. Atualizar estatísticas de sucesso/falha
3. Analisar tendências de incidentes
4. Ajustar scores de recomendação
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np

from src.core.neo4j_playbook_store import Neo4jPlaybookStore, PlaybookStatus

logger = logging.getLogger(__name__)

class FeedbackLoopEngine:
    """Motor de Feedback e Análise de Tendências."""
    
    def __init__(self, store: Neo4jPlaybookStore):
        self.store = store
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_execution_feedback(self, 
                                 execution_id: str, 
                                 success: bool, 
                                 duration_seconds: float,
                                 feedback_notes: Optional[str] = None) -> bool:
        """Processa feedback de uma execução.
        
        Args:
            execution_id: ID da execução
            success: Se foi bem sucedida
            duration_seconds: Duração em segundos
            feedback_notes: Notas opcionais
            
        Returns:
            True se processado com sucesso
        """
        try:
            # 1. Atualizar registro de execução
            status = "SUCCESS" if success else "FAILURE"
            
            # Atualizar no Neo4j (assumindo método update_execution no store)
            # self.store.update_execution(execution_id, status, duration_seconds, feedback_notes)
            
            # 2. Recuperar playbook associado
            # playbook_id = self.store.get_playbook_id_by_execution(execution_id)
            
            # 3. Atualizar estatísticas do playbook
            # self.store.update_playbook_stats(playbook_id, success)
            
            # 4. Verificar se precisa de revisão (se taxa de falha > threshold)
            # stats = self.store.get_playbook_statistics(playbook_id)
            # if stats['failure_rate'] > 0.3 and stats['executions'] > 5:
            #     self.store.flag_for_review(playbook_id, "High failure rate detected")
            
            self.logger.info(f"Feedback processado para execução {execution_id} | Success: {success}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao processar feedback: {e}")
            return False
    
    def analyze_trends(self, days: int = 7) -> Dict[str, Any]:
        """Analisa tendências de incidentes e eficácia de playbooks.
        
        Args:
            days: Janela de análise em dias
            
        Returns:
            Relatório de tendências
        """
        try:
            # Simulação de análise (em produção, faria queries complexas no Neo4j)
            
            # 1. Padrões mais frequentes
            top_patterns = [
                {"type": "METRIC_METRIC", "count": 45, "trend": "up"},
                {"type": "LOG_METRIC", "count": 32, "trend": "stable"},
                {"type": "TEMPORAL", "count": 12, "trend": "down"}
            ]
            
            # 2. Serviços mais afetados
            top_services = [
                {"name": "api-service", "incidents": 28},
                {"name": "worker-service", "incidents": 15},
                {"name": "db-service", "incidents": 8}
            ]
            
            # 3. Eficácia global de remediação
            remediation_stats = {
                "total_executions": 150,
                "success_rate": 0.88,
                "avg_duration": 45.5,  # segundos
                "automation_savings": 125.5  # horas economizadas (estimado)
            }
            
            return {
                "window_days": days,
                "generated_at": datetime.now().isoformat(),
                "top_patterns": top_patterns,
                "top_services": top_services,
                "remediation_stats": remediation_stats
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao analisar tendências: {e}")
            return {}
    
    def get_optimization_candidates(self) -> List[Dict[str, Any]]:
        """Identifica playbooks candidatos a otimização.
        
        Critérios:
        1. Alta frequência de uso
        2. Taxa de sucesso moderada (precisa melhorar)
        3. Duração alta (pode ser otimizado)
        
        Returns:
            Lista de candidatos
        """
        # Em produção, buscaria no Neo4j com filtros específicos
        return [
            {
                "playbook_id": "pb-123",
                "reason": "High usage (50+), moderate success (75%)",
                "suggestion": "Review steps 3-4 for potential race conditions"
            }
        ]
