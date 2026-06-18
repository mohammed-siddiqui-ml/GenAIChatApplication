"""
Tests for OpenAI Client Integration (Task-015)

This test module validates:
- Text embeddings generation (text-embedding-3-small, 1536 dimensions)
- LLM chat completions (GPT-4 Turbo)
- Streaming responses
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Token counting and usage tracking
- Error handling and rate limiting
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any

from integrations.openai_client import (
    OpenAIClient,
    OpenAIError,
    OpenAIRateLimitError,
    OpenAIAPIError,
    CircuitBreakerOpen,
    CircuitState,
    UsageStats,
    CircuitBreaker,
)


# ========== Test Data ==========

TEST_API_KEY = "sk-test-key-1234567890"
SAMPLE_TEXT = "Hello, world!"
SAMPLE_EMBEDDING = [0.1] * 1536  # 1536-dimensional vector
SAMPLE_MESSAGES = [{"role": "user", "content": "What is AI?"}]
SAMPLE_COMPLETION = "Artificial Intelligence (AI) is..."


# ========== Test Fixtures ==========

@pytest_asyncio.fixture
async def mock_openai_client():
    """Create a mocked AsyncOpenAI client."""
    with patch('integrations.openai_client.AsyncOpenAI') as mock:
        yield mock


@pytest_asyncio.fixture
async def openai_client(mock_openai_client):
    """Create OpenAIClient instance with mocked backend."""
    client = OpenAIClient(api_key=TEST_API_KEY)
    return client


@pytest_asyncio.fixture
def mock_embedding_response():
    """Create mock embedding response."""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=SAMPLE_EMBEDDING)]
    mock_response.usage = MagicMock(prompt_tokens=10, total_tokens=10)
    return mock_response


@pytest_asyncio.fixture
def mock_completion_response():
    """Create mock chat completion response."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = SAMPLE_COMPLETION
    mock_choice.message.role = "assistant"
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30
    )
    return mock_response


# ========== Client Initialization Tests ==========

def test_init_with_valid_api_key():
    """TC-001: Initialize client with valid API key."""
    client = OpenAIClient(api_key=TEST_API_KEY)

    assert client.api_key == TEST_API_KEY
    # Note: embedding_model comes from environment variable EMBEDDING_MODEL set in conftest.py
    # to prevent SSL errors during test setup. The actual value is "openai" not the default.
    assert client.embedding_model == "openai"  # From conftest.py environment variable
    assert client.chat_model == "gpt-4-turbo-preview"
    assert client.circuit_breaker is not None
    assert client.usage_stats.prompt_tokens == 0
    assert client.usage_stats.completion_tokens == 0


def test_init_without_api_key():
    """TC-002: Initialize client without API key should raise error."""
    with patch('integrations.openai_client.settings') as mock_settings:
        mock_settings.OPENAI_API_KEY = None
        
        with pytest.raises(OpenAIError, match="OpenAI API key not provided"):
            OpenAIClient()


def test_init_with_custom_models():
    """TC-003: Initialize client with custom models."""
    client = OpenAIClient(
        api_key=TEST_API_KEY,
        embedding_model="custom-embedding-model",
        chat_model="custom-chat-model"
    )
    
    assert client.embedding_model == "custom-embedding-model"
    assert client.chat_model == "custom-chat-model"


def test_init_with_circuit_breaker_disabled():
    """TC-004: Initialize client with circuit breaker disabled."""
    client = OpenAIClient(api_key=TEST_API_KEY, enable_circuit_breaker=False)
    
    assert client.circuit_breaker is None


# ========== Embedding Generation Tests ==========

@pytest.mark.asyncio
async def test_generate_embedding_success(openai_client, mock_embedding_response):
    """TC-003: Generate embedding for valid text."""
    openai_client.client.embeddings.create = AsyncMock(return_value=mock_embedding_response)
    
    embedding = await openai_client.generate_embedding(SAMPLE_TEXT)
    
    assert len(embedding) == 1536
    assert all(isinstance(x, float) for x in embedding)
    assert openai_client.usage_stats.prompt_tokens == 10
    assert openai_client.usage_stats.completion_tokens == 0


@pytest.mark.asyncio
async def test_generate_embedding_empty_text(openai_client):
    """TC-004: Generate embedding with empty text should fail."""
    with pytest.raises(OpenAIError, match="Text cannot be empty"):
        await openai_client.generate_embedding("")
    
    with pytest.raises(OpenAIError, match="Text cannot be empty"):
        await openai_client.generate_embedding("   ")


