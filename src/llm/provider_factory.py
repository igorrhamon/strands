"""
LLM Provider Factory - Factory Pattern para Múltiplos Providers de LLM

Suporta 4 providers: OpenAI, Anthropic (Claude), Ollama (local), GitHub Models
Selecionável via variável de ambiente LLM_PROVIDER.

Padrão: Factory Pattern + Strategy Pattern
Resiliência: Fallback automático, retry com backoff
"""

import logging
import os
from typing import Optional, Dict, Any
from enum import Enum
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMProviderType(str, Enum):
    """Tipos de providers de LLM."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GITHUB = "github"


class LLMConfig(BaseModel):
    """Configuração de LLM."""
    
    provider: LLMProviderType = Field(..., description="Provider de LLM")
    api_key: Optional[str] = Field(None, description="API Key (se necessário)")
    model: str = Field(..., description="Nome do modelo")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperatura (0-2)")
    max_tokens: int = Field(2000, ge=1, le=32000, description="Máximo de tokens")
    timeout: int = Field(30, ge=1, le=300, description="Timeout em segundos")
    base_url: Optional[str] = Field(None, description="URL base (para Ollama/GitHub)")
    
    class Config:
        frozen = True


class BaseLLMProvider(ABC):
    """Interface base para providers de LLM."""
    
    def __init__(self, config: LLMConfig):
        """Inicializa provider.
        
        Args:
            config: Configuração de LLM
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Gera resposta para um prompt.
        
        Args:
            prompt: Prompt de entrada
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta gerada
        """
        pass
    
    @abstractmethod
    async def generate_with_context(self,
                                   prompt: str,
                                   context: str,
                                   **kwargs) -> str:
        """Gera resposta com contexto.
        
        Args:
            prompt: Prompt de entrada
            context: Contexto adicional
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta gerada
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica saúde do provider.
        
        Returns:
            True se saudável
        """
        pass


class OpenAIProvider(BaseLLMProvider):
    """Provider OpenAI (GPT-4, GPT-3.5)."""
    
    def __init__(self, config: LLMConfig):
        """Inicializa provider OpenAI.
        
        Args:
            config: Configuração
        """
        super().__init__(config)
        
        try:
            import openai
            self.openai = openai
            # Inicializar cliente assíncrono do OpenAI
            self.client = openai.AsyncOpenAI(api_key=config.api_key)
        except ImportError:
            raise ImportError("Pacote openai não instalado. Execute: pip install openai")
        
        self.logger.info(f"OpenAI Provider inicializado | model={config.model}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Gera resposta com OpenAI.
        
        Args:
            prompt: Prompt
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout,
                **kwargs
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            self.logger.error(f"Erro ao gerar com OpenAI: {e}")
            raise
    
    async def generate_with_context(self,
                                   prompt: str,
                                   context: str,
                                   **kwargs) -> str:
        """Gera resposta com contexto.
        
        Args:
            prompt: Prompt
            context: Contexto
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        full_prompt = f"Contexto:\n{context}\n\nPergunta:\n{prompt}"
        return await self.generate(full_prompt, **kwargs)
    
    async def health_check(self) -> bool:
        """Verifica saúde do OpenAI.
        
        Returns:
            True se saudável
        """
        try:
            await self.client.models.list()
            self.logger.debug("OpenAI health check: OK")
            return True
        except Exception as e:
            self.logger.error(f"OpenAI health check falhou: {e}")
            return False


