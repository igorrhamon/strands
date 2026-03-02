"""
Runbook Resolver - Deterministic selection of runbooks based on context.
"""

import logging
import yaml
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class Runbook:
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.description = data.get("description")
        self.service = data.get("service")
        self.hypotheses = data.get("hypotheses", [])
        self.min_confidence = data.get("min_confidence", 0.0)
        self.risk_level = data.get("risk_level", "medium")
        self.steps = data.get("steps", [])

class RunbookResolver:
    """
    Resolves relevant runbooks based on hypothesis, service, and confidence.
    """
    def __init__(self, catalog_path: str = "src/rules/catalog/runbooks.yaml"):
        self.catalog_path = catalog_path
        self.runbooks: List[Runbook] = []
        self._load_catalog()

    def _load_catalog(self):
        if not os.path.exists(self.catalog_path):
            logger.warning(f"Runbook catalog not found at {self.catalog_path}")
            return

        try:
            with open(self.catalog_path, 'r') as f:
                data = yaml.safe_load(f)
                if data and "runbooks" in data:
                    self.runbooks = [Runbook(rb) for rb in data["runbooks"]]
            logger.info(f"Loaded {len(self.runbooks)} runbooks from catalog")
        except Exception as e:
            logger.error(f"Failed to load runbook catalog: {e}")

    def match_runbooks(self, hypothesis: str, service: str, confidence: float) -> List[Runbook]:
        import re
        matches = []

        # Tokenize hypothesis for better matching (word boundaries)
        hypothesis_tokens = set(re.findall(r'\w+', hypothesis.lower()))

        for rb in self.runbooks:
            # Service match (or 'any')
            service_match = (rb.service == "any" or rb.service == service)

            # Token-based match for hypothesis
            # Ensures "No High CPU" doesn't naively match "High CPU"
            hyp_match = False
            for h in rb.hypotheses:
                h_tokens = re.findall(r'\w+', h.lower())
                # Check if all tokens of a runbook hypothesis are present in the target hypothesis
                if all(tok in hypothesis_tokens for tok in h_tokens):
                    hyp_match = True
                    break

            # Confidence threshold
            conf_match = (confidence >= rb.min_confidence)

            if service_match and hyp_match and conf_match:
                matches.append(rb)

        return matches

    def rank_and_select(self, matches: List[Runbook], context: Dict[str, Any]) -> Optional[Runbook]:
        """
        Ranks matched runbooks and selects the best one.
        Ensures stable, deterministic sorting.
        """
        if not matches:
            return None

        # Multi-level stable sort:
        # 1. Risk Level (low first)
        # 2. Number of steps (shorter first as heuristic for simplicity)
        # 3. ID as tie-breaker (absolute determinism)
        def rank_key(rb):
            risk_score = {"low": 0, "medium": 1, "high": 2}.get(rb.risk_level, 1)
            return (risk_score, len(rb.steps), rb.id)

        sorted_matches = sorted(matches, key=rank_key)
        return sorted_matches[0]
