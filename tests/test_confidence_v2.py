import unittest
import sys
import os

sys.path.append('/home/ubuntu/strands')
from src.services.confidence_service_v2 import ConfidenceServiceV2, RiskLevel

class TestConfidenceV2(unittest.TestCase):
    def setUp(self):
        self.service = ConfidenceServiceV2()

    def test_risk_level_thresholds(self):
        # Test critical threshold (0.95)
        res = self.service.calculate_confidence(0.9, "agent1", risk_level=RiskLevel.CRITICAL)
        self.assertFalse(res.is_above_threshold)
        
        # Test low threshold (0.50)
        res = self.service.calculate_confidence(0.6, "agent1", risk_level=RiskLevel.LOW)
        self.assertTrue(res.is_above_threshold)

    def test_category_multipliers(self):
        # Security should be stricter (lower final score for same inputs)
        res_app = self.service.calculate_confidence(0.8, "agent1", alert_category="application")
        res_sec = self.service.calculate_confidence(0.8, "agent1", alert_category="security")
        self.assertLess(res_sec.final_score, res_app.final_score)

    def test_metadata_presence(self):
        res = self.service.calculate_confidence(0.8, "agent1")
        self.assertIn("embedding", res.metadata)
        self.assertIn("weight_matrix_version", res.metadata)
        self.assertEqual(res.metadata["weight_matrix_version"], "2026-02")

if __name__ == "__main__":
    unittest.main()
