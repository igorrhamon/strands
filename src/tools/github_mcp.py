"""
GitHub MCP Client - Repository Metadata Lookup

Interfaces with GitHub via MCP tools to retrieve repository metadata.
Used to enrich alert context with team, ownership, and README information.
"""

import base64
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"


class GitHubClientError(Exception):
    """Raised when GitHub operations fail."""
    pass


class GitHubMCPClient:
    """
    Client for fetching repository metadata via GitHub REST API.
    
    Authentication uses a personal access token supplied via the
    ``GITHUB_TOKEN`` environment variable or the *api_token* constructor
    parameter.
    """
    
    def __init__(
        self,
        owner: Optional[str] = None,
        default_org: str = "organization",
        api_token: Optional[str] = None,
    ):
        """
        Initialize GitHub MCP client.
        
        Args:
            owner: Default repository owner/organization.
            default_org: Fallback organization name.
            api_token: GitHub PAT (falls back to GITHUB_TOKEN env var).
        """
        self._owner = owner or default_org
        self._mcp_available = False
        self._token = api_token or os.environ.get("GITHUB_TOKEN", "")
        self._headers: dict = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"
    
    def check_connection(self) -> bool:
        """
        Verify MCP connection is available.
        
        Returns:
            True if MCP tools are accessible.
        """
        self._mcp_available = True
        return self._mcp_available
    
    async def get_repository_info(
        self,
        service_name: str,
    ) -> dict:
        """
        Get repository information for a service via GitHub REST API.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            logger.info(f"Looking up repository for service: {service_name}")
            async with httpx.AsyncClient(headers=self._headers, timeout=5.0) as client:
                response = await client.get(
                    f"{_GITHUB_API}/repos/{self._owner}/{service_name}"
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "name": data.get("name", service_name),
                    "full_name": data.get("full_name", f"{self._owner}/{service_name}"),
                    "owner": data.get("owner", {}).get("login", self._owner),
                    "default_branch": data.get("default_branch", "main"),
                    "language": data.get("language"),
                    "topics": data.get("topics", []),
                    "open_issues": data.get("open_issues_count", 0),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Repository {self._owner}/{service_name} not found")
                return {
                    "name": service_name,
                    "full_name": f"{self._owner}/{service_name}",
                    "owner": self._owner,
                    "default_branch": "main",
                    "language": None,
                    "topics": [],
                    "open_issues": 0,
                    "created_at": None,
                    "updated_at": None,
                }
            raise GitHubClientError(f"GitHub API error {e.response.status_code}: {e}") from e
        except Exception as e:
            raise GitHubClientError(f"Failed to get repository info: {e}") from e
    
    async def get_team_info(
        self,
        service_name: str,
    ) -> dict:
        """
        Get team ownership for a service by reading the CODEOWNERS file,
        falling back to the first team with access to the repository.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=5.0) as client:
                # Try CODEOWNERS first
                for path in (".github/CODEOWNERS", "CODEOWNERS"):
                    r = await client.get(
                        f"{_GITHUB_API}/repos/{self._owner}/{service_name}/contents/{path}"
                    )
                    if r.status_code == 200:
                        raw = base64.b64decode(r.json()["content"]).decode()
                        # Extract first @org/team reference
                        for line in raw.splitlines():
                            line = line.strip()
                            if line and not line.startswith("#"):
                                parts = line.split()
                                if len(parts) >= 2:
                                    owner_ref = parts[1].lstrip("@")
                                    team_slug = owner_ref.split("/")[-1]
                                    return {
                                        "team_name": team_slug,
                                        "team_slug": team_slug,
                                        "maintainers": parts[1:],
                                        "on_call_integration": None,
                                    }
                # Fallback: list teams with push access
                r2 = await client.get(
                    f"{_GITHUB_API}/repos/{self._owner}/{service_name}/teams"
                )
                if r2.status_code == 200 and r2.json():
                    team = r2.json()[0]
                    return {
                        "team_name": team.get("name", ""),
                        "team_slug": team.get("slug", ""),
                        "maintainers": [],
                        "on_call_integration": None,
                    }
            # No owner information found
            return {
                "team_name": None,
                "team_slug": None,
                "maintainers": [],
                "on_call_integration": None,
            }
        except Exception as e:
            raise GitHubClientError(f"Failed to get team info: {e}") from e
    
    async def get_readme_context(
        self,
        service_name: str,
        max_length: int = 500,
    ) -> str:
        """
        Get README content for context via GitHub REST API.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=5.0) as client:
                response = await client.get(
                    f"{_GITHUB_API}/repos/{self._owner}/{service_name}/readme"
                )
                response.raise_for_status()
                data = response.json()
                content_b64 = data.get("content", "")
                readme = base64.b64decode(content_b64).decode("utf-8", errors="replace")
                if len(readme) > max_length:
                    return readme[:max_length] + "..."
                return readme
        except httpx.HTTPStatusError:
            logger.warning(f"README not found for {service_name}")
            return ""
        except Exception as e:
            logger.warning(f"Failed to get README: {e}")
            return ""
    
    async def get_recent_commits(
        self,
        service_name: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Get recent commits for a service repository via GitHub REST API.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=5.0) as client:
                response = await client.get(
                    f"{_GITHUB_API}/repos/{self._owner}/{service_name}/commits",
                    params={"per_page": min(limit, 100)},
                )
                response.raise_for_status()
                return [
                    {
                        "sha": c.get("sha", "")[:7],
                        "message": (
                            c.get("commit", {}).get("message", "").splitlines()[0]
                            if c.get("commit", {}).get("message")
                            else ""
                        ),
                        "author": (
                            c.get("commit", {}).get("author", {}).get("name", "")
                        ),
                        "date": (
                            c.get("commit", {}).get("author", {}).get("date", "")
                        ),
                        "url": c.get("html_url", ""),
                    }
                    for c in response.json()
                ]
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch commits ({e.response.status_code}): {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to get recent commits: {e}")
            return []


async def get_service_context(service_name: str) -> dict:
    """
    Convenience function to get full service context.
    
    Args:
        service_name: Name of the service.
    
    Returns:
        Combined context from repository and team info.
    """
    client = GitHubMCPClient()
    
    repo_info = await client.get_repository_info(service_name)
    team_info = await client.get_team_info(service_name)
    readme = await client.get_readme_context(service_name)
    
    return {
        "repository": repo_info,
        "team": team_info,
        "readme_summary": readme,
    }

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GitHubClientError(Exception):
    """Raised when GitHub operations fail."""
    pass


class GitHubMCPClient:
    """
    Client for fetching repository metadata via MCP.
    
    This client wraps MCP tool calls to abstract the underlying
    communication layer.
    """
    
    def __init__(
        self,
        owner: Optional[str] = None,
        default_org: str = "organization",
    ):
        """
        Initialize GitHub MCP client.
        
        Args:
            owner: Default repository owner/organization.
            default_org: Fallback organization name.
        """
        self._owner = owner or default_org
        self._mcp_available = False
    
    def check_connection(self) -> bool:
        """
        Verify MCP connection is available.
        
        Returns:
            True if MCP tools are accessible.
        """
        # In real implementation, this would call MCP health check
        self._mcp_available = True
        return self._mcp_available
    
    async def get_repository_info(
        self,
        service_name: str,
    ) -> dict:
        """
        Get repository information for a service.
        
        Args:
            service_name: Name of the service (used to find repo).
        
        Returns:
            Dict with repository metadata.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            # In real implementation, call MCP GitHub tools
            logger.info(f"Looking up repository for service: {service_name}")
            
            # Placeholder - real implementation would call:
            # mcp_github_repo(repo=f"{self._owner}/{service_name}", query="repository info")
            return {
                "name": service_name,
                "full_name": f"{self._owner}/{service_name}",
                "owner": self._owner,
                "default_branch": "main",
                "language": "Python",
                "topics": ["microservice", "api"],
                "open_issues": 5,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            }
        
        except Exception as e:
            raise GitHubClientError(f"Failed to get repository info: {e}") from e
    
    async def get_team_info(
        self,
        service_name: str,
    ) -> dict:
        """
        Get team ownership information for a service.
        
        Args:
            service_name: Name of the service.
        
        Returns:
            Dict with team information.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            # Placeholder - real implementation would parse CODEOWNERS
            # or use GitHub Teams API
            return {
                "team_name": "platform-team",
                "team_slug": "platform",
                "maintainers": [],
                "on_call_integration": None,
            }
        
        except Exception as e:
            raise GitHubClientError(f"Failed to get team info: {e}") from e
    
    async def get_readme_context(
        self,
        service_name: str,
        max_length: int = 500,
    ) -> str:
        """
        Get README content for context.
        
        Args:
            service_name: Name of the service.
            max_length: Maximum content length to return.
        
        Returns:
            Truncated README content.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            # Placeholder - real implementation would fetch README.md
            readme_content = f"# {service_name}\n\nMicroservice for handling requests."
            
            if len(readme_content) > max_length:
                return readme_content[:max_length] + "..."
            return readme_content
        
        except Exception as e:
            logger.warning(f"Failed to get README: {e}")
            return ""
    
    async def get_recent_commits(
        self,
        service_name: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Get recent commits for a service repository.
        
        Useful for correlating alerts with recent deployments.
        
        Args:
            service_name: Name of the service.
            limit: Maximum commits to return.
        
        Returns:
            List of recent commit summaries.
        """
        if not self._mcp_available:
            self.check_connection()
        
        try:
            # Placeholder - real implementation would use GitHub API
            return []
        
        except Exception as e:
            logger.warning(f"Failed to get recent commits: {e}")
            return []


async def get_service_context(service_name: str) -> dict:
    """
    Convenience function to get full service context.
    
    Args:
        service_name: Name of the service.
    
    Returns:
        Combined context from repository and team info.
    """
    client = GitHubMCPClient()
    
    repo_info = await client.get_repository_info(service_name)
    team_info = await client.get_team_info(service_name)
    readme = await client.get_readme_context(service_name)
    
    return {
        "repository": repo_info,
        "team": team_info,
        "readme_summary": readme,
    }
