"""
Agent Registry and Factory

Provides a centralized registry for discovering and instantiating agents.
Supports both built-in agents and dynamically loaded plugins.
"""

from typing import Dict, Type, List, Optional
import importlib
import logging

from swarm_intelligence.core.swarm import Agent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for agent classes.
    
    Allows registration of agent classes by ID and provides factory methods
    for creating agent instances.
    """
    
    def __init__(self):
        self._agents: Dict[str, Type[Agent]] = {}
    
    def register(self, agent_id: str, agent_class: Type[Agent]) -> None:
        """Register an agent class with the given ID."""
        if agent_id in self._agents:
            logger.warning(f"Overwriting existing agent registration: {agent_id}")
        self._agents[agent_id] = agent_class
        logger.info(f"Registered agent: {agent_id} -> {agent_class.__name__}")
    
    def unregister(self, agent_id: str) -> None:
        """Unregister an agent by ID."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
    
    def get(self, agent_id: str) -> Optional[Type[Agent]]:
        """Get an agent class by ID."""
        return self._agents.get(agent_id)
    
    def create(self, agent_id: str, **kwargs) -> Agent:
        """
        Create an agent instance by ID.
        
        Args:
            agent_id: The agent identifier
            **kwargs: Additional arguments to pass to the agent constructor
            
        Returns:
            An instantiated agent
            
        Raises:
            ValueError: If agent_id is not registered
        """
        agent_class = self.get(agent_id)
        if agent_class is None:
            raise ValueError(f"Agent not registered: {agent_id}")
        
        # Pass agent_id as first argument if not in kwargs
        if "agent_id" not in kwargs:
            return agent_class(agent_id, **kwargs)
        return agent_class(**kwargs)
    
    def list_agents(self) -> List[str]:
        """List all registered agent IDs."""
        return list(self._agents.keys())
    
    def load_from_module(self, module_path: str, agent_classes: List[str]) -> None:
        """
        Dynamically load agent classes from a module.
        
        Args:
            module_path: Python module path (e.g., 'examples.mock_agents')
            agent_classes: List of class names to load
        """
        try:
            module = importlib.import_module(module_path)
            for class_name in agent_classes:
                agent_class = getattr(module, class_name, None)
                if agent_class is None:
                    logger.warning(f"Class not found in {module_path}: {class_name}")
                    continue
                
                # Use the class name as the default agent_id
                agent_id = class_name.lower().replace("agent", "").replace("_", "")
                self.register(agent_id, agent_class)
                
        except ImportError as e:
            logger.error(f"Failed to load module {module_path}: {e}")
            raise


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def register_agent(agent_id: str, agent_class: Type[Agent]) -> None:
    """Convenience function to register an agent in the global registry."""
    get_registry().register(agent_id, agent_class)


def create_agent(agent_id: str, **kwargs) -> Agent:
    """Convenience function to create an agent from the global registry."""
    return get_registry().create(agent_id, **kwargs)


def load_mock_agents() -> None:
    """Load mock agents for testing/development."""
    registry = get_registry()
    registry.load_from_module(
        "examples.mock_agents",
        ["ThreatIntelAgent", "LogAnalysisAgent", "NetworkScannerAgent"]
    )
    logger.info("Loaded mock agents for development")


def load_real_agents() -> None:
    """Load real agent adapters for production use.
    
    These adapters wrap the actual agents from src/agents to be compatible
    with the SwarmOrchestrator interface.
    """
    registry = get_registry()
    
    try:
        from examples.real_agents import (
            CorrelatorAgentAdapter,
            LogInspectorAgentAdapter,
            MetricsAnalysisAgentAdapter,
            AlertCorrelatorAgentAdapter,
            RecommenderAgentAdapter,
        )
        
        # Register with explicit agent IDs to avoid naming conflicts
        registry.register("correlator", CorrelatorAgentAdapter)
        registry.register("loginspector", LogInspectorAgentAdapter)
        registry.register("metricsanalyzer", MetricsAnalysisAgentAdapter)
        registry.register("alertcorrelator", AlertCorrelatorAgentAdapter)
        registry.register("recommender", RecommenderAgentAdapter)
        
        logger.info("Loaded real agent adapters for production")
    except ImportError as e:
        logger.warning(f"Real agents not available, using mock agents only: {e}")


def load_all_agents() -> None:
    """Load both mock and real agents."""
    load_mock_agents()
    load_real_agents()
    logger.info("Loaded all agents (mock + real adapters)")
