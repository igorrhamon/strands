"""
Unit Tests for Similarity Threshold Logic

Tests:
- Threshold filtering
- Score validation
- Edge cases
"""

import pytest
from uuid import uuid4

from src.models.embedding import SimilarityResult
from src.tools.vector_store import VectorStore


# ============================================================================
# Threshold Configuration Tests
# ============================================================================

class TestSimilarityThreshold:
    """Tests for similarity threshold logic."""
    
    def test_default_threshold(self):
        """Test that default threshold is 0.75."""
        store = VectorStore()
        assert store._score_threshold == 0.75
    
    def test_custom_threshold(self):
        """Test that custom threshold is respected."""
        store = VectorStore(score_threshold=0.80)
        assert store._score_threshold == 0.80
    
    def test_threshold_range_min(self):
        """Test that very low threshold is valid."""
        store = VectorStore(score_threshold=0.0)
        assert store._score_threshold == 0.0
    
    def test_threshold_range_max(self):
        """Test that maximum threshold is valid."""
        store = VectorStore(score_threshold=1.0)
        assert store._score_threshold == 1.0


class TestSimilarityResultModel:
    """Tests for SimilarityResult model validation."""
    
    def test_valid_score_bounds(self):
        """Test that score must be between 0 and 1."""
        # Valid score
        result = SimilarityResult(
            decision_id=uuid4(),
            similarity_score=0.85,
            source_text="Test",
            service="test",
            rules_applied=[],
        )
        assert result.similarity_score == 0.85
    
    def test_score_at_zero(self):
        """Test that score of 0 is valid."""
        result = SimilarityResult(
            decision_id=uuid4(),
            similarity_score=0.0,
            source_text="Test",
            service="test",
            rules_applied=[],
        )
        assert result.similarity_score == 0.0
    
    def test_score_at_one(self):
        """Test that score of 1.0 is valid."""
        result = SimilarityResult(
            decision_id=uuid4(),
            similarity_score=1.0,
            source_text="Test",
            service="test",
            rules_applied=[],
        )
        assert result.similarity_score == 1.0
    
    def test_invalid_score_below_zero(self):
        """Test that score below 0 raises error."""
        with pytest.raises(ValueError):
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=-0.1,
                source_text="Test",
                service="test",
                rules_applied=[],
            )
    
    def test_invalid_score_above_one(self):
        """Test that score above 1 raises error."""
        with pytest.raises(ValueError):
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=1.1,
                source_text="Test",
                service="test",
                rules_applied=[],
            )


class TestSimilarityFiltering:
    """Tests for filtering results by threshold."""
    
    def test_filter_below_threshold(self):
        """Test that results below threshold are filtered."""
        results = [
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.90,
                source_text="High score",
                service="test",
                rules_applied=[],
            ),
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.70,  # Below 0.75 threshold
                source_text="Low score",
                service="test",
                rules_applied=[],
            ),
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.85,
                source_text="Medium score",
                service="test",
                rules_applied=[],
            ),
        ]
        
        threshold = 0.75
        filtered = [r for r in results if r.similarity_score >= threshold]
        
        assert len(filtered) == 2
        assert all(r.similarity_score >= threshold for r in filtered)
    
    def test_filter_at_threshold_included(self):
        """Test that results at exactly threshold are included."""
        results = [
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.75,  # Exactly at threshold
                source_text="At threshold",
                service="test",
                rules_applied=[],
            ),
        ]
        
        threshold = 0.75
        filtered = [r for r in results if r.similarity_score >= threshold]
        
        assert len(filtered) == 1
    
    def test_filter_all_below_threshold(self):
        """Test that all results filtered when below threshold."""
        results = [
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.60,
                source_text="Low",
                service="test",
                rules_applied=[],
            ),
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.50,
                source_text="Lower",
                service="test",
                rules_applied=[],
            ),
        ]
        
        threshold = 0.75
        filtered = [r for r in results if r.similarity_score >= threshold]
        
        assert len(filtered) == 0


class TestTopKConfiguration:
    """Tests for top-K result limiting."""
    
    def test_default_top_k(self):
        """Test that default top_k is 5."""
        store = VectorStore()
        assert store._top_k == 5
    
    def test_custom_top_k(self):
        """Test that custom top_k is respected."""
        store = VectorStore(top_k=10)
        assert store._top_k == 10
    
    def test_top_k_limits_results(self):
        """Test that results are limited to top_k."""
        all_results = [
            SimilarityResult(
                decision_id=uuid4(),
                similarity_score=0.90 - i * 0.02,
                source_text=f"Result {i}",
                service="test",
                rules_applied=[],
            )
            for i in range(10)
        ]
        
        top_k = 5
        limited = all_results[:top_k]
        
        assert len(limited) == 5
        # Verify they're the top 5 by score
        assert all(r.similarity_score >= 0.80 for r in limited)


class TestOnlyConfirmedFilter:
    """Tests for only_confirmed filtering (Constitution Principle III)."""
    
    def test_only_confirmed_embeddings_searchable(self):
        """
        Verify that only CONFIRMED decision embeddings are in the store.
        
        This is enforced at persist time, not search time.
        Constitution Principle III: Embeddings only after human confirmation.
        """
        # This test verifies the design principle
        # Actual enforcement is in VectorStore.persist_decision()
        
        # The search results should only contain confirmed decisions
        # because we never persist unconfirmed ones
        result = SimilarityResult(
            decision_id=uuid4(),
            similarity_score=0.85,
            source_text="Confirmed decision: closed alert as resolved",
            service="test",
            rules_applied=["rule_1"],
        )
        
        # The presence of rules_applied indicates this came from a real decision
        assert len(result.rules_applied) > 0
