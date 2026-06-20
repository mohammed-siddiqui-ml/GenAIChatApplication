"""
Ollama Client Integration

Provides a client wrapper for Ollama API for local LLM execution with:
- Text embeddings generation using local models
- LLM chat completions using local models (e.g., llama2, mistral, codellama)
- Streaming responses
- Retry logic with exponential backoff
- Compatible interface with OpenAI client for easy switching
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, AsyncIterator
from enum import Enum

import httpx

from core.config import settings
from core.metrics import (
    llm_api_requests_total,
    llm_api_duration,
    llm_tokens_used,
    embedding_generation_total,
)


# Logger
logger = logging.getLogger(__name__)


# Custom Exceptions
class OllamaError(Exception):
    """Base exception for Ollama client errors."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when connection to Ollama server fails."""
    pass


class OllamaAPIError(OllamaError):
    """Raised when Ollama API returns an error."""
    pass


@dataclass
class UsageStats:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def update(self, prompt: int, completion: int) -> None:
        """Update usage statistics."""
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += (prompt + completion)


class OllamaClient:
    """
    Ollama API client for local LLM execution.

    Features:
    - Text embeddings using local models (e.g., nomic-embed-text)
    - Chat completions using local models (e.g., llama2, mistral)
    - Streaming responses
    - Retry logic with exponential backoff
    - Compatible with OpenAI client interface
    """

    # Default models
    EMBEDDING_MODEL = "nomic-embed-text"  # 768 dimensions
    CHAT_MODEL = "llama2"  # Default chat model

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 10.0  # seconds

    def __init__(
        self,
        base_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        chat_model: Optional[str] = None,
        timeout: float = 120.0
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server URL (defaults to settings.OLLAMA_BASE_URL)
            embedding_model: Embedding model name
            chat_model: Chat completion model name
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip('/')
        self.embedding_model = embedding_model or settings.OLLAMA_EMBEDDING_MODEL or self.EMBEDDING_MODEL
        self.chat_model = chat_model or settings.OLLAMA_CHAT_MODEL or self.CHAT_MODEL
        self.timeout = timeout

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )

        # Usage tracking
        self.usage_stats = UsageStats()

        logger.info(
            f"Ollama client initialized: base_url={self.base_url}, "
            f"embedding_model={self.embedding_model}, chat_model={self.chat_model}"
        )

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic."""
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = min(
                        self.BASE_RETRY_DELAY * (2 ** attempt),
                        self.MAX_RETRY_DELAY
                    )
                    logger.warning(
                        f"Ollama request failed (attempt {attempt + 1}/{self.MAX_RETRIES}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Ollama request failed after {self.MAX_RETRIES} attempts")

        raise OllamaConnectionError(f"Failed to connect to Ollama server: {last_exception}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            OllamaError: If embedding generation fails
        """
        if not text or not text.strip():
            raise OllamaError("Input text cannot be empty")

        start_time = time.time()

        try:
            response = await self._retry_with_backoff(
                self.client.post,
                "/api/embeddings",
                json={"model": self.embedding_model, "prompt": text}
            )
            response.raise_for_status()
            data = response.json()

            duration = time.time() - start_time
            embedding = data.get("embedding", [])

            # Update metrics
            embedding_generation_total.labels(
                model=self.embedding_model,
                status="success"
            ).inc()

            logger.debug(f"Generated embedding: dim={len(embedding)}, time={duration:.3f}s")
            return embedding

        except httpx.HTTPStatusError as e:
            embedding_generation_total.labels(
                model=self.embedding_model,
                status="error"
            ).inc()
            logger.error(f"Embedding generation HTTP error: {e}")
            raise OllamaAPIError(f"Embedding generation failed: {e}")
        except Exception as e:
            embedding_generation_total.labels(
                model=self.embedding_model,
                status="error"
            ).inc()
            logger.error(f"Embedding generation error: {e}")
            raise OllamaError(f"Embedding generation failed: {e}")

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors

        Raises:
            OllamaError: If batch embedding generation fails
        """
        if not texts:
            return []

        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)

        return embeddings

    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion (non-streaming).

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2, defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            stream: Must be False for this method
            **kwargs: Additional Ollama API parameters

        Returns:
            Dict containing response with OpenAI-compatible structure

        Raises:
            OllamaError: If completion generation fails
        """
        if not messages:
            raise OllamaError("Messages cannot be empty")

        if stream:
            raise OllamaError("Use generate_completion_stream for streaming responses")

        temperature = temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.OLLAMA_MAX_TOKENS

        start_time = time.time()

        try:
            # Convert messages to Ollama format
            # Ollama expects a single prompt, so we combine messages
            prompt = self._format_messages(messages)

            payload = {
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            response = await self._retry_with_backoff(
                self.client.post,
                "/api/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            duration = time.time() - start_time

            # Extract response text
            content = data.get("response", "")

            # Estimate token counts (Ollama doesn't provide exact counts)
            prompt_tokens = len(prompt.split())
            completion_tokens = len(content.split())

            # Update stats
            self.usage_stats.update(prompt_tokens, completion_tokens)

            # Update metrics
            llm_api_requests_total.labels(
                model=self.chat_model,
                status="success"
            ).inc()

            llm_api_duration.labels(model=self.chat_model).observe(duration)
            llm_tokens_used.labels(
                model=self.chat_model,
                token_type="prompt"
            ).inc(prompt_tokens)
            llm_tokens_used.labels(
                model=self.chat_model,
                token_type="completion"
            ).inc(completion_tokens)

            logger.debug(f"Completion generated: tokens={completion_tokens}, time={duration:.3f}s")

            # Return OpenAI-compatible format
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }],
                "model": self.chat_model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            }

        except httpx.HTTPStatusError as e:
            llm_api_requests_total.labels(
                model=self.chat_model,
                status="error"
            ).inc()
            logger.error(f"Completion HTTP error: {e}")
            raise OllamaAPIError(f"Completion generation failed: {e}")
        except Exception as e:
            llm_api_requests_total.labels(
                model=self.chat_model,
                status="error"
            ).inc()
            logger.error(f"Completion error: {e}")
            raise OllamaError(f"Completion generation failed: {e}")

    async def generate_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2, defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            **kwargs: Additional Ollama API parameters

        Yields:
            Content chunks as they arrive

        Raises:
            OllamaError: If streaming fails
        """
        if not messages:
            raise OllamaError("Messages cannot be empty")

        temperature = temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.OLLAMA_MAX_TOKENS

        try:
            prompt = self._format_messages(messages)

            payload = {
                "model": self.chat_model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            async with self.client.stream("POST", "/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        import json
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse streaming response: {line}")

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise OllamaError(f"Streaming failed: {e}")

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Format messages list into a single prompt string for Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Formatted prompt string
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")

        return "\n\n".join(formatted) + "\n\nAssistant:"

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

