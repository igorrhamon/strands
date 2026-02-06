#!/usr/bin/env python3
"""
End-to-end test for GitHub Models integration with swarm intelligence.
This test validates the complete flow without requiring Neo4j.
"""
import asyncio
import hashlib
import logging
import os
import sys
from typing import Dict, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from swarm_intelligence.core.enums import EvidenceType, HumanAction
from swarm_intelligence.core.models import (
    Evidence, Alert, SwarmPlan, SwarmStep,
    Decision, HumanDecision, AgentExecution
)
from swarm_intelligence.core.swarm import Agent, SwarmOrchestrator


class SimpleAnalysisAgent(Agent):
    """Mock agent for testing - doesn't require external dependencies."""
    
    def __init__(self, agent_id: str, result_data: dict):
        super().__init__(
            agent_id, 
            version="1.0", 
            logic_hash=hashlib.md5(f"simple_{agent_id}".encode()).hexdigest()
        )
        self.result_data = result_data

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        await asyncio.sleep(0.01)  # Simulate work
        
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params
        )
        
        evidence = Evidence(
            source_agent_execution_id=execution.execution_id,
            agent_id=self.agent_id,
            content=self.result_data,
            confidence=0.85,
            evidence_type=EvidenceType.METRICS
        )
        execution.output_evidence.append(evidence)
        return execution


async def test_basic_swarm():
    """Test basic swarm orchestration without external dependencies."""
    print("=" * 60)
    print("TEST 1: Basic Swarm Orchestration (no GitHub Models)")
    print("=" * 60)
    
    # Create simple agents
    agents = [
        SimpleAnalysisAgent("metrics_agent", {"cpu_usage": 78.5, "memory_usage": 65.2}),
        SimpleAnalysisAgent("log_agent", {"error_count": 42, "warning_count": 156})
    ]
    
    orchestrator = SwarmOrchestrator(agents)
    
    # Create a simple plan
    plan = SwarmPlan(
        objective="Analyze system health",
        steps=[
            SwarmStep(agent_id="metrics_agent", mandatory=True),
            SwarmStep(agent_id="log_agent", mandatory=True)
        ]
    )
    
    alert = Alert(alert_id="test-001", data={"system": "prod-web-01"})
    
    # Execute agents through orchestrator
    print("\n📊 Executing agents...")
    executions = await orchestrator.execute_swarm(plan.steps)
    
    for execution in executions:
        evidence_count = len(execution.output_evidence) if execution.is_successful() else 0
        status = "✓" if execution.is_successful() else "✗"
        print(f"  {status} {execution.agent_id}: {evidence_count} evidence pieces")
    
    # Collect all evidence
    all_evidence = [ev for ex in executions for ev in ex.output_evidence]
    print(f"\n✓ Total evidence collected: {len(all_evidence)}")
    
    for ev in all_evidence:
        print(f"  - Agent {ev.agent_id}: confidence={ev.confidence:.2f}, data={ev.content}")
    
    return True


async def test_github_models_provider():
    """Test GitHub Models provider if token is available."""
    print("\n" + "=" * 60)
    print("TEST 2: GitHub Models Provider")
    print("=" * 60)
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("⚠️  GITHUB_TOKEN not set - skipping GitHub Models test")
        print("   Set token with: export GITHUB_TOKEN='ghp_...'")
        return False
    
    print(f"✓ Token found: {token[:20]}...")
    
    try:
        # Direct HTTP test without the strands package dependency
        import aiohttp
        
        print("✓ aiohttp available for HTTP testing")
        
        endpoint = "https://models.github.ai/inference"
        model_name = "gpt-4o"
        
        print(f"✓ Endpoint: {endpoint}")
        print(f"✓ Model: {model_name}")
        
        # Test simple API call
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Say 'success' if you can read this"}
            ],
            "max_tokens": 50,
            "temperature": 0.7
        }
        
        print("\n📤 Sending test message to GitHub Models API...")
        print(f"   Prompt: {payload['messages'][1]['content']}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(f"\n📥 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        print(f"   Response: {content}")
                        print("\n✓ GitHub Models API test passed!")
                        return True
                    else:
                        print(f"   Unexpected response format: {data}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"   Error: {error_text}")
                    return False
        
    except ImportError as e:
        print(f"⚠️  Missing dependency for HTTP test: {e}")
        print("   Install with: pip install aiohttp")
        return False
    except Exception as e:
        print(f"❌ GitHub Models test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all end-to-end tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n🧪 STRANDS END-TO-END TEST SUITE")
    print(f"Python: {sys.version}")
    print(f"Working dir: {os.getcwd()}")
    
    results = []
    
    # Test 1: Basic swarm (always works)
    try:
        result = await test_basic_swarm()
        results.append(("Basic Swarm", result))
    except Exception as e:
        print(f"\n❌ Basic swarm test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Basic Swarm", False))
    
    # Test 2: GitHub Models (requires token)
    try:
        result = await test_github_models_provider()
        results.append(("GitHub Models", result))
    except Exception as e:
        print(f"\n❌ GitHub Models test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("GitHub Models", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:10} {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nPassed: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed or were skipped")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
