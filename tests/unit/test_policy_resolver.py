"""
Unit tests for ImmediateRetryPolicy and PolicyResolver.
"""
import pytest
from unittest.mock import MagicMock

from swarm_intelligence.policy.retry_policy import (
    ExponentialBackoffPolicy,
    ImmediateRetryPolicy,
    RetryContext,
)
from swarm_intelligence.policy.policy_resolver import PolicyResolver


# ---------------------------------------------------------------------------
# ImmediateRetryPolicy
# ---------------------------------------------------------------------------

class TestImmediateRetryPolicy:

    def test_calculate_delay_always_zero(self):
        policy = ImmediateRetryPolicy(max_retries=5)
        for attempt in range(10):
            assert policy.calculate_delay(attempt) == 0.0

    def test_should_retry_within_max(self):
        policy = ImmediateRetryPolicy(max_retries=3, max_attempts=3)
        assert policy.should_retry(RetryContext(attempt=0)) is True
        assert policy.should_retry(RetryContext(attempt=2)) is True

    def test_should_not_retry_when_exhausted(self):
        policy = ImmediateRetryPolicy(max_retries=3, max_attempts=3)
        assert policy.should_retry(RetryContext(attempt=4)) is False

    def test_default_max_retries_is_three(self):
        policy = ImmediateRetryPolicy()
        assert policy.max_retries == 3


# ---------------------------------------------------------------------------
# ExponentialBackoffPolicy (regression)
# ---------------------------------------------------------------------------

class TestExponentialBackoffPolicy:

    def test_delay_increases_exponentially(self):
        policy = ExponentialBackoffPolicy(base_delay=1.0, backoff_factor=2.0, max_delay=60.0)
        delays = [policy.calculate_delay(i) for i in range(5)]
        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_delay_capped_at_max(self):
        policy = ExponentialBackoffPolicy(base_delay=10.0, backoff_factor=3.0, max_delay=15.0)
        assert policy.calculate_delay(2) == 15.0  # 90 > 15 → capped


# ---------------------------------------------------------------------------
# PolicyResolver
# ---------------------------------------------------------------------------

class TestPolicyResolver:

    def _make_resolver(self, policy_names):
        mock_adapter = MagicMock()
        mock_adapter.get_policies_for_domain.return_value = policy_names
        return PolicyResolver(neo4j_adapter=mock_adapter)

    def test_resolves_exponential_backoff(self):
        resolver = self._make_resolver(["ExponentialBackoffPolicy"])
        domain = MagicMock()
        domain.id = "infra"
        policy = resolver.resolve_policy(domain, RetryContext())
        assert isinstance(policy, ExponentialBackoffPolicy)

    def test_resolves_immediate_retry(self):
        resolver = self._make_resolver(["ImmediateRetry"])
        domain = MagicMock()
        domain.id = "infra"
        policy = resolver.resolve_policy(domain, RetryContext())
        assert isinstance(policy, ImmediateRetryPolicy)
        # Must NOT silently fall through to ExponentialBackoffPolicy
        assert policy.calculate_delay(0) == 0.0

    def test_unknown_policy_falls_back_to_exponential(self):
        resolver = self._make_resolver(["UnknownPolicyXYZ"])
        domain = MagicMock()
        domain.id = "infra"
        policy = resolver.resolve_policy(domain, RetryContext())
        assert isinstance(policy, ExponentialBackoffPolicy)

    def test_no_domain_policies_returns_default(self):
        resolver = self._make_resolver([])
        domain = MagicMock()
        domain.id = "infra"
        policy = resolver.resolve_policy(domain, RetryContext())
        assert isinstance(policy, ExponentialBackoffPolicy)
