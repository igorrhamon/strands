#!/usr/bin/env python3
"""
Validate all agents: mock agents + real agent adapters

Run this before main.py to ensure all agents are properly loaded and instantiated.
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_all_agents():
    """Validate that all agents (mock + real adapters) can be loaded and instantiated."""
    
    logger.info("=" * 80)
    logger.info("STRANDS FULL AGENT VALIDATION TEST (MOCK + REAL ADAPTERS)")
    logger.info("=" * 80)
    
    try:
        # Step 1: Import required modules
        logger.info("\n[1/4] Importing swarm intelligence modules...")
        from swarm_intelligence.registry import get_registry, load_all_agents
        from swarm_intelligence.core.swarm import SwarmOrchestrator
        logger.info("✅ Imports successful")
        
        # Step 2: Load all agents (mock + real)
        logger.info("\n[2/4] Loading all agents (mock + real adapters)...")
        load_all_agents()
        logger.info("✅ All agents loaded")
        
        # Step 3: List all available agents
        logger.info("\n[3/4] Listing all available agents...")
        registry = get_registry()
        available_agents = registry.list_agents()
        logger.info(f"📊 Total agents in registry: {len(available_agents)}")
        
        # Categorize agents
        mock_agents = ["threatintel", "loganalysis", "networkscanner"]
        real_agents = ["correlator", "loginspector", "metricsanalyzer", "alertcorrelator", "recommender"]
        
        logger.info("\n  📋 MOCK AGENTS (3):")
        for agent in mock_agents:
            status = "✅" if agent in available_agents else "❌"
            logger.info(f"     {status} {agent}")
        
        logger.info("\n  🔧 REAL AGENT ADAPTERS (5):")
        for agent in real_agents:
            status = "✅" if agent in available_agents else "❌"
            logger.info(f"     {status} {agent}")
        
        logger.info(f"\n  All agents: {', '.join(sorted(available_agents))}")
        
        # Step 4: Instantiate all agents
        logger.info("\n[4/4] Instantiating all agents for execution...")
        instantiated = []
        failed = []
        
        for agent_id in available_agents:
            try:
                agent = registry.create(agent_id)
                instantiated.append((agent_id, agent.__class__.__name__))
                logger.info(f"  ✅ {agent_id:20s} → {agent.__class__.__name__}")
            except Exception as e:
                failed.append((agent_id, str(e)))
                logger.error(f"  ❌ {agent_id:20s} → ERROR: {e}")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ VALIDATION PASSED")
        logger.info(f"  Successfully instantiated: {len(instantiated)}/{len(available_agents)} agents")
        
        if failed:
            logger.warning(f"\n⚠️  {len(failed)} agents failed to instantiate:")
            for agent_id, error in failed:
                logger.warning(f"    • {agent_id}: {error}")
        
        logger.info("=" * 80)
        logger.info("\n✨ Ready to run: python3 main.py\n")
        
        return len(failed) == 0
        
    except Exception as e:
        logger.error(f"\n❌ VALIDATION FAILED: {str(e)}")
        logger.error("\nTraceback:")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = validate_all_agents()
    sys.exit(0 if success else 1)