@pytest.mark.asyncio
async def test_generate_embeddings_batch(openai_client, mock_embedding_response):
    """TC-005: Generate embeddings for multiple texts."""
    # Mock batch response with multiple embeddings
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=SAMPLE_EMBEDDING),
        MagicMock(embedding=SAMPLE_EMBEDDING),
        MagicMock(embedding=SAMPLE_EMBEDDING),
    ]
    mock_response.usage = MagicMock(prompt_tokens=30, total_tokens=30)

    openai_client.client.embeddings.create = AsyncMock(return_value=mock_response)

    texts = ["text1", "text2", "", "text3"]
    embeddings = await openai_client.generate_embeddings_batch(texts)

    assert len(embeddings) == 3  # Empty text filtered
    assert all(len(emb) == 1536 for emb in embeddings)


@pytest.mark.asyncio
async def test_batch_embeddings_all_empty(openai_client):
    """TC-020: Batch with all empty texts should fail."""
    with pytest.raises(OpenAIError, match="No valid texts provided"):
        await openai_client.generate_embeddings_batch(["", "  ", "\n"])


@pytest.mark.asyncio
async def test_batch_embeddings_chunking(openai_client):
    """TC-006: Batch embeddings with chunking (>100 texts)."""
    # Create mock that returns correct number of embeddings per batch
    def create_batch_response(batch_size):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=SAMPLE_EMBEDDING) for _ in range(batch_size)]
        mock_response.usage = MagicMock(prompt_tokens=batch_size, total_tokens=batch_size)
        return mock_response

    # Mock will be called 3 times with batches of 100, 100, and 50
    openai_client.client.embeddings.create = AsyncMock(
        side_effect=[
            create_batch_response(100),
            create_batch_response(100),
            create_batch_response(50)
        ]
    )

    texts = [f"text{i}" for i in range(250)]
    embeddings = await openai_client.generate_embeddings_batch(texts)

    # Should call API 3 times (100, 100, 50)
    assert openai_client.client.embeddings.create.call_count == 3
    assert len(embeddings) == 250


# ========== Chat Completion Tests ==========

@pytest.mark.asyncio
async def test_generate_completion_success(openai_client, mock_completion_response):
    """TC-007: Generate chat completion."""
    openai_client.client.chat.completions.create = AsyncMock(return_value=mock_completion_response)

    result = await openai_client.generate_completion(SAMPLE_MESSAGES)

    assert result["content"] == SAMPLE_COMPLETION
    assert result["role"] == "assistant"
    assert result["finish_reason"] == "stop"
    assert result["usage"]["prompt_tokens"] == 10
    assert result["usage"]["completion_tokens"] == 20
    assert openai_client.usage_stats.prompt_tokens == 10
    assert openai_client.usage_stats.completion_tokens == 20


@pytest.mark.asyncio
async def test_generate_completion_empty_messages(openai_client):
    """TC-016: Generate completion with empty messages should fail."""
    with pytest.raises(OpenAIError, match="Messages cannot be empty"):
        await openai_client.generate_completion([])


@pytest.mark.asyncio
async def test_generate_completion_custom_params(openai_client, mock_completion_response):
    """TC-016: Custom temperature and max_tokens."""
    openai_client.client.chat.completions.create = AsyncMock(return_value=mock_completion_response)

    await openai_client.generate_completion(
        SAMPLE_MESSAGES,
        temperature=0.2,
        max_tokens=100
    )

    # Verify parameters passed to API
    call_kwargs = openai_client.client.chat.completions.create.call_args[1]
    assert call_kwargs["temperature"] == 0.2
    assert call_kwargs["max_tokens"] == 100


# ========== Streaming Completion Tests ==========

@pytest.mark.asyncio
async def test_generate_completion_stream(openai_client):
    """TC-008: Generate streaming completion."""
    # Create mock streaming response
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta.content = "Hello "

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta.content = "world!"

    async def mock_stream():
        yield mock_chunk1
        yield mock_chunk2

    openai_client.client.chat.completions.create = AsyncMock(return_value=mock_stream())

    chunks = []
    async for chunk in openai_client.generate_completion_stream(SAMPLE_MESSAGES):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert "".join(chunks) == "Hello world!"


@pytest.mark.asyncio
async def test_streaming_empty_messages(openai_client):
    """TC-023: Streaming with empty messages should fail."""
    with pytest.raises(OpenAIError, match="Messages cannot be empty"):
        async for _ in openai_client.generate_completion_stream([]):
            pass


# ========== Retry Logic Tests ==========

