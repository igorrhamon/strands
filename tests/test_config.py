"""
Test suite for configuration management.

Verifies that config loading, validation, and environment-based settings work correctly.
"""

import os
import pytest
from pydantic import ValidationError

from swarm_intelligence.config import Config, get_config, reload_config


class TestConfiguration:
    """Test the configuration system."""
    
    def test_config_loads_defaults(self):
        """Test that config loads with default values when no env vars are set."""
        # Clear relevant env vars
        for key in list(os.environ.keys()):
            if key.startswith(('NEO4J_', 'QDRANT_', 'API_', 'SWARM_', 'GRAFANA_', 'PROMETHEUS_')):
                del os.environ[key]
        
        # Set only required values
        os.environ['NEO4J_PASSWORD'] = 'test_password'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'test_grafana_pass'
        
        config = Config()
        
        assert config.environment == "development"
        assert config.debug == False
        assert config.neo4j.uri == "bolt://localhost:7687"
        assert config.neo4j.username == "neo4j"
        assert config.neo4j.password == "test_password"
        assert config.api.port == 8000
        assert config.swarm.max_retry_rounds == 10
    
    def test_config_loads_from_env_vars(self):
        """Test that config loads from environment variables."""
        os.environ['ENVIRONMENT'] = 'staging'
        os.environ['NEO4J_URI'] = 'bolt://neo4j.example.com:7687'
        os.environ['NEO4J_USERNAME'] = 'custom_user'
        os.environ['NEO4J_PASSWORD'] = 'secure_password_123'
        os.environ['API_PORT'] = '9000'
        os.environ['SWARM_MAX_RETRY_ROUNDS'] = '20'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'grafana_secure'
        
        config = Config()
        
        assert config.environment == "staging"
        assert config.neo4j.uri == "bolt://neo4j.example.com:7687"
        assert config.neo4j.username == "custom_user"
        assert config.neo4j.password == "secure_password_123"
        assert config.api.port == 9000
        assert config.swarm.max_retry_rounds == 20
    
    def test_config_validates_environment(self):
        """Test that invalid environment values are rejected."""
        os.environ['ENVIRONMENT'] = 'invalid_env'
        os.environ['NEO4J_PASSWORD'] = 'test_password'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'test_grafana'
        
        with pytest.raises(ValidationError) as exc_info:
            Config()
        
        assert 'environment' in str(exc_info.value).lower()
    
    def test_config_validates_log_level(self):
        """Test that invalid log levels are rejected."""
        os.environ['API_LOG_LEVEL'] = 'INVALID_LEVEL'
        os.environ['NEO4J_PASSWORD'] = 'test_password'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'test_grafana'
        
        with pytest.raises(ValidationError) as exc_info:
            Config()
        
        assert 'log_level' in str(exc_info.value).lower()
    
    def test_config_requires_neo4j_password(self):
        """Test that Neo4j password is required."""
        # Clear password env var
        if 'NEO4J_PASSWORD' in os.environ:
            del os.environ['NEO4J_PASSWORD']
        
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'test_grafana'
        
        with pytest.raises(ValidationError) as exc_info:
            Config()
        
        assert 'neo4j_password' in str(exc_info.value).lower() or 'required' in str(exc_info.value).lower()
    
    def test_production_validation(self):
        """Test that production environment has stricter validation."""
        os.environ['ENVIRONMENT'] = 'production'
        os.environ['DEBUG'] = 'true'
        os.environ['NEO4J_PASSWORD'] = 'password'  # Default password
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'admin'  # Default password
        
        config = Config()
        
        with pytest.raises(ValueError) as exc_info:
            config.validate_required()
        
        assert 'debug' in str(exc_info.value).lower() or 'password' in str(exc_info.value).lower()
    
    def test_production_with_secure_config(self):
        """Test that production with secure config passes validation."""
        os.environ['ENVIRONMENT'] = 'production'
        os.environ['DEBUG'] = 'false'
        os.environ['NEO4J_PASSWORD'] = 'secure_production_password_xyz123'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'secure_grafana_password_abc456'
        
        config = Config()
        config.validate_required()  # Should not raise
        
        assert config.environment == 'production'
        assert config.debug == False
    
    def test_nested_config_access(self):
        """Test accessing nested configuration objects."""
        os.environ['NEO4J_PASSWORD'] = 'test_password'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'test_grafana'
        os.environ['QDRANT_HOST'] = 'qdrant.example.com'
        os.environ['QDRANT_PORT'] = '7333'
        
        config = Config()
        
        assert config.qdrant.host == 'qdrant.example.com'
        assert config.qdrant.port == 7333
        assert config.neo4j.database == 'neo4j'  # Default value


class TestGlobalConfigInstance:
    """Test the global config instance management."""
    
    def test_get_config_returns_same_instance(self):
        """Test that get_config() returns the same instance."""
        os.environ['NEO4J_PASSWORD'] = 'test_password'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'test_grafana'
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
    
    def test_reload_config_creates_new_instance(self):
        """Test that reload_config() creates a new instance."""
        os.environ['NEO4J_PASSWORD'] = 'test_password'
        os.environ['GRAFANA_ADMIN_PASSWORD'] = 'test_grafana'
        
        config1 = get_config()
        
        # Change env var
        os.environ['API_PORT'] = '9999'
        
        config2 = reload_config()
        
        assert config1 is not config2
        assert config2.api.port == 9999


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
