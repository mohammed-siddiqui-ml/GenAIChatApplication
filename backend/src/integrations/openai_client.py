"""
OpenAI Client Integration

Provides a robust client wrapper for OpenAI API with:
- Text embeddings generation (text-embedding-3-small, 1536 dimensions)
- LLM chat completions (GPT-4 Turbo)
- Streaming responses
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Rate limiting and token usage tracking
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, AsyncIterator
from enum import Enum

import openai
import tiktoken
from openai import AsyncOpenAI, OpenAIError as BaseOpenAIError
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types import CreateEmbeddingResponse

from core.config import settings


# Logger
logger = logging.getLogger(__name__)


# Custom Exceptions
class OpenAIError(Exception):
    """Base exception for OpenAI client errors."""
    pass


class OpenAIRateLimitError(OpenAIError):
    """Raised when rate limit is exceeded."""
    pass


class OpenAIAPIError(OpenAIError):
    """Raised when OpenAI API returns an error."""
    pass


class CircuitBreakerOpen(OpenAIError):
    """Raised when circuit breaker is open."""
    pass


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Too many failures, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


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


class CircuitBreaker:
    """
    Circuit breaker implementation for API fault tolerance.

    Prevents cascading failures by temporarily blocking requests
    when error rate exceeds threshold.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            half_open_max_calls: Max calls to allow in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0

        logger.info(
            f"Circuit breaker initialized: threshold={failure_threshold}, "
            f"timeout={recovery_timeout}s"
        )

    def call(self) -> None:
        """
        Check if call is allowed.

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker is OPEN. Retry after {self.recovery_timeout - elapsed:.1f}s"
                    )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpen("Circuit breaker is HALF_OPEN and at capacity")
            self.half_open_calls += 1

    def record_success(self) -> None:
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker transitioning to CLOSED (recovered)")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.half_open_calls = 0

    def record_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker OPENING after {self.failure_count} failures"
            )
            self.state = CircuitState.OPEN

        # If in half-open and failed, go back to open
        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker reopening from HALF_OPEN")
            self.state = CircuitState.OPEN


class OpenAIClient:
    """
    Robust OpenAI API client with retry logic and circuit breaker.

    Features:
    - Text embeddings (text-embedding-3-small, 1536 dimensions)
    - Chat completions (GPT-4 Turbo)
    - Streaming responses
    - Exponential backoff retry (max 3 retries)
    - Circuit breaker for fault tolerance
    - Token counting and usage tracking
    """

    # Default models
    EMBEDDING_MODEL = "text-embedding-3-small"
    CHAT_MODEL = "gpt-4-turbo-preview"

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 10.0  # seconds

    # Batch limits
    MAX_EMBEDDING_BATCH_SIZE = 100

    def __init__(
        self,
        api_key: Optional[str] = None,
        embedding_model: Optional[str] = None,
        chat_model: Optional[str] = None,
        enable_circuit_breaker: bool = True
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
            embedding_model: Embedding model name
            chat_model: Chat completion model name
            enable_circuit_breaker: Whether to enable circuit breaker
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.embedding_model = embedding_model or settings.EMBEDDING_MODEL or self.EMBEDDING_MODEL
        self.chat_model = chat_model or settings.OPENAI_MODEL or self.CHAT_MODEL

        if not self.api_key:
            raise OpenAIError("OpenAI API key not provided")

        # Initialize async client
        self.client = AsyncOpenAI(api_key=self.api_key)

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

        # Usage tracking
        self.usage_stats = UsageStats()

        # Token encoder for counting
        self._encoder_cache: Dict[str, Any] = {}

        logger.info(
            f"OpenAI client initialized: embedding_model={self.embedding_model}, "
            f"chat_model={self.chat_model}"
        )

    def _get_encoder(self, model: str) -> Any:
        """Get or create token encoder for model."""
        if model not in self._encoder_cache:
            try:
                self._encoder_cache[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for newer models
                logger.warning(f"No encoder for {model}, using cl100k_base")
                self._encoder_cache[model] = tiktoken.get_encoding("cl100k_base")

        return self._encoder_cache[model]

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """
        Count tokens in text for given model.

        Args:
            text: Text to count tokens for
            model: Model name (defaults to chat model)

        Returns:
            Number of tokens
        """
        model = model or self.chat_model
        encoder = self._get_encoder(model)
        return len(encoder.encode(text))

    async def _retry_with_backoff(
        self,
        func,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with exponential backoff retry.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            OpenAIError: If all retries exhausted
        """
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Check circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.call()

                # Execute function
                result = await func(*args, **kwargs)

                # Record success
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                return result

            except openai.RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                # Always retry rate limits with backoff
                if attempt < self.MAX_RETRIES - 1:
                    delay = min(
                        self.BASE_RETRY_DELAY * (2 ** attempt),
                        self.MAX_RETRY_DELAY
                    )
                    logger.info(f"Retrying after {delay}s...")
                    await asyncio.sleep(delay)

            except openai.APIError as e:
                last_exception = e
                logger.error(f"API error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                # Retry on server errors (5xx)
                if attempt < self.MAX_RETRIES - 1 and hasattr(e, 'status_code') and e.status_code >= 500:
                    delay = min(
                        self.BASE_RETRY_DELAY * (2 ** attempt),
                        self.MAX_RETRY_DELAY
                    )
                    logger.info(f"Retrying after {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    break

            except CircuitBreakerOpen as e:
                logger.error(f"Circuit breaker open: {e}")
                raise

            except BaseOpenAIError as e:
                last_exception = e
                logger.error(f"OpenAI error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                break  # Don't retry on client errors

            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                break

        # All retries exhausted
        if isinstance(last_exception, openai.RateLimitError):
            raise OpenAIRateLimitError(f"Rate limit exceeded: {last_exception}")
        elif isinstance(last_exception, BaseOpenAIError):
            raise OpenAIAPIError(f"OpenAI API error: {last_exception}")
        else:
            raise OpenAIError(f"Request failed: {last_exception}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to generate embedding for

        Returns:
            List of 1536 floats representing the embedding

        Raises:
            OpenAIError: If embedding generation fails
        """
        if not text or not text.strip():
            raise OpenAIError("Text cannot be empty")

        try:
            logger.debug(f"Generating embedding for text ({len(text)} chars)")

            response: CreateEmbeddingResponse = await self._retry_with_backoff(
                self.client.embeddings.create,
                model=self.embedding_model,
                input=text
            )

            # Extract embedding
            embedding = response.data[0].embedding

            # Update usage stats
            if hasattr(response, 'usage') and response.usage:
                self.usage_stats.update(response.usage.prompt_tokens, 0)

            logger.debug(f"Embedding generated: {len(embedding)} dimensions")

            return embedding

        except (OpenAIRateLimitError, OpenAIAPIError, CircuitBreakerOpen):
            raise
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise OpenAIError(f"Embedding generation failed: {e}")

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to generate embeddings for
            batch_size: Batch size (max 100, defaults to MAX_EMBEDDING_BATCH_SIZE)

        Returns:
            List of embeddings (each is a list of 1536 floats)

        Raises:
            OpenAIError: If batch processing fails
        """
        if not texts:
            return []

        # Filter out empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            raise OpenAIError("No valid texts provided")

        batch_size = min(batch_size or self.MAX_EMBEDDING_BATCH_SIZE, self.MAX_EMBEDDING_BATCH_SIZE)

        logger.info(f"Generating embeddings for {len(valid_texts)} texts in batches of {batch_size}")

        all_embeddings = []

        try:
            # Process in batches
            for i in range(0, len(valid_texts), batch_size):
                batch = valid_texts[i:i + batch_size]

                logger.debug(f"Processing batch {i // batch_size + 1} ({len(batch)} texts)")

                response: CreateEmbeddingResponse = await self._retry_with_backoff(
                    self.client.embeddings.create,
                    model=self.embedding_model,
                    input=batch
                )

                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                # Update usage stats
                if hasattr(response, 'usage') and response.usage:
                    self.usage_stats.update(response.usage.prompt_tokens, 0)

            logger.info(f"Generated {len(all_embeddings)} embeddings")

            return all_embeddings

        except (OpenAIRateLimitError, OpenAIAPIError, CircuitBreakerOpen):
            raise
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise OpenAIError(f"Batch embedding generation failed: {e}")

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2, defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            **kwargs: Additional OpenAI API parameters

        Returns:
            Dict with 'content', 'role', 'finish_reason', 'usage'

        Raises:
            OpenAIError: If completion generation fails
        """
        if not messages:
            raise OpenAIError("Messages cannot be empty")

        temperature = temperature if temperature is not None else settings.OPENAI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.OPENAI_MAX_TOKENS

        try:
            logger.debug(f"Generating completion with {len(messages)} messages")

            response: ChatCompletion = await self._retry_with_backoff(
                self.client.chat.completions.create,
                model=self.chat_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            # Extract completion
            choice = response.choices[0]
            content = choice.message.content or ""

            # Update usage stats
            if response.usage:
                self.usage_stats.update(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )

            result = {
                "content": content,
                "role": choice.message.role,
                "finish_reason": choice.finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            }

            logger.debug(
                f"Completion generated: {len(content)} chars, "
                f"{result['usage']['total_tokens']} tokens"
            )

            return result

        except (OpenAIRateLimitError, OpenAIAPIError, CircuitBreakerOpen):
            raise
        except Exception as e:
            logger.error(f"Failed to generate completion: {e}")
            raise OpenAIError(f"Completion generation failed: {e}")

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
            **kwargs: Additional OpenAI API parameters

        Yields:
            Content chunks as they arrive

        Raises:
            OpenAIError: If streaming fails
        """
        if not messages:
            raise OpenAIError("Messages cannot be empty")

        temperature = temperature if temperature is not None else settings.OPENAI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.OPENAI_MAX_TOKENS

        try:
            logger.debug(f"Generating streaming completion with {len(messages)} messages")

            # Check circuit breaker before streaming
            if self.circuit_breaker:
                self.circuit_breaker.call()

            stream = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )

            chunk_count = 0
            total_content = ""

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        chunk_count += 1
                        total_content += delta.content
                        yield delta.content

            # Record success after streaming completes
            if self.circuit_breaker:
                self.circuit_breaker.record_success()

            logger.debug(
                f"Streaming completed: {chunk_count} chunks, "
                f"{len(total_content)} chars"
            )

        except openai.RateLimitError as e:
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            logger.error(f"Rate limit during streaming: {e}")
            raise OpenAIRateLimitError(f"Rate limit exceeded: {e}")

        except CircuitBreakerOpen:
            raise

        except BaseOpenAIError as e:
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            logger.error(f"API error during streaming: {e}")
            raise OpenAIAPIError(f"OpenAI API error: {e}")

        except Exception as e:
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            logger.error(f"Failed to generate streaming completion: {e}")
            raise OpenAIError(f"Streaming completion failed: {e}")

    def get_usage_stats(self) -> Dict[str, int]:
        """
        Get current usage statistics.

        Returns:
            Dict with token usage counts
        """
        return {
            "prompt_tokens": self.usage_stats.prompt_tokens,
            "completion_tokens": self.usage_stats.completion_tokens,
            "total_tokens": self.usage_stats.total_tokens,
        }

    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        self.usage_stats = UsageStats()
        logger.info("Usage statistics reset")

    def get_circuit_breaker_state(self) -> Optional[str]:
        """
        Get current circuit breaker state.

        Returns:
            Circuit state name or None if disabled
        """
        if self.circuit_breaker:
            return self.circuit_breaker.state.value
        return None

