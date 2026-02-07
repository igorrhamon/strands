"""
Testes - LLM Provider Factory

Testa factory e providers de LLM.
"""

import pytest
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.llm.provider_factory import (
    LLMProviderFactory,
    LLMProviderType,
    LLMConfig,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
)


class TestLLMConfig:
    """Testes para LLMConfig."""
    
    def test_create_config_openai(self):
        """Testa criação de config para OpenAI."""
        config = LLMConfig(
            provider=LLMProviderType.OPENAI,
            api_key="sk-test",
            model="gpt-4"
        )
        
        assert config.provider == LLMProviderType.OPENAI
        assert config.api_key == "sk-test"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000
    
    def test_create_config_anthropic(self):
        """Testa criação de config para Anthropic."""
        config = LLMConfig(
            provider=LLMProviderType.ANTHROPIC,
            api_key="sk-ant-test",
            model="claude-3-opus"
        )
        
        assert config.provider == LLMProviderType.ANTHROPIC
        assert config.model == "claude-3-opus"
    
    def test_create_config_ollama(self):
        """Testa criação de config para Ollama."""
        config = LLMConfig(
            provider=LLMProviderType.OLLAMA,
            model="llama2",
            base_url="http://localhost:11434"
        )
        
        assert config.provider == LLMProviderType.OLLAMA
        assert config.model == "llama2"
        assert config.base_url == "http://localhost:11434"
    
    def test_config_temperature_validation(self):
        """Testa validação de temperatura."""
        # Temperatura válida
        config = LLMConfig(
            provider=LLMProviderType.OPENAI,
            api_key="sk-test",
            model="gpt-4",
            temperature=1.5
        )
        assert config.temperature == 1.5
        
        # Temperatura inválida (muito alta)
        with pytest.raises(ValueError):
            LLMConfig(
                provider=LLMProviderType.OPENAI,
                api_key="sk-test",
                model="gpt-4",
                temperature=3.0
            )
    
    def test_config_frozen(self):
        """Testa se config é imutável."""
        config = LLMConfig(
            provider=LLMProviderType.OPENAI,
            api_key="sk-test",
            model="gpt-4"
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            config.model = "gpt-3.5"


class TestLLMProviderFactory:
    """Testes para LLMProviderFactory."""
    
    def test_list_providers(self):
        """Testa listagem de providers."""
        providers = LLMProviderFactory.list_providers()
        
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers
    
    def test_create_openai_provider(self):
        """Testa criação de provider OpenAI."""
        config = LLMConfig(
            provider=LLMProviderType.OPENAI,
            api_key="sk-test",
            model="gpt-4"
        )
        
        with patch("openai.AsyncOpenAI"):
            provider = LLMProviderFactory.create(config)
            assert isinstance(provider, OpenAIProvider)
            assert provider.config == config
    
    def test_create_anthropic_provider(self):
        """Testa criação de provider Anthropic."""
        config = LLMConfig(
            provider=LLMProviderType.ANTHROPIC,
            api_key="sk-ant-test",
            model="claude-3-opus"
        )
        
        with patch("anthropic.AsyncAnthropic"):
            provider = LLMProviderFactory.create(config)
            assert isinstance(provider, AnthropicProvider)
            assert provider.config == config
    
    def test_create_ollama_provider(self):
        """Testa criação de provider Ollama."""
        config = LLMConfig(
            provider=LLMProviderType.OLLAMA,
            model="llama2",
            base_url="http://localhost:11434"
        )
        
        with patch("ollama.AsyncClient"):
            provider = LLMProviderFactory.create(config)
            assert isinstance(provider, OllamaProvider)
            assert provider.config == config
    
    def test_create_invalid_provider(self):
        """Testa criação de provider inválido."""
        config = LLMConfig(
            provider=LLMProviderType.OPENAI,
            api_key="sk-test",
            model="gpt-4"
        )
        
        # Simular provider inválido
        with patch.dict(LLMProviderFactory.PROVIDERS, {}, clear=True):
            with pytest.raises(ValueError):
                LLMProviderFactory.create(config)
    
    @patch.dict(os.environ, {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-test",
        "LLM_MODEL": "gpt-4",
        "LLM_TEMPERATURE": "0.8",
        "LLM_MAX_TOKENS": "4000"
    })
    def test_create_from_env_openai(self):
        """Testa criação a partir de variáveis de ambiente (OpenAI)."""
        with patch("openai.AsyncOpenAI"):
            provider = LLMProviderFactory.create_from_env()
            
            assert isinstance(provider, OpenAIProvider)
            assert provider.config.provider == LLMProviderType.OPENAI
            assert provider.config.model == "gpt-4"
            assert provider.config.temperature == 0.8
            assert provider.config.max_tokens == 4000
    
    @patch.dict(os.environ, {
        "LLM_PROVIDER": "anthropic",
        "LLM_API_KEY": "sk-ant-test",
        "LLM_MODEL": "claude-3-opus"
    })
    def test_create_from_env_anthropic(self):
        """Testa criação a partir de variáveis de ambiente (Anthropic)."""
        with patch("anthropic.AsyncAnthropic"):
            provider = LLMProviderFactory.create_from_env()
            
            assert isinstance(provider, AnthropicProvider)
            assert provider.config.provider == LLMProviderType.ANTHROPIC
            assert provider.config.model == "claude-3-opus"
    
    @patch.dict(os.environ, {
        "LLM_PROVIDER": "ollama",
        "LLM_MODEL": "llama2",
        "LLM_BASE_URL": "http://localhost:11434"
    })
    def test_create_from_env_ollama(self):
        """Testa criação a partir de variáveis de ambiente (Ollama)."""
        with patch("ollama.AsyncClient"):
            provider = LLMProviderFactory.create_from_env()
            
            assert isinstance(provider, OllamaProvider)
            assert provider.config.provider == LLMProviderType.OLLAMA
            assert provider.config.model == "llama2"
            assert provider.base_url == "http://localhost:11434"
    
    @patch.dict(os.environ, {"LLM_PROVIDER": "invalid"})
    def test_create_from_env_invalid_provider(self):
        """Testa erro com provider inválido."""
        with pytest.raises(ValueError, match="Provider inválido"):
            LLMProviderFactory.create_from_env()
    
    @patch.dict(os.environ, {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-test"
    }, clear=True)
    def test_create_from_env_missing_model(self):
        """Testa erro com modelo não definido."""
        with pytest.raises(ValueError, match="LLM_MODEL não definido"):
            LLMProviderFactory.create_from_env()
    
    @patch.dict(os.environ, {
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "gpt-4"
    }, clear=True)
    def test_create_from_env_missing_api_key(self):
        """Testa erro com API key não definida."""
        with pytest.raises(ValueError, match="LLM_API_KEY necessário"):
            LLMProviderFactory.create_from_env()


class TestOpenAIProvider:
    """Testes para OpenAI Provider."""
    
    @pytest.fixture
    def config(self):
        """Cria config."""
        return LLMConfig(
            provider=LLMProviderType.OPENAI,
            api_key="sk-test",
            model="gpt-4"
        )
    
    @pytest.fixture
    def provider(self, config):
        """Cria provider."""
        with patch("openai.AsyncOpenAI"):
            return OpenAIProvider(config)
    
    @pytest.mark.asyncio
    async def test_generate(self, provider):
        """Testa geração de resposta."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Resposta teste"))]
        
        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await provider.generate("Teste prompt")
        
        assert result == "Resposta teste"
        provider.client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_with_context(self, provider):
        """Testa geração com contexto."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Resposta com contexto"))]
        
        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await provider.generate_with_context("Pergunta", "Contexto")
        
        assert result == "Resposta com contexto"
        call_args = provider.client.chat.completions.create.call_args
        assert "Contexto" in call_args[1]["messages"][0]["content"]
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Testa health check bem-sucedido."""
        provider.client.models.list = AsyncMock()
        
        result = await provider.health_check()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        """Testa health check com falha."""
        provider.client.models.list = AsyncMock(side_effect=Exception("Erro"))
        
        result = await provider.health_check()
        
        assert result is False


class TestAnthropicProvider:
    """Testes para Anthropic Provider."""
    
    @pytest.fixture
    def config(self):
        """Cria config."""
        return LLMConfig(
            provider=LLMProviderType.ANTHROPIC,
            api_key="sk-ant-test",
            model="claude-3-opus"
        )
    
    @pytest.fixture
    def provider(self, config):
        """Cria provider."""
        with patch("anthropic.AsyncAnthropic"):
            return AnthropicProvider(config)
    
    @pytest.mark.asyncio
    async def test_generate(self, provider):
        """Testa geração de resposta."""
        mock_response = Mock()
        mock_response.content = [Mock(text="Resposta Anthropic")]
        
        provider.client.messages.create = AsyncMock(return_value=mock_response)
        
        result = await provider.generate("Teste prompt")
        
        assert result == "Resposta Anthropic"
        provider.client.messages.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_with_context(self, provider):
        """Testa geração com contexto."""
        mock_response = Mock()
        mock_response.content = [Mock(text="Resposta com contexto")]
        
        provider.client.messages.create = AsyncMock(return_value=mock_response)
        
        result = await provider.generate_with_context("Pergunta", "Contexto")
        
        assert result == "Resposta com contexto"


class TestOllamaProvider:
    """Testes para Ollama Provider."""
    
    @pytest.fixture
    def config(self):
        """Cria config."""
        return LLMConfig(
            provider=LLMProviderType.OLLAMA,
            model="llama2",
            base_url="http://localhost:11434"
        )
    
    @pytest.fixture
    def provider(self, config):
        """Cria provider."""
        with patch("ollama.AsyncClient"):
            return OllamaProvider(config)
    
    @pytest.mark.asyncio
    async def test_generate(self, provider):
        """Testa geração de resposta."""
        mock_response = {"response": "Resposta Ollama"}
        
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=mock_response)
        
        with patch.object(provider.ollama, "AsyncClient", return_value=mock_client):
            result = await provider.generate("Teste prompt")
            
            assert result == "Resposta Ollama"
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Testa health check bem-sucedido."""
        mock_response = Mock(status_code=200)
        
        with patch("httpx.AsyncClient") as mock_http:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_http.return_value = mock_client
            
            result = await provider.health_check()
            
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
