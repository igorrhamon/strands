"""
Refactored Pipeline with Real Integrations
- Ollama local embeddings
- Qdrant vector store (local)
- GitHub MCP repository context
- Pluggable, minimal, production-ready
"""

import logging
import os
from typing import Optional, Any
from datetime import datetime, timezone
from uuid import UUID

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from src.models.cluster import AlertCluster
from src.models.embedding import SimilarityResult
from src.models.decision import SemanticEvidence

logger = logging.getLogger(__name__)


class OllamaEmbedder:
    """Local LLaMA embeddings via Ollama HTTP API."""
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "nomic-embed-text:latest",
        vector_dim: int = 384,
    ):
        self.host = host
        self.model = model
        self.vector_dim = vector_dim
        self._client: Optional[httpx.AsyncClient] = None
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text via Ollama."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=60.0)
        
        try:
            response = await self._client.post(
                f"{self.host}/api/embed",
                json={"model": self.model, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            emb = data["embeddings"][0] if data.get("embeddings") else []
            if emb:
                self.vector_dim = len(emb)
            return emb
        except httpx.RequestError as e:
            logger.error(f"[OllamaEmbedder] Request failed: {e}")
            raise
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            try:
                emb = await self.embed(text)
                embeddings.append(emb)
            except Exception as e:
                logger.warning(f"[OllamaEmbedder] Failed to embed text: {e}")
                embeddings.append([0.0] * self.vector_dim)
        return embeddings
    
    async def health_check(self) -> bool:
        """Verify Ollama is available."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=5.0)
        
        try:
            response = await self._client.get(f"{self.host}/api/tags")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


class QdrantVectorStore:
    """Local Qdrant vector store for semantic search."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "alert_decisions",
        vector_dim: int = 384,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        self._client = QdrantClient(host=host, port=port)
        self._ensure_collection()
    
    def _ensure_collection(self) -> None:
        """Create collection if not exists."""
        try:
            coll = self._client.get_collection(self.collection_name)
            # If collection exists, try to extract vector size
            if coll:
                # Try to access vector config; structure varies by Qdrant version
                try:
                    config = getattr(coll, 'config', None) or getattr(coll, 'vectors_config', None)
                    if config:
                        size = getattr(config, 'size', None)
                        if size and int(size) != self.vector_dim:
                            logger.warning(f"[Qdrant] Collection {self.collection_name} exists with dim {size}, expected {self.vector_dim}")
                except Exception as e:
                    logger.debug(f"[Qdrant] Could not check vector size: {e}")
        except Exception:
            logger.info(f"[Qdrant] Creating collection {self.collection_name}")
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_dim,
                    distance=Distance.COSINE,
                ),
            )
    
    def store_embedding(
        self,
        decision_id: str,
        vector: list[float],
        metadata: dict[str, Any],
    ) -> None:
        """Store embedding with metadata."""
        vlen = len(vector)
        if vlen != self.vector_dim:
            logger.warning(
                f"[Qdrant] Vector dim mismatch: collection dim={self.vector_dim}, vector dim={vlen}"
            )
            raise ValueError(f"Vector dimension mismatch: expected {self.vector_dim}, got {vlen}")

        point = PointStruct(
            id=hash(decision_id) % (2**31),
            vector=vector,
                payload={
                    "decision_id": decision_id,
                    "summary": metadata.get("summary", ""),
                    "service": metadata.get("service", ""),
                    "severity": metadata.get("severity", ""),
                    "created_at": metadata.get("created_at", ""),
                    "metadata": metadata,
                },
            )

        try:
            self._client.upsert(collection_name=self.collection_name, points=[point])
        except Exception as e:
            logger.exception(f"[Qdrant] upsert failed: {e}")
            raise

    def search_similar(
        self,
        vector: list[float],
        limit: int = 5,
        score_threshold: float = 0.75,
    ) -> list[dict]:
        """Search for similar embeddings."""
        # Use an Any-typed alias to avoid static-analysis errors about QdrantClient
        client_any: Any = self._client  # type: ignore[assignment]
        search_fn = getattr(client_any, "search", None)
        results: list[Any] = []
        if callable(search_fn):
            raw = search_fn(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
            )
            # Cast to list to satisfy static type checkers
            try:
                results = list(raw)  # type: ignore[assignment]
            except TypeError:
                results = []
        else:
            # Fallback to REST API search if client doesn't expose 'search'
            try:
                url = f"http://{self.host}:{self.port}/collections/{self.collection_name}/points/search"
                payload = {"vector": vector, "limit": limit, "with_payload": True}
                with httpx.Client(timeout=10.0) as c:
                    resp = c.post(url, json=payload)
                    resp.raise_for_status()
                    body = resp.json()
                    raw = body.get("result") or body.get("data") or body.get("points") or []
                    # Qdrant REST may return items under 'result' as dicts with 'id','payload','score'
                    parsed = []
                    for item in raw:
                        if isinstance(item, dict):
                            parsed.append(item)
                        else:
                            # if structure unexpected, append as-is
                            parsed.append(item)
                    results = parsed
            except Exception as e:
                logger.warning(f"[Qdrant] REST fallback search failed: {e}")
                results = []
        
        filtered = []
        for r in results:
            # r may be different shapes depending on client or REST API
            score = 0.0
            payload = {}
            if isinstance(r, dict):
                # Try common fields
                payload = r.get('payload') or r.get('point') or r.get('data') or r.get('payloads') or r.get('payload', {})
                score = r.get('score') or r.get('dist') or r.get('distance') or 0.0
                # sometimes payload is under 'point' key
                if not payload and 'point' in r and isinstance(r['point'], dict):
                    payload = r['point'].get('payload', {})
            else:
                payload = {}

            try:
                score = float(score or 0.0)
            except Exception:
                score = 0.0

            if score >= score_threshold:
                filtered.append({
                    "decision_id": payload.get("decision_id", ""),
                    "similarity_score": score,
                    "summary": payload.get("summary", ""),
                    "service": payload.get("service", ""),
                    "severity": payload.get("severity", ""),
                })
        return filtered
    
    def health_check(self) -> bool:
        """Verify Qdrant is available."""
        try:
            self._client.get_collection(self.collection_name)
            return True
        except Exception:
            return False