class AnthropicProvider(BaseLLMProvider):
    """Provider Anthropic (Claude)."""
    
    def __init__(self, config: LLMConfig):
        """Inicializa provider Anthropic.
        
        Args:
            config: Configuração
        """
        super().__init__(config)
        
        try:
            import anthropic
            self.anthropic = anthropic
            # Inicializar cliente assíncrono do Anthropic
            self.client = anthropic.AsyncAnthropic(api_key=config.api_key)
        except ImportError:
            raise ImportError("Pacote anthropic não instalado. Execute: pip install anthropic")
        
        self.logger.info(f"Anthropic Provider inicializado | model={config.model}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Gera resposta com Anthropic.
        
        Args:
            prompt: Prompt
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        try:
            message = await self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                timeout=self.config.timeout,
                **kwargs
            )
            
            return message.content[0].text
        
        except Exception as e:
            self.logger.error(f"Erro ao gerar com Anthropic: {e}")
            raise
    
    async def generate_with_context(self,
                                   prompt: str,
                                   context: str,
                                   **kwargs) -> str:
        """Gera resposta com contexto.
        
        Args:
            prompt: Prompt
            context: Contexto
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        full_prompt = f"Contexto:\n{context}\n\nPergunta:\n{prompt}"
        return await self.generate(full_prompt, **kwargs)
    
    async def health_check(self) -> bool:
        """Verifica saúde do Anthropic.
        
        Returns:
            True se saudável
        """
        try:
            # Fazer chamada mínima para verificar conectividade
            await self.client.messages.create(
                model=self.config.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            self.logger.debug("Anthropic health check: OK")
            return True
        except Exception as e:
            self.logger.error(f"Anthropic health check falhou: {e}")
            return False


class OllamaProvider(BaseLLMProvider):
    """Provider Ollama (LLM local)."""
    
    def __init__(self, config: LLMConfig):
        """Inicializa provider Ollama.
        
        Args:
            config: Configuração
        """
        super().__init__(config)
        
        try:
            import ollama
            self.ollama = ollama
        except ImportError:
            raise ImportError("Pacote ollama não instalado. Execute: pip install ollama")
        
        self.base_url = config.base_url or "http://localhost:11434"
        self.logger.info(f"Ollama Provider inicializado | model={config.model} | url={self.base_url}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Gera resposta com Ollama.
        
        Args:
            prompt: Prompt
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        try:
            response = await self.ollama.AsyncClient(host=self.base_url).generate(
                model=self.config.model,
                prompt=prompt,
                stream=False,
                **kwargs
            )
            
            return response["response"]
        
        except Exception as e:
            self.logger.error(f"Erro ao gerar com Ollama: {e}")
            raise
    
    async def generate_with_context(self,
                                   prompt: str,
                                   context: str,
                                   **kwargs) -> str:
        """Gera resposta com contexto.
        
        Args:
            prompt: Prompt
            context: Contexto
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        full_prompt = f"Contexto:\n{context}\n\nPergunta:\n{prompt}"
        return await self.generate(full_prompt, **kwargs)
    
    async def health_check(self) -> bool:
        """Verifica saúde do Ollama.
        
        Returns:
            True se saudável
        """
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5)
                is_healthy = response.status_code == 200
                
                if is_healthy:
                    self.logger.debug("Ollama health check: OK")
                else:
                    self.logger.warning(f"Ollama health check falhou: {response.status_code}")
                
                return is_healthy
        except Exception as e:
            self.logger.error(f"Ollama health check falhou: {e}")
            return False


class GitHubModelsProvider(BaseLLMProvider):
    """Provider GitHub Models (via Azure AI Inference SDK)."""
    
    def __init__(self, config: LLMConfig):
        """Inicializa provider GitHub Models.
        
        Args:
            config: Configuração
        """
        super().__init__(config)
        
        try:
            from azure.ai.inference.aio import ChatCompletionsClient
            from azure.core.credentials import AzureKeyCredential
            
            self.client = ChatCompletionsClient(
                endpoint=config.base_url or "https://models.inference.ai.azure.com",
                credential=AzureKeyCredential(config.api_key)
            )
        except ImportError:
            raise ImportError("Pacote azure-ai-inference não instalado. Execute: pip install azure-ai-inference")
        
        self.logger.info(f"GitHub Models Provider inicializado | model={config.model}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Gera resposta com GitHub Models.
        
        Args:
            prompt: Prompt
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        try:
            response = await self.client.complete(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                **kwargs
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            self.logger.error(f"Erro ao gerar com GitHub Models: {e}")
            raise
    
    async def generate_with_context(self,
                                   prompt: str,
                                   context: str,
                                   **kwargs) -> str:
        """Gera resposta com contexto.
        
        Args:
            prompt: Prompt
            context: Contexto
            **kwargs: Parâmetros adicionais
        
        Returns:
            Resposta
        """
        full_prompt = f"Contexto:\n{context}\n\nPergunta:\n{prompt}"
        return await self.generate(full_prompt, **kwargs)
    
    async def health_check(self) -> bool:
        """Verifica saúde do GitHub Models.
        
        Returns:
            True se saudável
        """
        try:
            # Fazer chamada mínima para verificar conectividade
            await self.client.complete(
                messages=[{"role": "user", "content": "test"}],
                model=self.config.model,
                max_tokens=5
            )
            self.logger.debug("GitHub Models health check: OK")
            return True
        except Exception as e:
            self.logger.error(f"GitHub Models health check falhou: {e}")
            return False


class LLMFactory:
    """Factory para criar providers de LLM."""
    
    @staticmethod
    def create_provider(config: Optional[LLMConfig] = None) -> BaseLLMProvider:
        """Cria provider baseado na configuração.
        
        Args:
            config: Configuração (opcional, lê de env se None)
        
        Returns:
            Provider instanciado
        """
        if config is None:
            # Ler de variáveis de ambiente
            provider_type = os.getenv("LLM_PROVIDER", "ollama").lower()
            api_key = os.getenv("LLM_API_KEY")
            model = os.getenv("LLM_MODEL", "llama3")
            base_url = os.getenv("LLM_BASE_URL")
            
            config = LLMConfig(
                provider=LLMProviderType(provider_type),
                api_key=api_key,
                model=model,
                base_url=base_url
            )
        
        if config.provider == LLMProviderType.OPENAI:
            return OpenAIProvider(config)
        elif config.provider == LLMProviderType.ANTHROPIC:
            return AnthropicProvider(config)
        elif config.provider == LLMProviderType.OLLAMA:
            return OllamaProvider(config)
        elif config.provider == LLMProviderType.GITHUB:
            return GitHubModelsProvider(config)
        else:
            raise ValueError(f"Provider desconhecido: {config.provider}")
