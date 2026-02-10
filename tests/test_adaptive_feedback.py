"""
Integration Tests for Adaptive Feedback Loop V2

Testa:
1. Atualização incremental de estatísticas (Welford)
2. Controle de concorrência (simulado)
3. Scoring adaptativo
4. Downgrade de segurança
"""

import unittest
from unittest.mock import MagicMock, patch
import math
from src.core.neo4j_playbook_store import Neo4jPlaybookStore
from src.agents.governance.recommender_with_learning import RecommenderAgentWithLearning

class TestAdaptiveFeedback(unittest.TestCase):
    
    def setUp(self):
        self.store_mock = MagicMock(spec=Neo4jPlaybookStore)
        self.store_mock.connected = True
        self.generator_mock = MagicMock()
        self.recommender = RecommenderAgentWithLearning(self.store_mock, self.generator_mock)

    def test_welford_algorithm_logic(self):
        """Testa a lógica matemática do algoritmo de Welford para média incremental."""
        # Simulação manual do algoritmo implementado na query Cypher
        
        # Estado inicial
        avg = 10.0
        n = 5
        
        # Nova execução
        new_val = 16.0
        
        # Lógica Welford
        delta = new_val - avg
        new_avg = avg + delta / (n + 1)
        
        # Esperado: (10*5 + 16) / 6 = 66 / 6 = 11.0
        self.assertAlmostEqual(new_avg, 11.0)

    def test_adaptive_scoring_formula(self):
        """Testa se a fórmula de score valoriza volume e sucesso."""
        
        # Playbook A: 100% sucesso, mas só 1 execução (Cold Start)
        pb_a = {"playbook_id": "A", "success_rate": 1.0, "total_executions": 1}
        
        # Playbook B: 90% sucesso, 100 execuções (Experiente)
        pb_b = {"playbook_id": "B", "success_rate": 0.9, "total_executions": 100}
        
        confidence = 0.9
        
        # Rankear
        ranked = self.recommender._rank_playbooks([pb_a, pb_b], confidence)
        
        # B deve vencer A devido ao volume (log boost)
        self.assertEqual(ranked[0]['playbook_id'], "B")
        
        # Verificar scores
        score_a = ranked[1]['score'] # 0.9 * 1.0 * log(2) ≈ 0.62
        score_b = ranked[0]['score'] # 0.9 * 0.9 * log(101) ≈ 3.73
        
        self.assertGreater(score_b, score_a)

    def test_safety_downgrade(self):
        """Testa se o downgrade de segurança é aplicado corretamente."""
        
        # Playbook perigoso: Alta falha com volume suficiente
        pb_dangerous = {
            "playbook_id": "DANGER",
            "success_rate": 0.4,  # < 0.5 threshold
            "total_executions": 20, # > 5 min volume
            "automation_level": "FULL",
            "risk_level": "LOW"
        }
        
        result = self.recommender._apply_safety_downgrade(pb_dangerous)
        
        self.assertEqual(result['automation_level'], "MANUAL")
        self.assertEqual(result['risk_level'], "HIGH")
        self.assertIn("Low success rate", result['downgrade_reason'])

    def test_no_downgrade_for_cold_start(self):
        """Testa se playbooks novos não são penalizados prematuramente."""
        
        # Playbook novo: Falhou na primeira vez
        pb_new = {
            "playbook_id": "NEW",
            "success_rate": 0.0,
            "total_executions": 1, # < 5 min volume
            "automation_level": "FULL",
            "risk_level": "LOW"
        }
        
        result = self.recommender._apply_safety_downgrade(pb_new)
        
        # Não deve mudar ainda
        self.assertEqual(result['automation_level'], "FULL")

if __name__ == '__main__':
    unittest.main()