class GitHubMCPRepository:
    """GitHub context via MCP tools with token authentication."""
    
    def __init__(self, token: Optional[str] = None, owner: str = "org"):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.owner = owner
        self._session: Optional[httpx.AsyncClient] = None
    
    async def _get_session(self) -> httpx.AsyncClient:
        """Lazy-load async HTTP session with auth."""
        if not self._session:
            self._session = httpx.AsyncClient(
                headers={"Authorization": f"token {self.token}"}
                if self.token
                else {},
                timeout=30.0,
            )
        else:
            await self._session.aclose()
            self._session = httpx.AsyncClient(
                headers={"Authorization": f"token {self.token}"}
                if self.token
                else {},
                timeout=30.0,
            )
        return self._session
    
    async def get_repository_info(self, service: str) -> dict:
        """Get repo metadata: name, team, last_commit, on_call."""
        repo_name = f"{self.owner}/{service}"
        
        try:
            session = await self._get_session()
            response = await session.get(
                f"https://api.github.com/repos/{repo_name}",
            )
            if response.status_code == 404:
                return self._fallback_repo_info(service)
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "service": service,
                "repository": repo_name,
                "url": data.get("html_url", ""),
                "description": data.get("description", ""),
                "team": data.get("team", {}).get("name", "platform"),
                "last_commit": data.get("pushed_at", ""),
                "default_branch": data.get("default_branch", "main"),
                "topics": data.get("topics", []),
            }
        except Exception as e:
            logger.warning(f"[GitHubMCP] Failed to fetch {repo_name}: {e}")
            return self._fallback_repo_info(service)
    
    async def get_code_context(
        self,
        service: str,
        file_path: str,
    ) -> dict:
        """Get code snippet from repo file (if token has read:repo scope)."""
        repo_name = f"{self.owner}/{service}"
        
        try:
            session = await self._get_session()
            response = await session.get(
                f"https://api.github.com/repos/{repo_name}/contents/{file_path}",
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "file": file_path,
                "content": data.get("content", ""),
                "size": data.get("size", 0),
                "sha": data.get("sha", ""),
            }
        except Exception as e:
            logger.warning(f"[GitHubMCP] Failed to fetch code {file_path}: {e}")
            return {}
    
    async def get_team_ownership(self, service: str) -> dict:
        """Get team responsible for service (query GitHub Teams API)."""
        try:
            session = await self._get_session()
            response = await session.get(
                f"https://api.github.com/orgs/{self.owner}/teams",
            )
            response.raise_for_status()
            teams = response.json()
            
            for team in teams:
                if service in team.get("description", "").lower():
                    return {
                        "team": team.get("name", ""),
                        "slug": team.get("slug", ""),
                        "members_count": team.get("members_count", 0),
                    }
            
            return {"team": "platform", "slug": "platform", "members_count": 0}
        except Exception as e:
            logger.warning(f"[GitHubMCP] Failed to fetch team ownership: {e}")
            return {"team": "platform", "slug": "platform", "members_count": 0}
    
    def _fallback_repo_info(self, service: str) -> dict:
        """Fallback when repo not found or network error."""
        return {
            "service": service,
            "repository": f"{self.owner}/{service}",
            "url": "",
            "description": "",
            "team": "platform",
            "last_commit": "",
            "default_branch": "main",
            "topics": [],
        }
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.aclose()


