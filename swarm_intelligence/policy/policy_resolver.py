
from typing import List, Optional
from swarm_intelligence.core.models import Domain
from swarm_intelligence.policy.retry_policy import RetryPolicy, RetryContext, ExponentialBackoffPolicy
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter

class PolicyResolver:
    """
    Resolves the appropriate retry policy for a given context, with a focus on
    domain-specific policies.
    """

    def __init__(self, neo4j_adapter: Neo4jAdapter):
        self.neo4j_adapter = neo4j_adapter

    def resolve_policy(self, domain: Domain, context: RetryContext) -> RetryPolicy:
        """
        Resolves the best retry policy for the given domain and context.
        """
        # Step 1: Fetch policies valid for the domain from Neo4j
        policy_names = self.neo4j_adapter.get_policies_for_domain(domain.id)

        # Step 2: If no domain-specific policies, fallback to a default
        if not policy_names:
            # In a real system, this would be a well-defined institutional default
            return ExponentialBackoffPolicy()

        # Step 3: For now, use the first valid policy.
        # Future enhancement: Add ranking and selection logic here.
        policy_name = policy_names[0]

        # Step 4: Instantiate the policy by name.
        # This is simplified; a real implementation would use a factory or registry.
        if policy_name == "ExponentialBackoffPolicy":
            return ExponentialBackoffPolicy()
        elif policy_name == "ImmediateRetry":
            # Assuming an ImmediateRetryPolicy exists
            # from .retry_policy import ImmediateRetryPolicy
            # return ImmediateRetryPolicy()
            pass

        # Fallback if the policy name is unknown
        return ExponentialBackoffPolicy()
