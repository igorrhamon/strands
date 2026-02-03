from .analyzer import AlertAnalyzer
from .schemas import AgentInput, AgentOutput

class GrafanaAlertAgent:
    def run(self, input: AgentInput) -> AgentOutput:
        """
        Run the Grafana Alert Analysis Agent.
        
        Args:
            input: AgentInput object
            
        Returns:
            AgentOutput object
        """
        analyzer = AlertAnalyzer()
        return analyzer.execute(input)
