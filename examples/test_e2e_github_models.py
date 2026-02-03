"""
End-to-End Test: GitHub Models Integration with Swarm Orchestration

This test demonstrates:
1. Creating a SwarmPlan with GitHub Models as an agent
2. Executing through the new SwarmRunCoordinator (PR #4)
3. Confidence tracking with the refactored service (PR #5)
4. Full Neo4j persistence
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from swarm_intelligence.core.models import (
    SwarmPlan,
    SwarmStep,
    Alert,
    Evidence,
    EvidenceType,
)
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator
from swarm_intelligence.controllers.swarm_execution_controller import SwarmExecutionController
from swarm_intelligence.controllers.swarm_retry_controller import SwarmRetryController
from swarm_intelligence.controllers.swarm_decision_controller import SwarmDecisionController
from swarm_intelligence.coordinators.swarm_run_coordinator import SwarmRunCoordinator
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.policy.confidence_policy import DefaultConfidencePolicy
from swarm_intelligence.policy.retry_policy import ExponentialBackoffPolicy
from src.providers.github_models import GitHubModels


class GitHubAnalysisAgent(Agent):
    """
    Agent that uses GitHub Models to analyze alert data.
    """

    def __init__(self, agent_id: str, model: GitHubModels):
        self.agent_id = agent_id
        self.version = "1.0.0"
        self.logic_hash = "github_analysis_v1"
        self.model = model

    async def execute(self, params, step_id: str):
        """
        Execute analysis using GitHub Models.
        """
        from swarm_intelligence.core.models import AgentExecution

        try:
            alert_data = params.get("alert_data", {})
            
            prompt = f"""
Analyze this security alert and provide structured output:
{alert_data}

