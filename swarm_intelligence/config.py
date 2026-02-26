"""
Centralized Configuration Management for Strands

Uses Pydantic Settings for type-safe environment variable loading.
All sensitive values must be provided via environment variables.
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jConfig(BaseSettings):
    """Neo4j database configuration."""
    
    uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI"
    )
    username: str = Field(
        default="neo4j",
        description="Neo4j username"
    )
    password: str = Field(
        ...,
        description="Neo4j password (required)"
    )
    database: str = Field(
        default="neo4j",
        description="Neo4j database name"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="NEO4J_",
        case_sensitive=False
    )


class QdrantConfig(BaseSettings):
    """Qdrant vector database configuration."""
    
    host: str = Field(
        default="localhost",
        description="Qdrant host"
    )
    port: int = Field(
        default=6333,
        description="Qdrant port"
    )
    grpc_port: int = Field(
        default=6334,
        description="Qdrant gRPC port"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Qdrant API key (optional for local)"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        case_sensitive=False
    )


class PrometheusConfig(BaseSettings):
    """Prometheus monitoring configuration."""
    
    url: str = Field(
        default="http://localhost:9090",
        description="Prometheus server URL"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="PROMETHEUS_",
        case_sensitive=False
    )


class GrafanaConfig(BaseSettings):
    """Grafana dashboard configuration."""
    
    url: str = Field(
        default="http://localhost:3000",
        description="Grafana server URL"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Grafana API key (optional)"
    )
    admin_password: str = Field(
        default="admin",
        description="Grafana admin password"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="GRAFANA_",
        case_sensitive=False
    )


class APIConfig(BaseSettings):
    """FastAPI server configuration."""
    
    host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    port: int = Field(
        default=8000,
        description="API server port"
    )
    reload: bool = Field(
        default=False,
        description="Enable auto-reload (development only)"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    enable_cors: bool = Field(
        default=True,
        description="Enable CORS"
    )
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper
    
    model_config = SettingsConfigDict(
        env_prefix="API_",
        case_sensitive=False
    )


class SwarmConfig(BaseSettings):
    """Swarm intelligence configuration."""
    
    max_retry_rounds: int = Field(
        default=10,
        description="Maximum retry rounds per swarm run"
    )
    max_runtime_seconds: float = Field(
        default=300.0,
        description="Maximum runtime in seconds"
    )
    max_total_attempts: int = Field(
        default=50,
        description="Maximum total execution attempts"
    )
    use_llm_fallback: bool = Field(
        default=True,
        description="Enable LLM fallback for failed mandatory steps"
    )
    llm_fallback_threshold: float = Field(
        default=0.5,
        description="Confidence threshold for LLM fallback"
    )
    llm_agent_id: str = Field(
        default="llm_agent",
        description="LLM agent identifier"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="SWARM_",
        case_sensitive=False
    )


class Config(BaseSettings):
    """Main application configuration."""
    
    # Environment
    environment: str = Field(
        default="development",
        description="Application environment: development, staging, production"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    # Sub-configurations
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    grafana: GrafanaConfig = Field(default_factory=GrafanaConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return v.lower()
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def validate_required(self) -> None:
        """Validate that all required configuration is present for production."""
        if self.environment == "production":
            #if self.debug:
            #    raise ValueError("debug must be False in production")
            if self.neo4j.password == "password":
                raise ValueError("NEO4J_PASSWORD must be changed from default in production")
            if self.grafana.admin_password == "admin":
                raise ValueError("GRAFANA_ADMIN_PASSWORD must be changed from default in production")


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
        _config.validate_required()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment (useful for testing)."""
    global _config
    _config = Config()
    _config.validate_required()
    return _config
