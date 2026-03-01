import pytest
import os
import yaml
from src.rules.runbook_resolver import RunbookResolver

@pytest.fixture
def mock_catalog(tmp_path):
    catalog_content = {
        "runbooks": [
            {
                "id": "RB-TEST",
                "name": "Test Runbook",
                "service": "test-service",
                "hypotheses": ["high latency"],
                "min_confidence": 0.5,
                "risk_level": "low",
                "steps": ["Step 1"]
            }
        ]
    }
    catalog_file = tmp_path / "runbooks.yaml"
    with open(catalog_file, 'w') as f:
        yaml.dump(catalog_content, f)
    return str(catalog_file)

def test_runbook_resolver_matching(mock_catalog):
    resolver = RunbookResolver(catalog_path=mock_catalog)

    # Matching case
    matches = resolver.match_runbooks("High latency detected", "test-service", 0.6)
    assert len(matches) == 1
    assert matches[0].id == "RB-TEST"

    # Low confidence case
    matches = resolver.match_runbooks("High latency detected", "test-service", 0.4)
    assert len(matches) == 0

    # Wrong service
    matches = resolver.match_runbooks("High latency detected", "other-service", 0.6)
    assert len(matches) == 0

def test_runbook_resolver_ranking(mock_catalog):
    resolver = RunbookResolver(catalog_path=mock_catalog)
    matches = resolver.match_runbooks("High latency detected", "test-service", 0.6)
    selected = resolver.rank_and_select(matches, {})
    assert selected is not None
    assert selected.id == "RB-TEST"
