#!/usr/bin/env python3
"""
Validate that all agents in main.py can be loaded and instantiated.
Use this to verify agent registry before running main.py
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_agents():
    """Validate that all agents required by main.py are available."""
    
    logger.info("=" * 60)
    logger.info("STRANDS AGENT VALIDATION TEST")
    logger.info("=" * 60)
    
    try:
        # Import required modules
        logger.info("\n[1/4] Importing swarm intelligence modules...")
        from swarm_intelligence.registry import get_registry, load_mock_agents
        from swarm_intelligence.core.swarm import SwarmOrchestrator
        logger.info("✅ Imports successful")
        
        # Load mock agents
        logger.info("\n[2/4] Loading mock agents to registry...")
        load_mock_agents()
        logger.info("✅ Mock agents loaded")
        
        # Get registry and list available agents
        logger.info("\n[3/4] Checking agent registry...")
        registry = get_registry()
        available_agents = registry.list_agents()
        logger.info(f"📊 Total agents in registry: {len(available_agents)}")
        for agent in available_agents:
            logger.info(f"  • {agent}")
        
        # Try to instantiate each agent required by main.py
        logger.info("\n[4/4] Validating required agents from main.py...")
        required_agents = ["threat_intel", "log_analysis", "network_scanner"]
        
        instantiated_agents = []
        for agent_id in required_agents:
            try:
                # Try primary name
                if agent_id in available_agents:
                    agent = registry.create_agent(agent_id)
                    logger.info(f"✅ {agent_id}: {agent.__class__.__name__}")
                    instantiated_agents.append(agent)
                else:
                    # Try alternate name (without underscore)
                    agent_id_alt = agent_id.replace("_", "")
                    if agent_id_alt in available_agents:
                        agent = registry.create_agent(agent_id_alt)
                        logger.info(f"✅ {agent_id} (loaded as {agent_id_alt}): {agent.__class__.__name__}")
                        instantiated_agents.append(agent)
                    else:
                        logger.error(f"❌ {agent_id}: NOT FOUND")
                        logger.error(f"   Available: {available_agents}")
                        return False
            except Exception as e:
                logger.error(f"❌ {agent_id}: {str(e)}")
                return False
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("✅ VALIDATION PASSED")
        logger.info(f"Successfully instantiated {len(instantiated_agents)} agents")
        logger.info("=" * 60)
        logger.info("\n✨ Ready to run: bash run_main.sh\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ VALIDATION FAILED: {str(e)}")
        logger.error("\nTraceback:")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = validate_agents()
    sys.exit(0 if success else 1)
