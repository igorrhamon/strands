"""GitHub MCP client wrapper (read-only)"""
import httpx
from typing import List, Dict, Any, Optional
import logging

from src.config.settings import config
from src.models.audit import RepositoryAssociation


logger = logging.getLogger(__name__)


class GitHubMCPClient:
    """Wrapper for GitHub MCP operations (read-only)"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url or config.mcp.github_url
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def search_related_prs(
        self,
        repository: str,
        keywords: List[str],
        since_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Search for related pull requests
        
        Args:
            repository: Repository name (owner/repo)
            keywords: Search keywords
            since_days: Look back period in days
            
        Returns:
            List of PR metadata dicts
        """
        try:
            response = self.client.post(
                f"{self.base_url}/search/pulls",
                json={
                    "repository": repository,
                    "keywords": keywords,
                    "since_days": since_days
                }
            )
            response.raise_for_status()
            data = response.json()
            
            prs = data.get("pull_requests", [])
            logger.info(f"Found {len(prs)} related PRs in {repository}")
            return prs
            
        except httpx.HTTPError as e:
            logger.error(f"GitHub PR search failed: {e}")
            return []
    
    def search_related_issues(
        self,
        repository: str,
        keywords: List[str],
        since_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Search for related issues
        
        Args:
            repository: Repository name (owner/repo)
            keywords: Search keywords
            since_days: Look back period in days
            
        Returns:
            List of issue metadata dicts
        """
        try:
            response = self.client.post(
                f"{self.base_url}/search/issues",
                json={
                    "repository": repository,
                    "keywords": keywords,
                    "since_days": since_days
                }
            )
            response.raise_for_status()
            data = response.json()
            
            issues = data.get("issues", [])
            logger.info(f"Found {len(issues)} related issues in {repository}")
            return issues
            
        except httpx.HTTPError as e:
            logger.error(f"GitHub issue search failed: {e}")
            return []
    
    def get_recent_commits(
        self,
        repository: str,
        branch: str = "main",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent commits from a branch
        
        Args:
            repository: Repository name (owner/repo)
            branch: Branch name
            limit: Maximum number of commits
            
        Returns:
            List of commit metadata dicts
        """
        try:
            response = self.client.get(
                f"{self.base_url}/repos/{repository}/commits",
                params={"branch": branch, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            
            commits = data.get("commits", [])
            logger.info(f"Fetched {len(commits)} commits from {repository}/{branch}")
            return commits
            
        except httpx.HTTPError as e:
            logger.error(f"GitHub commit fetch failed: {e}")
            return []
    
    def close(self) -> None:
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