@pytest.mark.asyncio
async def test_retry_on_rate_limit(openai_client, mock_embedding_response):
    """TC-009: Retry logic on rate limit with exponential backoff."""
    import openai
    from httpx import Response, Request

    # Create proper rate limit error with request object
    mock_request = Request("POST", "https://api.openai.com/v1/embeddings")
    mock_response = Response(status_code=429, text="Rate limit exceeded", request=mock_request)

    # Fail twice, then succeed
    openai_client.client.embeddings.create = AsyncMock(
        side_effect=[
            openai.RateLimitError("Rate limit exceeded", response=mock_response, body=None),
            openai.RateLimitError("Rate limit exceeded", response=mock_response, body=None),
            mock_embedding_response
        ]
    )

    with patch('asyncio.sleep') as mock_sleep:
        embedding = await openai_client.generate_embedding(SAMPLE_TEXT)

        # Should have retried with exponential backoff
        assert mock_sleep.call_count == 2
        assert len(embedding) == 1536


@pytest.mark.asyncio
async def test_retry_exhaustion(openai_client):
    """TC-010: Retry exhaustion after max retries."""
    import openai
    from httpx import Response, Request

    # Create proper rate limit error with request object
    mock_request = Request("POST", "https://api.openai.com/v1/embeddings")
    mock_response = Response(status_code=429, text="Rate limit exceeded", request=mock_request)

    openai_client.client.embeddings.create = AsyncMock(
        side_effect=openai.RateLimitError("Rate limit exceeded", response=mock_response, body=None)
    )

    with patch('asyncio.sleep'):
        with pytest.raises(OpenAIRateLimitError):
            await openai_client.generate_embedding(SAMPLE_TEXT)

        # Should have tried exactly 3 times (MAX_RETRIES)
        assert openai_client.client.embeddings.create.call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_client_errors(openai_client):
    """TC-018: No retry on client errors (4xx)."""
    import openai
    from httpx import Response, Request

    mock_response = Response(status_code=400, text="Bad request")
    mock_request = Request("POST", "https://api.openai.com/v1/embeddings")

    mock_error = openai.APIError("Bad request", request=mock_request, body=None)
    mock_error.status_code = 400

    openai_client.client.embeddings.create = AsyncMock(side_effect=mock_error)

    with pytest.raises(OpenAIAPIError):
        await openai_client.generate_embedding(SAMPLE_TEXT)

    # Should only call once, no retries
    assert openai_client.client.embeddings.create.call_count == 1


@pytest.mark.asyncio
async def test_retry_on_server_errors(openai_client, mock_embedding_response):
    """TC-019: Retry on server errors (5xx)."""
    import openai
    from httpx import Response, Request

    mock_response = Response(status_code=500, text="Internal server error")
    mock_request = Request("POST", "https://api.openai.com/v1/embeddings")

    mock_error = openai.APIError("Internal server error", request=mock_request, body=None)
    mock_error.status_code = 500

    openai_client.client.embeddings.create = AsyncMock(
        side_effect=[mock_error, mock_error, mock_embedding_response]
    )

    with patch('asyncio.sleep'):
        embedding = await openai_client.generate_embedding(SAMPLE_TEXT)

        assert len(embedding) == 1536
        assert openai_client.client.embeddings.create.call_count == 3


# ========== Circuit Breaker Tests ==========

def test_circuit_breaker_initial_state():
    """TC-011: Circuit breaker starts in CLOSED state."""
    cb = CircuitBreaker()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_circuit_breaker_opens_after_failures():
    """TC-011: Circuit breaker opens after threshold failures."""
    cb = CircuitBreaker(failure_threshold=5)

    # Record 5 failures
    for _ in range(5):
        cb.record_failure()

    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 5


def test_circuit_breaker_raises_when_open():
    """TC-011: Circuit breaker raises exception when open."""
    cb = CircuitBreaker(failure_threshold=1)

    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpen):
        cb.call()


