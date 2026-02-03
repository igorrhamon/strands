"""Configuration loader and environment variable management"""
import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class MCPConfig(BaseModel):
    """MCP endpoint configurations"""
    grafana_url: str = Field(default_factory=lambda: os.getenv("GRAFANA_MCP_URL", ""))
    github_url: str = Field(default_factory=lambda: os.getenv("GITHUB_MCP_URL", ""))
    kubectl_url: str = Field(default_factory=lambda: os.getenv("KUBECTL_MCP_URL", ""))
    mysql_url: str = Field(default_factory=lambda: os.getenv("MYSQL_MCP_URL", ""))
    timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("MCP_TIMEOUT", "30")))


class PrometheusConfig(BaseModel):
    """Prometheus configuration"""
    url: str = Field(default_factory=lambda: os.getenv("PROMETHEUS_URL", ""))
    timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("PROM_TIMEOUT", "10")))
    max_retries: int = Field(default=3)
    retry_delays: list[int] = Field(default=[1, 2, 4])


class Neo4jConfig(BaseModel):
    """Neo4j graph database configuration"""
    uri: str = Field(default_factory=lambda: os.getenv("NEO4J_URI", ""))
    user: str = Field(default_factory=lambda: os.getenv("NEO4J_USER", ""))
    password: str = Field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))


class ChromaConfig(BaseModel):
    """ChromaDB vector store configuration"""
    host: str = Field(default_factory=lambda: os.getenv("CHROMA_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("CHROMA_PORT", "8000")))


class GovernanceConfig(BaseModel):
    """Governance and decision policies"""
    confidence_threshold: float = Field(
        default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
    )
    human_review_required: bool = Field(
        default_factory=lambda: os.getenv("HUMAN_REVIEW_REQUIRED", "true").lower() == "true"
    )
    audit_log_path: str = Field(default_factory=lambda: os.getenv("AUDIT_LOG_PATH", "./audit_logs"))


class Config(BaseModel):
    """Master configuration"""
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    chroma: ChromaConfig = Field(default_factory=ChromaConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Global config instance
config = Config()