class RefragRepository:
    """Unified repository for semantic context retrieval."""
    
    def __init__(
        self,
        embedder: Optional[OllamaEmbedder] = None,
        vector_store: Optional[QdrantVectorStore] = None,
        github_repo: Optional[GitHubMCPRepository] = None,
    ):
        self.embedder = embedder or OllamaEmbedder()
        self.vector_store = vector_store or QdrantVectorStore()
        self.github_repo = github_repo or GitHubMCPRepository()
    
    async def get_semantic_context(
        self,
        cluster: AlertCluster,
        top_k: int = 5,
        score_threshold: float = 0.75,
    ) -> dict:
        """
        Get semantic context: embeddings + vector search + repo metadata.
        
        Returns:
            {
                "semantic_evidence": [SimilarityResult],
                "repository_context": {repo metadata},
                "context_quality": float,
            }
        """
        query_text = self._build_query(cluster)
        
        try:
            query_vector = await self.embedder.embed(query_text)
        except Exception as e:
            logger.error(f"[RefragRepository] Embedding failed: {e}")
            return {
                "semantic_evidence": [],
                "repository_context": {},
                "context_quality": 0.0,
            }
        
        similar = self.vector_store.search_similar(
            query_vector,
            limit=top_k,
            score_threshold=score_threshold,
        )
        
        repo_metadata = await self.github_repo.get_repository_info(
            cluster.primary_service
        )
        
        quality = self._calculate_quality(similar)
        
        return {
            "semantic_evidence": similar,
            "repository_context": repo_metadata,
            "context_quality": quality,
        }
    
    def _build_query(self, cluster: AlertCluster) -> str:
        """Build search query from cluster."""
        descriptions = [a.description for a in cluster.alerts[:5]]
        combined = " | ".join(descriptions)
        return (
            f"Service: {cluster.primary_service} | "
            f"Severity: {cluster.primary_severity} | {combined}"
        )
    
    def _calculate_quality(self, results: list[dict]) -> float:
        """Calculate context quality score."""
        if not results:
            return 0.0
        
        avg_score = sum(r["similarity_score"] for r in results) / len(results)
        high_conf = sum(1 for r in results if r["similarity_score"] >= 0.9)
        confidence_bonus = min(0.2, high_conf * 0.05)
        count_factor = min(1.0, len(results) / 3)
        
        return min(1.0, (avg_score * 0.6) + (count_factor * 0.2) + confidence_bonus)
    
    async def store_decision(
        self,
        decision_id: str,
        summary: str,
        service: str,
        severity: str,
    ) -> None:
        """Store confirmed decision in vector store."""
        text = f"Service: {service} | Severity: {severity} | Summary: {summary}"
        
        try:
            vector = await self.embedder.embed(text)
            self.vector_store.store_embedding(
                decision_id,
                vector,
                {
                    "summary": summary,
                    "service": service,
                    "severity": severity,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"[RefragRepository] Failed to store decision: {e}")
    
    async def health_check(self) -> dict:
        """Check all integrations."""
        return {
            "ollama": await self.embedder.health_check(),
            "qdrant": self.vector_store.health_check(),
            "github": bool(self.github_repo.token),
        }
    
    async def close(self) -> None:
        """Close all connections."""
        await self.embedder.close()
        try:
            await self.github_repo.close()
        except Exception as e:
            logger.warning(f"[RefragRepository] Error closing GitHub repo: {e}")


# Factory for dependency injection
def create_refrag_repository(
    ollama_host: Optional[str] = None,
    ollama_model: Optional[str] = None,
    qdrant_host: Optional[str] = None,
    github_token: Optional[str] = None,
) -> RefragRepository:
    """Create repository with optional overrides."""
    embedder = OllamaEmbedder(
        host=ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model=ollama_model or os.getenv("OLLAMA_MODEL", "nomic-embed-text:latest"),
    )
    vector_store = QdrantVectorStore(
        host=qdrant_host or os.getenv("QDRANT_HOST", "localhost"),
        vector_dim=embedder.vector_dim,
    )
    github_repo = GitHubMCPRepository(
        token=github_token or os.getenv("GITHUB_TOKEN"),
    )
    
    return RefragRepository(embedder, vector_store, github_repo)
