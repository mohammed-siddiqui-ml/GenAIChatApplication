"""
LLM Factory

Factory pattern for creating LLM clients based on configuration.
Supports switching between OpenAI and Ollama providers.
"""

import logging
from typing import Union

from core.config import settings
from integrations.openai_client import OpenAIClient
from integrations.ollama_client import OllamaClient


logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Factory for creating LLM client instances based on configuration.
    
    Supports:
    - OpenAI (cloud-based)
    - Ollama (local/self-hosted)
    """
    
    @staticmethod
    def create_client() -> Union[OpenAIClient, OllamaClient]:
        """
        Create an LLM client based on LLM_PROVIDER setting.

        Returns:
            OpenAIClient or OllamaClient instance

        Raises:
            ValueError: If LLM_PROVIDER is invalid
        """
        provider = settings.LLM_PROVIDER.lower()
        logger.info(f"LLMFactory: LLM_PROVIDER={settings.LLM_PROVIDER}, provider={provider}")

        if provider == "openai":
            logger.info("Creating OpenAI client")
            return OpenAIClient(
                api_key=settings.OPENAI_API_KEY,
                embedding_model=settings.EMBEDDING_MODEL,
                chat_model=settings.OPENAI_MODEL
            )
        elif provider == "ollama":
            logger.info(f"Creating Ollama client with base_url={settings.OLLAMA_BASE_URL}, embedding_model={settings.OLLAMA_EMBEDDING_MODEL}")
            return OllamaClient(
                base_url=settings.OLLAMA_BASE_URL,
                embedding_model=settings.OLLAMA_EMBEDDING_MODEL,
                chat_model=settings.OLLAMA_CHAT_MODEL
            )
        else:
            raise ValueError(
                f"Invalid LLM_PROVIDER: {provider}. "
                f"Must be 'openai' or 'ollama'"
            )
    
    @staticmethod
    def get_embedding_dimension() -> int:
        """
        Get the embedding dimension for the current provider.
        
        Returns:
            Embedding dimension size
        """
        provider = settings.LLM_PROVIDER.lower()
        
        if provider == "openai":
            return settings.EMBEDDING_DIMENSION
        elif provider == "ollama":
            return settings.OLLAMA_EMBEDDING_DIMENSION
        else:
            raise ValueError(f"Invalid LLM_PROVIDER: {provider}")
