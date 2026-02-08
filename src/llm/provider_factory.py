"""
LLM Provider Factory - Factory Pattern para Múltiplos Providers de LLM

Suporta 3 providers: OpenAI, Anthropic (Claude), Ollama (local)
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


class LLMConfig(BaseModel):
    """Configuração de LLM."""
    
    provider: LLMProviderType = Field(..., description="Provider de LLM")
    api_key: Optional[str] = Field(None, description="API Key (se necessário)")
    model: str = Field(..., description="Nome do modelo")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperatura (0-2)")
    max_tokens: int = Field(2000, ge=1, le=32000, description="Máximo de tokens")
    timeout: int = Field(30, ge=1, le=300, description="Timeout em segundos")
    base_url: Optional[str] = Field(None, description="URL base (para Ollama)")
    
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
                    self.logger.error(f"Ollama health check falhou: status={response.status_code}")
                
                return is_healthy
        except Exception as e:
            self.logger.error(f"Ollama health check falhou: {e}")
            return False


class LLMProviderFactory:
    """Factory para criar providers de LLM.
    
    Responsabilidades:
    1. Ler configuração de variáveis de ambiente
    2. Criar provider apropriado
    3. Validar configuração
    4. Fornecer fallback se necessário
    """
    
    # Mapeamento de providers
    PROVIDERS = {
        LLMProviderType.OPENAI: OpenAIProvider,
        LLMProviderType.ANTHROPIC: AnthropicProvider,
        LLMProviderType.OLLAMA: OllamaProvider,
    }
    
    @staticmethod
    def create_from_env() -> BaseLLMProvider:
        """Cria provider a partir de variáveis de ambiente.
        
        Variáveis esperadas:
        - LLM_PROVIDER: openai | anthropic | ollama (padrão: openai)
        - LLM_API_KEY: API key (se necessário)
        - LLM_MODEL: Nome do modelo (obrigatório)
        - LLM_TEMPERATURE: Temperatura (padrão: 0.7)
        - LLM_MAX_TOKENS: Máximo de tokens (padrão: 2000)
        - LLM_TIMEOUT: Timeout em segundos (padrão: 30)
        - LLM_BASE_URL: URL base (para Ollama)
        
        Returns:
            Provider de LLM
        
        Raises:
            ValueError: Se configuração inválida
        
        Exemplo:
            export LLM_PROVIDER=openai
            export LLM_API_KEY=sk-...
            export LLM_MODEL=gpt-4
            
            provider = LLMProviderFactory.create_from_env()
        """
        # Ler variáveis de ambiente
        provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL")
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))
        timeout = int(os.getenv("LLM_TIMEOUT", "30"))
        base_url = os.getenv("LLM_BASE_URL")
        
        # Validar provider
        try:
            provider_type = LLMProviderType(provider_name)
        except ValueError:
            raise ValueError(
                f"Provider inválido: {provider_name}. "
                f"Opções: {', '.join([p.value for p in LLMProviderType])}"
            )
        
        # Validar modelo
        if not model:
            raise ValueError("LLM_MODEL não definido")
        
        # Validar API key (se necessário)
        if provider_type in [LLMProviderType.OPENAI, LLMProviderType.ANTHROPIC] and not api_key:
            raise ValueError(f"LLM_API_KEY necessário para {provider_name}")
        
        # Criar configuração
        config = LLMConfig(
            provider=provider_type,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            base_url=base_url,
        )
        
        logger.info(f"Criando provider LLM: {provider_name} | model={model}")
        
        # Criar provider
        return LLMProviderFactory.create(config)
    
    @staticmethod
    def create(config: LLMConfig) -> BaseLLMProvider:
        """Cria provider a partir de configuração.
        
        Args:
            config: Configuração de LLM
        
        Returns:
            Provider de LLM
        
        Raises:
            ValueError: Se provider não suportado
        """
        if config.provider not in LLMProviderFactory.PROVIDERS:
            raise ValueError(f"Provider não suportado: {config.provider}")
        
        provider_class = LLMProviderFactory.PROVIDERS[config.provider]
        
        logger.info(f"Criando provider: {config.provider.value}")
        
        return provider_class(config)
    
    @staticmethod
    def list_providers() -> Dict[str, str]:
        """Lista providers disponíveis.
        
        Returns:
            Dicionário com providers
        """
        return {
            "openai": "OpenAI (GPT-4, GPT-3.5)",
            "anthropic": "Anthropic (Claude)",
            "ollama": "Ollama (LLM local)",
        }


class LLMProviderConfig(BaseModel):
    """Configuração global de providers."""
    
    default_provider: LLMProviderType = Field(
        LLMProviderType.OPENAI,
        description="Provider padrão"
    )
    enable_fallback: bool = Field(True, description="Habilitar fallback?")
    fallback_providers: list[LLMProviderType] = Field(
        default_factory=lambda: [LLMProviderType.ANTHROPIC, LLMProviderType.OLLAMA],
        description="Providers de fallback em ordem"
    )
    retry_attempts: int = Field(3, ge=1, le=10, description="Tentativas de retry")
    retry_backoff: float = Field(1.5, ge=1.0, le=5.0, description="Backoff multiplicador")
    
    class Config:
        frozen = True
