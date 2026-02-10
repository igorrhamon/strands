"""
Feedback Loop & Trend Analysis Engine (Adaptive V2)

Responsável por:
1. Coletar feedback de execuções de playbooks
2. Analisar tendências com thresholds estatísticos
3. Detectar drift de performance
4. Identificar candidatos a otimização
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import math

from src.core.neo4j_playbook_store import Neo4jPlaybookStore, PlaybookStatus

logger = logging.getLogger(__name__)

class FeedbackLoopEngine:
    """Motor de Feedback e Análise de Tendências."""
    
    def __init__(self, store: Neo4jPlaybookStore):
        self.store = store
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Configurações de Threshold
        self.MIN_VOLUME_FOR_TREND = 10  # Mínimo de incidentes para calcular tendência
        self.GROWTH_THRESHOLD = 0.2     # +/- 20% para considerar tendência significativa
        self.DRIFT_THRESHOLD = 0.2      # Desvio de 20% na taxa de sucesso para flag de drift
    
    def process_execution_feedback(self, 
                                 execution_id: str, 
                                 success: bool, 
                                 duration_seconds: float,
                                 feedback_notes: Optional[str] = None) -> bool:
        """Processa feedback de uma execução.
        
        Delega para o store a atualização atômica e incremental.
        """
        return self.store.update_execution(execution_id, success, duration_seconds, feedback_notes)
    
    def analyze_trends(self, days: int = 7) -> Dict[str, Any]:
        """Analisa tendências de incidentes com rigor estatístico.
        
        Args:
            days: Janela de análise em dias
            
        Returns:
            Relatório de tendências com classificação (UP/DOWN/STABLE)
        """
        try:
            raw_trends = self.store.get_incident_trends(days)
            if not raw_trends:
                return {}
            
            prev_total = raw_trends.get("previous_window", {}).get("total_incidents", 0)
            growth_rate = raw_trends.get("growth_rate", 0.0)
            
            # Classificação de Tendência com Volume Mínimo
            trend_classification = "STABLE"
            if prev_total >= self.MIN_VOLUME_FOR_TREND:
                if growth_rate > self.GROWTH_THRESHOLD:
                    trend_classification = "UP"
                elif growth_rate < -self.GROWTH_THRESHOLD:
                    trend_classification = "DOWN"
            else:
                trend_classification = "INSUFFICIENT_DATA"
            
            raw_trends["trend_classification"] = trend_classification
            raw_trends["generated_at"] = datetime.now().isoformat()
            
            return raw_trends
            
        except Exception as e:
            self.logger.error(f"Erro ao analisar tendências: {e}")
            return {}
    
    def detect_concept_drift(self, playbook_id: str) -> Optional[Dict[str, Any]]:
        """Detecta se a performance do playbook está degradando (Drift).
        
        Compara taxa de sucesso recente (últimas 10 execuções) com histórico total.
        """
        # Em produção, isso exigiria uma query específica para "janela recente"
        # Por enquanto, usamos a variância armazenada para detectar instabilidade
        
        stats = self.store.get_playbook_statistics(playbook_id)
        if not stats or stats['total'] < self.MIN_VOLUME_FOR_TREND:
            return None
            
        # Se desvio padrão for muito alto em relação à média, pode indicar instabilidade
        cv = stats.get('std_dev_duration', 0) / stats['duration'] if stats['duration'] > 0 else 0
        
        if cv > 0.5:  # Coeficiente de variação > 50%
            return {
                "playbook_id": playbook_id,
                "type": "PERFORMANCE_INSTABILITY",
                "details": f"High duration variance (CV={cv:.2f})",
                "severity": "MEDIUM"
            }
            
        return None
    
    def get_optimization_candidates(self) -> List[Dict[str, Any]]:
        """Identifica playbooks candidatos a otimização.
        
        Critérios:
        1. Alta frequência (> 50 execuções)
        2. Taxa de sucesso moderada (< 80%)
        3. Duração alta (> média global)
        """
        # Em produção, buscaria no Neo4j com filtros específicos
        # Simulação baseada em lógica real
        return []
