"""
Resilience & Stress Tests - Strands Platform
Simulates infrastructure failures and high load to ensure safe degradation.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.append('/home/ubuntu/strands')
from src.deduplication.distributed_deduplicator import DistributedEventDeduplicator, DeduplicationAction
from src.services.confidence_service_v2 import ConfidenceServiceV2

class TestResilience(unittest.TestCase):
    
    def test_redis_failure_fallback(self):
        """Test that system continues to work even if Redis is down."""
        # Mocking redis to raise connection error
        with patch('redis.from_url') as mock_redis:
            mock_redis.side_effect = Exception("Connection Refused")
            
            deduplicator = DistributedEventDeduplicator(redis_url="redis://invalid:6379")
            
            # Should not crash, should return NEW_EXECUTION as fallback
            action, exec_id = deduplicator.check_duplicate("alert_1", {"data": "test"})
            self.assertEqual(action, DeduplicationAction.NEW_EXECUTION)
            self.assertIsNone(exec_id)

    def test_embedding_model_failure(self):
        """Test that semantic recovery handles model loading failures."""
        from src.services.semantic_recovery_service import SemanticRecoveryService
        
        with patch('sentence_transformers.SentenceTransformer') as mock_model:
            mock_model.side_effect = Exception("Model Load Error")
            
            service = SemanticRecoveryService()
            # Should initialize with self._model = None and not crash
            self.assertIsNone(service._model)

    def test_high_concurrency_lock(self):
        """Simulate high load and lock contention."""
        # This is a logic test for the lock mechanism
        deduplicator = DistributedEventDeduplicator()
        # Mock redis for lock
        deduplicator._redis = MagicMock()
        
        # Simulate lock already held
        deduplicator._redis.set.return_value = False
        lock_acquired = deduplicator.acquire_lock("busy_resource")
        self.assertFalse(lock_acquired)
        
        # Simulate lock free
        deduplicator._redis.set.return_value = True
        lock_acquired = deduplicator.acquire_lock("free_resource")
        self.assertTrue(lock_acquired)

if __name__ == "__main__":
    unittest.main()
EOF