def test_circuit_breaker_transitions_to_half_open():
    """TC-012: Circuit breaker transitions to HALF_OPEN after timeout."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)

    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Mock time passage
    with patch('integrations.openai_client.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = cb.last_failure_time + timedelta(seconds=61)

        # Should transition to HALF_OPEN on next call
        cb.call()
        assert cb.state == CircuitState.HALF_OPEN


def test_circuit_breaker_closes_on_success():
    """TC-012: Circuit breaker closes after successful HALF_OPEN call."""
    cb = CircuitBreaker()

    cb.state = CircuitState.HALF_OPEN
    cb.record_success()

    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_circuit_breaker_reopens_on_half_open_failure():
    """TC-013: Circuit breaker reopens if HALF_OPEN call fails."""
    cb = CircuitBreaker()

    cb.state = CircuitState.HALF_OPEN
    cb.record_failure()

    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_integration(openai_client):
    """TC-011: Circuit breaker prevents calls when open."""
    import openai
    from httpx import Response, Request

    mock_response = Response(status_code=500, text="API Error")
    mock_request = Request("POST", "https://api.openai.com/v1/embeddings")

    openai_client.client.embeddings.create = AsyncMock(
        side_effect=openai.APIError("API Error", request=mock_request, body=None)
    )

    # Trigger 5 failures to open circuit
    for i in range(5):
        try:
            await openai_client.generate_embedding(SAMPLE_TEXT)
        except:
            pass

    # Circuit should be open now
    assert openai_client.circuit_breaker.state == CircuitState.OPEN

    # Next call should fail immediately without API call
    call_count_before = openai_client.client.embeddings.create.call_count

    with pytest.raises(CircuitBreakerOpen):
        await openai_client.generate_embedding(SAMPLE_TEXT)

    # API should not have been called
    assert openai_client.client.embeddings.create.call_count == call_count_before


# ========== Token Counting Tests ==========

def test_count_tokens():
    """TC-014: Token counting."""
    client = OpenAIClient(api_key=TEST_API_KEY)

    count = client.count_tokens("Hello, world!")
    assert isinstance(count, int)
    assert count > 0


def test_count_tokens_with_model():
    """TC-014: Token counting with specific model."""
    client = OpenAIClient(api_key=TEST_API_KEY)

    count1 = client.count_tokens("Test text", model="gpt-4")
    count2 = client.count_tokens("Test text", model="gpt-3.5-turbo")

    assert isinstance(count1, int)
    assert isinstance(count2, int)
    assert count1 > 0
    assert count2 > 0


# ========== Usage Statistics Tests ==========

def test_usage_stats_initial():
    """TC-015: Initial usage stats are zero."""
    stats = UsageStats()
    assert stats.prompt_tokens == 0
    assert stats.completion_tokens == 0
    assert stats.total_tokens == 0


def test_usage_stats_update():
    """TC-015: Usage stats update correctly."""
    stats = UsageStats()
    stats.update(10, 20)

    assert stats.prompt_tokens == 10
    assert stats.completion_tokens == 20
    assert stats.total_tokens == 30


def test_usage_stats_cumulative():
    """TC-015: Cumulative usage stats tracking."""
    stats = UsageStats()
    stats.update(10, 20)
    stats.update(5, 10)

    assert stats.prompt_tokens == 15
    assert stats.completion_tokens == 30
    assert stats.total_tokens == 45


@pytest.mark.asyncio
async def test_usage_stats_tracking(openai_client, mock_embedding_response, mock_completion_response):
    """TC-015: Usage stats updated after operations."""
    # Initial stats should be zero
    assert openai_client.usage_stats.prompt_tokens == 0

    # Generate embedding
    openai_client.client.embeddings.create = AsyncMock(return_value=mock_embedding_response)
    await openai_client.generate_embedding(SAMPLE_TEXT)

    assert openai_client.usage_stats.prompt_tokens == 10
    assert openai_client.usage_stats.completion_tokens == 0

    # Generate completion
    openai_client.client.chat.completions.create = AsyncMock(return_value=mock_completion_response)
    await openai_client.generate_completion(SAMPLE_MESSAGES)

    assert openai_client.usage_stats.prompt_tokens == 20  # 10 + 10
    assert openai_client.usage_stats.completion_tokens == 20


def test_reset_usage_stats(openai_client):
    """TC-015: Reset usage statistics."""
    openai_client.usage_stats.update(100, 200)

    openai_client.reset_usage_stats()

    assert openai_client.usage_stats.prompt_tokens == 0
    assert openai_client.usage_stats.completion_tokens == 0
    assert openai_client.usage_stats.total_tokens == 0


def test_get_usage_stats(openai_client):
    """TC-015: Get usage statistics."""
    openai_client.usage_stats.update(50, 75)

    stats = openai_client.get_usage_stats()

    assert stats["prompt_tokens"] == 50
    assert stats["completion_tokens"] == 75
    assert stats["total_tokens"] == 125


def test_get_circuit_breaker_state(openai_client):
    """Test getting circuit breaker state."""
    state = openai_client.get_circuit_breaker_state()
    assert state == "closed"


def test_get_circuit_breaker_state_disabled():
    """Test getting circuit breaker state when disabled."""
    client = OpenAIClient(api_key=TEST_API_KEY, enable_circuit_breaker=False)
    state = client.get_circuit_breaker_state()
    assert state is None
