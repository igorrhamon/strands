import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
from swarm_intelligence.coordinators.swarm_run_coordinator import SwarmRunCoordinator
from swarm_intelligence.core.models import SwarmPlan, Alert, Decision, Domain, SwarmRun, RiskLevel
from swarm_intelligence.core.monitor_policy import MonitorPolicy, EscalationAction

@pytest.mark.asyncio
async def test_monitor_scheduling():
    # Mocks
    exec_ctrl = MagicMock()
    retry_ctrl = MagicMock()
    decision_ctrl = MagicMock()
    conf_svc = MagicMock()
    
    coordinator = SwarmRunCoordinator(
        execution_controller=exec_ctrl,
        retry_controller=retry_ctrl,
        decision_controller=decision_ctrl,
        confidence_service=conf_svc
    )
    
    # Setup test data
    domain = Domain(id="test", name="Test", description="Test", risk_level=RiskLevel.MEDIUM)
    plan = SwarmPlan(objective="Test", steps=[])
    alert = Alert(alert_id="alert_123", data={"alertname": "TestAlert"})
    
    # Mock decision to be MONITOR
    mock_decision = Decision(
        summary="Monitoring incident",
        action_proposed="MONITOR",
        confidence=0.8,
        supporting_evidence=[],
        monitor_policy=MonitorPolicy(recheck_after_minutes=1, max_rechecks=2)
    )
    
    # Mock aexecute_plan to return a finished run
    async def mock_aexecute_plan(*args, **kwargs):
        return (
            SwarmRun(run_id="run_1", domain=domain, plan=plan, master_seed=123, final_decision=mock_decision),
            [], []
        )
    coordinator.aexecute_plan = mock_aexecute_plan

    # Trigger the monitor handler
    await coordinator._handle_monitor_decision(domain, plan, alert, "run_1", mock_decision)
    
    # Check if job was added to scheduler
    jobs = coordinator.scheduler.get_jobs()
    assert len(jobs) == 1
    assert coordinator.monitor_states["run_1"].recheck_count == 1
    
    print("✅ MONITOR job scheduled successfully.")

    # Trigger second recheck
    await coordinator._handle_monitor_decision(domain, plan, alert, "run_1", mock_decision)
    assert coordinator.monitor_states["run_1"].recheck_count == 2
    
    # Trigger escalation
    await coordinator._handle_monitor_decision(domain, plan, alert, "run_1", mock_decision)
    assert coordinator.monitor_states["run_1"].recheck_count == 2 # Should not increment
    
    print("✅ Escalation triggered after max rechecks.")

if __name__ == "__main__":
    asyncio.run(test_monitor_scheduling())
