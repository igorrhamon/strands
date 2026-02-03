import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from src.agents.analysis.embedding_agent import EmbeddingAgent
from src.models.alert import NormalizedAlert
from src.models.decision import DecisionCandidate
from src.models.swarm import SwarmResult


def make_alert():
    return NormalizedAlert(
        timestamp=datetime.now(timezone.utc),
        fingerprint="fp1",
        service="checkout",
        severity="critical",
        description="Payment gateway errors observed",
        labels={}
    )


def test_analyze_with_match(monkeypatch):
    # Arrange
    fake_vector = [0.1, 0.2, 0.3]
    fake_payload = {"source_text": "Incident #99: Payment gateway timeout", "source_url": "http://itsm/inc/99"}
    fake_hit = {"score": 0.82, "payload": fake_payload}

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = fake_vector

    mock_repo = MagicMock()
    mock_repo.search_similar.return_value = [fake_hit]

    monkeypatch.setattr('src.agents.analysis.embedding_agent.EmbeddingClient', lambda: mock_embedder)

    agent = EmbeddingAgent(mock_repo)

    # Act
    result: SwarmResult = agent.analyze(make_alert())

    # Assert
    assert isinstance(result, SwarmResult)
    assert "Similar incident" in result.hypothesis or "Incident" in result.hypothesis
    assert result.confidence >= 0.8
    assert len(result.evidence) == 1
    mock_repo.search_similar.assert_called_once()


def test_analyze_no_match(monkeypatch):
    # Arrange
    fake_vector = [0.1, 0.2, 0.3]

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = fake_vector

    mock_repo = MagicMock()
    mock_repo.search_similar.return_value = []

    monkeypatch.setattr('src.agents.analysis.embedding_agent.EmbeddingClient', lambda: mock_embedder)

    agent = EmbeddingAgent(mock_repo)

    # Act
    result: SwarmResult = agent.analyze(make_alert())

    # Assert
    assert isinstance(result, SwarmResult)
    assert "No similar incidents" in result.hypothesis
    assert result.confidence < 0.5
    mock_repo.search_similar.assert_called_once()


def test_index_resolution_upserts(monkeypatch):
    # Arrange
    fake_vector = [0.1, 0.2, 0.3]
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = fake_vector

    mock_repo = MagicMock()
    mock_repo.ensure_collection.return_value = None
    mock_repo.upsert_embedding.return_value = None

    monkeypatch.setattr('src.agents.analysis.embedding_agent.EmbeddingClient', lambda: mock_embedder)

    agent = EmbeddingAgent(mock_repo)

    candidate = DecisionCandidate(
        alert_reference="checkout",
        summary="Restart payment pod",
        primary_hypothesis="Payment pod OOM",
        risk_assessment="low",
        automation_level="MANUAL",
    )

    # Act
    agent.index_resolution(candidate)

    # Assert
    mock_repo.ensure_collection.assert_called_once()
    mock_repo.upsert_embedding.assert_called_once()