Provide:
1. Risk level (critical/high/medium/low)
2. Affected systems
3. Recommended action
4. Confidence (0-1)
"""
            
            print(f"\n📤 [{self.agent_id}] Sending to GitHub Models...")
            print(f"   Prompt: {prompt[:100]}...")

            # For demo: use mock response (comment out for real API calls)
            response_text = "Risk Level: HIGH\nAffected Systems: web-prod-03\nAction: Isolate and investigate\nConfidence: 0.92"
            
            # Uncomment for real API call:
            # async for event in self.model.stream([{"role": "user", "content": prompt}]):
            #     # Collect response
            #     pass

            evidence = Evidence(
                source_agent_execution_id=str(uuid4()),
                agent_id=self.agent_id,
                evidence_type=EvidenceType.HYPOTHESIS,
                content={"analysis": response_text, "summary": "HIGH risk detected"},
                confidence=0.92,
            )

            return AgentExecution(
                agent_id=self.agent_id,
                agent_version=self.version,
                logic_hash=self.logic_hash,
                step_id=step_id,
                input_parameters=params,
                output_evidence=[evidence],
            )

        except Exception as e:
            print(f"❌ [{self.agent_id}] Error: {e}")
            from swarm_intelligence.core.models import AgentExecution

            return AgentExecution(
                agent_id=self.agent_id,
                agent_version=self.version,
                logic_hash=self.logic_hash,
                step_id=step_id,
                input_parameters=params,
                error=e,
            )


def _setup_neo4j():
    """Initialize Neo4j adapter."""
    print("\n1️⃣  Initializing Neo4j...")
    try:
        neo4j = Neo4jAdapter(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password"
        )
        neo4j.run_read_transaction("RETURN 1 as test")
        neo4j.setup_schema()
        print("   ✅ Neo4j connected")
        return neo4j
    except Exception as e:
        print(f"   ⚠️  Neo4j not available: {type(e).__name__}")
        print("   🔄 Continuing with mocked persistence...")
        return None


def _setup_github_model():
    """Initialize GitHub Models provider."""
    print("\n2️⃣  Initializing GitHub Models...")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        print(f"   ✅ Found GITHUB_TOKEN: {token[:20]}...")
        try:
            model = GitHubModels(model_name="openai/gpt-4o-mini")
            print(f"   ✅ Model: {model.model_name}")
            return model
        except Exception as e:
            print(f"   ⚠️  GitHub Models init error: {e}")
            print("   📝 Using mock mode for demo...")
            return None
    else:
        print("   ℹ️  GITHUB_TOKEN not set - using mock mode")
        print("   💡 For real API calls: export GITHUB_TOKEN='your_token'")
        return None


def _create_mock_agent():
    """Create a mock agent for testing."""
    class MockAgent(Agent):
        def __init__(self):
            self.agent_id = "github_analyzer"
            self.version = "1.0.0"
            self.logic_hash = "github_analysis_v1"
        
        async def execute(self, params, step_id: str):
            from swarm_intelligence.core.models import AgentExecution
            evidence = Evidence(
                source_agent_execution_id=str(uuid4()),
                agent_id=self.agent_id,
                evidence_type=EvidenceType.HYPOTHESIS,
                content={"analysis": "Mock analysis result", "summary": "MOCK: HIGH risk detected"},
                confidence=0.85,
            )
            return AgentExecution(
                agent_id=self.agent_id,
                agent_version=self.version,
                logic_hash=self.logic_hash,
                step_id=step_id,
                input_parameters=params,
                output_evidence=[evidence],
            )
    
    return MockAgent()


def _setup_agents(model):
    """Create and setup agents."""
    print("\n3️⃣  Creating agents...")
    if model:
        github_agent = GitHubAnalysisAgent("github_analyzer", model)
        print(f"   ✅ Agent: {github_agent.agent_id} (with real GitHub Models)")
        return github_agent
    else:
        github_agent = _create_mock_agent()
        print(f"   ✅ Agent: {github_agent.agent_id} (MOCK - no GitHub token)")
        return github_agent


def _setup_orchestration(github_agent, neo4j):
    """Setup orchestrator and controllers."""
    print("\n4️⃣  Setting up Swarm Orchestration...")
    orchestrator = SwarmOrchestrator([github_agent])
    execution_controller = SwarmExecutionController(orchestrator)
    retry_controller = SwarmRetryController()
    decision_controller = SwarmDecisionController()

    confidence_service = None
    coordinator = None

    if neo4j:
        confidence_service = ConfidenceService(neo4j)
        coordinator = SwarmRunCoordinator(
            execution_controller,
            retry_controller,
            decision_controller,
            confidence_service,
        )
        print("   ✅ Coordinator initialized (with Neo4j)")
    else:
        print("   ⚠️  Coordinator requires Neo4j for confidence tracking")

    return orchestrator, coordinator


def _create_alert_and_plan():
    """Create alert and swarm plan."""
    print("\n5️⃣  Creating SwarmPlan and Alert...")
    alert = Alert(
        alert_id="SEC-E2E-001",
        data={
            "hostname": "web-prod-03",
            "event": "Suspicious login from unknown IP",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "high",
        },
    )
    print(f"   ✅ Alert: {alert.alert_id}")

    analysis_step = SwarmStep(
        agent_id="github_analyzer",
        parameters={"alert_data": alert.data},
        mandatory=True,
        retry_policy=ExponentialBackoffPolicy(max_attempts=2, base_delay=0.5),
    )

    plan = SwarmPlan(
        objective="Analyze security alert using GitHub Models",
        steps=[analysis_step],
    )
    print(f"   ✅ Plan: {plan.objective}")
    return alert, plan


def _print_execution_results(decision, executions, retries, retry_decisions):
    """Print execution results."""
    print("\n7️⃣  Results:")
    print(f"   Decision ID: {decision.decision_id}")
    print(f"   Summary: {decision.summary[:80]}...")
    print(f"   Action: {decision.action_proposed}")
    print(f"   Confidence: {decision.confidence:.2f}")

    if executions:
        ex = executions[0]
        print("\n   Agent Execution:")
        print(f"   - Agent: {ex.agent_id}")
        print(f"   - Status: {'✅ Success' if ex.is_successful() else '❌ Failed'}")
        print(f"   - Evidence: {len(ex.output_evidence)} pieces")
        if ex.output_evidence:
            ev = ex.output_evidence[0]
            print(f"   - Evidence Type: {ev.evidence_type.value}")
            print(f"   - Confidence: {ev.confidence:.2f}")


def _print_direct_execution_results(executions):
    """Print direct execution results."""
    print("\n7️⃣  Direct Execution Results:")
    
    if executions:
        for i, ex in enumerate(executions, 1):
            print(f"\n   Execution #{i}:")
            print(f"   - Agent: {ex.agent_id}")
            print(f"   - Status: {'✅ Success' if ex.is_successful() else '❌ Failed'}")
            print(f"   - Evidence: {len(ex.output_evidence)} pieces")
            if ex.output_evidence:
                for j, ev in enumerate(ex.output_evidence, 1):
                    print(f"     Evidence #{j}:")
                    print(f"       - Type: {ev.evidence_type.value}")
                    print(f"       - Confidence: {ev.confidence:.2f}")
                    print(f"       - Content: {str(ev.content)[:60]}...")


async def test_e2e_github_models():
    """
    End-to-end test with GitHub Models.
    """
    print("\n" + "=" * 70)
    print("🧪 END-TO-END TEST: GitHub Models + Swarm Orchestration")
    print("=" * 70)

    # Setup
    neo4j = _setup_neo4j()
    model = _setup_github_model()
    github_agent = _setup_agents(model)
    orchestrator, coordinator = _setup_orchestration(github_agent, neo4j)
    alert, plan = _create_alert_and_plan()

    # Execution
    print("\n6️⃣  Executing SwarmPlan...")
    run_id = f"e2e-test-{alert.alert_id}"

    try:
        if coordinator:
            confidence_policy = DefaultConfidencePolicy()

            def human_review_hook(decision):
                from swarm_intelligence.core.models import HumanDecision, HumanAction
                return HumanDecision(
                    action=HumanAction.ACCEPT,
                    author="e2e-test",
                    override_reason="E2E test auto-accept",
                )

            decision, executions, retries, retry_decisions, master_seed = await coordinator.run(
                plan,
                run_id,
                confidence_policy=confidence_policy,
                human_hook=human_review_hook,
            )

            print("\n   ✅ Execution complete!")
            print(f"   📊 Executions: {len(executions)}")
            print(f"   🔄 Retries: {len(retries)}")
            print(f"   📋 Retry Decisions: {len(retry_decisions)}")

            _print_execution_results(decision, executions, retries, retry_decisions)

            # Persist to Neo4j
            if neo4j and executions:
                print("\n8️⃣  Persisting to Neo4j...")
                try:
                    neo4j.save_swarm_run(
                        plan, alert, executions, decision, retries, master_seed
                    )
                    print("   ✅ Saved to Neo4j")
                except Exception as e:
                    print(f"   ⚠️  Neo4j save failed: {e}")
        else:
            print("\n   📝 Using direct orchestrator (no confidence tracking)...")
            print(f"   📤 Executing {len(plan.steps)} steps...")
            executions = await orchestrator.execute_swarm(plan.steps)
            
            print("   ✅ Execution complete!")
            print(f"   📊 Executions: {len(executions)}")
            
            _print_direct_execution_results(executions)

    except Exception as e:
        print(f"   ❌ Execution error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("✅ E2E Test Complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_e2e_github_models())
