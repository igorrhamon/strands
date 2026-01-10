"""
Embedding Client - Text to Vector Conversion

Uses SentenceTransformers (text-embedding-3-small) for local embeddings.
No external API calls (free, ~5ms latency per embedding).

Research Decision: Local model for cost/latency (see research.md).
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# Model configuration (from research.md)
DEFAULT_MODEL_NAME = "text-embedding-3-small"
# Default vector dim (may be overridden by remote provider)
VECTOR_DIM = 384
DEFAULT_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")
GITHUB_MODEL_NAME = os.getenv("GITHUB_MODEL_NAME", "openai/text-embedding-3-large")
GITHUB_ENDPOINT = os.getenv("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")


class EmbeddingModelError(Exception):
    """Raised when embedding model fails to load or generate."""
    pass


class EmbeddingClient:
    """
    Embedding client with pluggable provider.

    Provider selection (env `EMBEDDING_PROVIDER`):
      - "local": use `sentence-transformers` (default)
      - "github": use GitHub-hosted models via `azure-ai-inference`

    The module avoids importing heavy local libs at import time; imports are lazy.
    """

    _instance: Optional["EmbeddingClient"] = None
    # explicit attributes for static analyzers
    _model_name: str
    _provider: str
    _remote_client: Optional[object]
    _vector_dim: int

    def __new__(cls, model_name: str = DEFAULT_MODEL_NAME, provider: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model_name = model_name
            cls._instance._provider = provider or DEFAULT_PROVIDER
            cls._instance._remote_client = None
            cls._instance._vector_dim = VECTOR_DIM
        return cls._instance

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, provider: Optional[str] = None):
        self._model_name = model_name
        if provider:
            self._provider = provider

    def _ensure_remote_client(self):
        """Lazy-init GitHub Models client using azure-ai-inference SDK."""
        if self._remote_client is None:
            try:
                from azure.ai.inference import EmbeddingsClient
                from azure.core.credentials import AzureKeyCredential

                token = os.getenv("GITHUB_TOKEN")
                if not token:
                    raise EmbeddingModelError("GITHUB_TOKEN is not set in the environment")

                endpoint = os.getenv("GITHUB_MODELS_ENDPOINT", GITHUB_ENDPOINT)
                self._remote_client = EmbeddingsClient(
                    endpoint=endpoint,
                    credential=AzureKeyCredential(token),
                )
                # model name may be overridden
                self._model_name = os.getenv("GITHUB_MODEL_NAME", self._model_name)
                # vector dim will be discovered on first call
                logger.info(f"Initialized remote embeddings client for model {self._model_name}")
            except ImportError as e:
                raise EmbeddingModelError(
                    "Remote embedding support requires 'azure-ai-inference' package."
                ) from e
            except Exception as e:
                raise EmbeddingModelError(f"Failed to initialize remote embeddings client: {e}") from e
        return self._remote_client

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")
        try:
            if self._provider == "github":
                client = self._ensure_remote_client()
                resp = client.embed(input=[text], model=self._model_name)
                data = list(resp.data)
                if not data:
                    raise EmbeddingModelError("Remote embedding returned empty response")
                emb = [float(x) for x in data[0].embedding]
                self._vector_dim = len(emb)
                return emb
            else:
                # Use local SentenceTransformer
                try:
                    result = SentenceTransformer(self._model_name).encode(text)
                    emb = result.tolist() if hasattr(result, 'tolist') else list(result)
                    self._vector_dim = len(emb)
                    return emb
                except RuntimeError as e:
                    # Shim raises RuntimeError when sentence-transformers not installed
                    raise EmbeddingModelError(str(e)) from e
        except EmbeddingModelError:
            raise
        except Exception as e:
            raise EmbeddingModelError(f"Failed to generate embedding: {e}") from e

    def generate_embedding(self, text: str) -> list[float]:
        """Alias for embed() for backward compatibility."""
        return self.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Cannot embed empty text at index {i}")
        try:
            if self._provider == "github":
                client = self._ensure_remote_client()
                resp = client.embed(input=texts, model=self._model_name)
                out = []
                for item in resp.data:
                    out.append([float(x) for x in item.embedding])
                if out:
                    self._vector_dim = len(out[0])
                return out
            else:
                # Use local SentenceTransformer
                try:
                    result = SentenceTransformer(self._model_name).encode(texts)
                    out = [row.tolist() if hasattr(row, 'tolist') else list(row) for row in result]
                    if out:
                        self._vector_dim = len(out[0])
                    return out
                except RuntimeError as e:
                    # Shim raises RuntimeError when sentence-transformers not installed
                    raise EmbeddingModelError(str(e)) from e
        except EmbeddingModelError:
            raise
        except Exception as e:
            raise EmbeddingModelError(f"Failed to generate batch embeddings: {e}") from e

    @property
    def vector_dimension(self) -> int:
        """Return the dimension of embedding vectors."""
        return getattr(self, '_vector_dim', VECTOR_DIM)

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name


# Expose a minimal SentenceTransformer shim so other modules/tests that import
# `from src.tools.embedding_client import SentenceTransformer` will not fail
# when the optional `sentence-transformers` package is not installed.
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    class SentenceTransformer:  # type: ignore
        """Minimal shim that raises a helpful error on use."""
        def __init__(self, model_name: str):
            raise RuntimeError(
                "sentence-transformers is not installed. Install it to use local embeddings, "
                "or set EMBEDDING_PROVIDER=github to use remote GitHub-hosted embeddings."
            )


def create_embedding_text(
    alert_description: str,
    service: str,
    severity: str,
    decision_summary: str,
    rules_applied: list[str],
) -> str:
    """
    Format text for embedding generation.
    
    Combines alert context with decision outcome for semantic search.
    
    Args:
        alert_description: Human-readable alert text.
        service: Service name from alert.
        severity: Alert severity (critical/warning/info).
        decision_summary: Justification from decision.
        rules_applied: List of rules that contributed to decision.
    
    Returns:
        Formatted text suitable for embedding.
    """
    rules_str = ", ".join(rules_applied) if rules_applied else "none"
    
    return (
        f"Alert: {alert_description} | "
        f"Service: {service} | "
        f"Severity: {severity} | "
        f"Decision: {decision_summary} | "
        f"Rules: {rules_str}"
    )
