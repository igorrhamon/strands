import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone
from src.agents.governance.human_review import HumanReviewAgent
from src.models.decision import DecisionCandidate, DecisionValidation, DecisionStatus, AutomationLevel

@pytest.fixture
def mock_candidate():
    return DecisionCandidate(
        decision_id=uuid4(),
        alert_reference="alert-123",
        summary="Test summary",
        status=DecisionStatus.PROPOSED,
        primary_hypothesis="Test hypothesis",
        risk_assessment="Low",
        automation_level=AutomationLevel.MANUAL,
        created_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def mock_repo():
    repo = Mock()
    repo.record_decision_outcome = Mock()
    return repo

@pytest.mark.asyncio
async def test_review_approval(mock_candidate, mock_repo):
    agent = HumanReviewAgent(mock_repo)
    
    validation = DecisionValidation(
        validation_id="val-1",
        decision_id=mock_candidate.decision_id,
        validated_by="operator",
        is_approved=True,
        feedback="Looks good"
    )
    
    result = await agent.process_review(mock_candidate, validation)
    
    assert result.status == DecisionStatus.APPROVED
    mock_repo.record_decision_outcome.assert_called_once_with(validation)

@pytest.mark.asyncio
async def test_review_rejection(mock_candidate, mock_repo):
    agent = HumanReviewAgent(mock_repo)
    
    validation = DecisionValidation(
        validation_id="val-2",
        decision_id=mock_candidate.decision_id,
        validated_by="operator",
        is_approved=False,
        feedback="Wrong hypothesis"
    )
    
    result = await agent.process_review(mock_candidate, validation)
    
    assert result.status == DecisionStatus.REJECTED
    mock_repo.record_decision_outcome.assert_called_once_with(validation)

@pytest.mark.asyncio
async def test_id_mismatch(mock_candidate, mock_repo):
    agent = HumanReviewAgent(mock_repo)
    
    validation = DecisionValidation(
        validation_id="val-3",
        decision_id=uuid4(), # Different ID
        validated_by="operator",
        is_approved=True
    )
    
    with pytest.raises(ValueError, match="Validation ID mismatch"):
        await agent.process_review(mock_candidate, validation)
