"""
Test suite for Confluence API Client (task-021)

Tests cover:
- Client initialization with valid/invalid credentials
- Space fetching with pagination
- Page fetching with content expansion
- Attachment retrieval
- Page history
- Rate limiting
- Retry logic with exponential backoff
- Error handling (auth, rate limit, API errors)
- Statistics tracking
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from requests.exceptions import HTTPError, RequestException
import asyncio
import time

from integrations.confluence_client import (
    ConfluenceClient,
    RateLimiter,
    ConfluenceError,
    ConfluenceAuthError,
    ConfluenceAPIError,
    ConfluenceRateLimitError
)


# Test Constants
TEST_CONFLUENCE_URL = "https://test.atlassian.net"
TEST_CONFLUENCE_USERNAME = "test@example.com"
TEST_CONFLUENCE_API_TOKEN = "test-api-token-abcd1234"
TEST_SPACE_KEY = "TEST"
TEST_PAGE_ID = "12345"

# Mock Data
MOCK_SPACES = {
    "results": [
        {"id": 1, "key": "DOCS", "name": "Documentation", "type": "global"},
        {"id": 2, "key": "TEAM", "name": "Team Space", "type": "global"}
    ],
    "start": 0,
    "limit": 50,
    "size": 2
}

MOCK_PAGES = {
    "results": [
        {
            "id": "12345",
            "title": "Getting Started",
            "type": "page",
            "body": {
                "storage": {
                    "value": "<h1>Getting Started</h1><p>Welcome</p>",
                    "representation": "storage"
                }
            },
            "version": {"number": 5}
        }
    ],
    "start": 0,
    "limit": 50,
    "size": 1
}

MOCK_PAGE_FULL = {
    "id": "12345",
    "title": "Test Page",
    "type": "page",
    "body": {
        "storage": {
            "value": "<h1>Test</h1><p>Content here</p>",
            "representation": "storage"
        },
        "view": {
            "value": "<div>Rendered HTML</div>",
            "representation": "view"
        }
    },
    "version": {"number": 3},
    "history": {"latest": True}
}

MOCK_ATTACHMENTS = {
    "results": [
        {
            "id": "att123",
            "title": "document.pdf",
            "type": "attachment",
            "metadata": {"mediaType": "application/pdf"},
            "_links": {"download": "/download/attachments/12345/document.pdf"}
        }
    ],
    "start": 0,
    "limit": 50,
    "size": 1
}

MOCK_HISTORY = {
    "lastUpdated": {
        "by": {"displayName": "Editor"},
        "when": "2024-01-15T14:20:00.000Z"
    },
    "latestVersion": {"number": 3}
}


# Fixtures
@pytest.fixture
def mock_confluence_api(mocker):
    """Mock the atlassian.Confluence class."""
    mock_client = MagicMock()
    mocker.patch('integrations.confluence_client.Confluence', return_value=mock_client)
    return mock_client


@pytest_asyncio.fixture
async def confluence_client(mock_confluence_api):
    """Create ConfluenceClient with mocked API."""
    client = ConfluenceClient(
        url=TEST_CONFLUENCE_URL,
        username=TEST_CONFLUENCE_USERNAME,
        api_token=TEST_CONFLUENCE_API_TOKEN,
        enable_rate_limiting=False  # Disabled for most tests
    )
    yield client


@pytest_asyncio.fixture
async def rate_limited_client(mock_confluence_api):
    """Create ConfluenceClient with rate limiting enabled."""
    client = ConfluenceClient(
        url=TEST_CONFLUENCE_URL,
        username=TEST_CONFLUENCE_USERNAME,
        api_token=TEST_CONFLUENCE_API_TOKEN,
        enable_rate_limiting=True
    )
    yield client


# ==================== Client Initialization Tests ====================

class TestClientInitialization:
    """Tests for ConfluenceClient initialization."""

    def test_init_with_valid_credentials(self, mock_confluence_api):
        """TC-001: Initialize client with valid credentials."""
        client = ConfluenceClient(
            url="https://test.atlassian.net/",  # With trailing slash
            username=TEST_CONFLUENCE_USERNAME,
            api_token=TEST_CONFLUENCE_API_TOKEN,
            enable_rate_limiting=True
        )

        assert client.url == "https://test.atlassian.net"  # Trailing slash removed
        assert client.username == TEST_CONFLUENCE_USERNAME
        assert client.api_token == TEST_CONFLUENCE_API_TOKEN
        assert client.rate_limiter is not None
        assert client.total_requests == 0
        assert client.failed_requests == 0

    def test_init_without_url_raises_error(self, mock_confluence_api):
        """TC-002: Initialize without URL raises ConfluenceAuthError."""
        with pytest.raises(ConfluenceAuthError, match="Confluence URL not provided"):
            ConfluenceClient(
                url="",
                username=TEST_CONFLUENCE_USERNAME,
                api_token=TEST_CONFLUENCE_API_TOKEN
            )

    def test_init_without_username_raises_error(self, mock_confluence_api):
        """TC-002: Initialize without username raises ConfluenceAuthError."""
        with pytest.raises(ConfluenceAuthError, match="Confluence username not provided"):
            ConfluenceClient(
                url=TEST_CONFLUENCE_URL,
                username="",
                api_token=TEST_CONFLUENCE_API_TOKEN
            )

    def test_init_without_api_token_raises_error(self, mock_confluence_api):
        """TC-002: Initialize without API token raises ConfluenceAuthError."""
        with pytest.raises(ConfluenceAuthError, match="Confluence API token not provided"):
            ConfluenceClient(
                url=TEST_CONFLUENCE_URL,
                username=TEST_CONFLUENCE_USERNAME,
                api_token=""
            )

    def test_init_with_rate_limiting_disabled(self, mock_confluence_api):
        """TC-003: Initialize with rate limiting disabled."""
        client = ConfluenceClient(
            url=TEST_CONFLUENCE_URL,
            username=TEST_CONFLUENCE_USERNAME,
            api_token=TEST_CONFLUENCE_API_TOKEN,
            enable_rate_limiting=False
        )

        assert client.rate_limiter is None


# ==================== Space Fetching Tests ====================

class TestSpaceFetching:
    """Tests for fetching Confluence spaces."""

    @pytest.mark.asyncio
    async def test_fetch_spaces_default_pagination(self, confluence_client):
        """TC-004: Fetch spaces with default pagination."""
        confluence_client.client.get_all_spaces = Mock(return_value=MOCK_SPACES)

        result = await confluence_client.fetch_spaces()

        assert result == MOCK_SPACES
        assert len(result['results']) == 2
        confluence_client.client.get_all_spaces.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_spaces_custom_pagination(self, confluence_client):
        """TC-005: Fetch spaces with custom pagination."""
        confluence_client.client.get_all_spaces = Mock(return_value=MOCK_SPACES)

        await confluence_client.fetch_spaces(start=10, limit=25)

        confluence_client.client.get_all_spaces.assert_called_with(
            start=10,
            limit=25,
            space_type=None
        )

    @pytest.mark.asyncio
    async def test_fetch_spaces_with_type_filter(self, confluence_client):
        """TC-006: Fetch spaces filtered by type."""
        confluence_client.client.get_all_spaces = Mock(return_value=MOCK_SPACES)

        await confluence_client.fetch_spaces(space_type='global')

        confluence_client.client.get_all_spaces.assert_called_with(
            start=0,
            limit=50,
            space_type='global'
        )

    @pytest.mark.asyncio
    async def test_fetch_spaces_limit_capped(self, confluence_client):
        """TC-007: Fetch spaces with limit exceeding MAX_PAGE_LIMIT."""
        confluence_client.client.get_all_spaces = Mock(return_value=MOCK_SPACES)

        await confluence_client.fetch_spaces(limit=150)

        # Should be capped at 100
        confluence_client.client.get_all_spaces.assert_called_with(
            start=0,
            limit=100,
            space_type=None
        )


# ==================== Page Fetching Tests ====================

class TestPageFetching:
    """Tests for fetching Confluence pages."""

    @pytest.mark.asyncio
    async def test_fetch_pages_default_expansion(self, confluence_client):
        """TC-008: Fetch pages from space with default expansion."""
        confluence_client.client.get_all_pages_from_space = Mock(return_value=MOCK_PAGES)

        result = await confluence_client.fetch_pages(space_key=TEST_SPACE_KEY)

        assert result == MOCK_PAGES
        confluence_client.client.get_all_pages_from_space.assert_called_once()
        call_args = confluence_client.client.get_all_pages_from_space.call_args
        assert 'body.storage' in call_args[1]['expand']
        assert 'version' in call_args[1]['expand']

    @pytest.mark.asyncio
    async def test_fetch_page_by_id(self, confluence_client):
        """TC-009: Fetch page by ID with HTML content."""
        confluence_client.client.get_page_by_id = Mock(return_value=MOCK_PAGE_FULL)

        result = await confluence_client.fetch_page_by_id(page_id=TEST_PAGE_ID)

        assert result == MOCK_PAGE_FULL
        assert result['body']['storage']['value'] is not None
        confluence_client.client.get_page_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_pages_from_space_pagination(self, confluence_client, mocker):
        """TC-010: Get all pages from space with auto-pagination."""
        # Mock fetch_pages since get_all_pages_from_space calls it internally
        # Simulate pagination: Implementation uses DEFAULT_PAGE_LIMIT=50
        # First batch: size == limit indicates there might be more pages
        first_batch = {
            "results": [{"id": str(i)} for i in range(1, 51)],  # 50 pages
            "start": 0,
            "limit": 50,  # DEFAULT_PAGE_LIMIT
            "size": 50    # size == limit means more pages may exist
        }
        # Second batch: size < limit indicates this is the last batch
        second_batch = {
            "results": [{"id": str(i)} for i in range(51, 76)],  # 25 more pages
            "start": 50,
            "limit": 50,  # DEFAULT_PAGE_LIMIT
            "size": 25    # size < limit means no more pages
        }

        # Mock the fetch_pages method which is called internally
        mock_fetch = mocker.patch.object(
            confluence_client,
            'fetch_pages',
            side_effect=[first_batch, second_batch]
        )

        result = await confluence_client.get_all_pages_from_space(space_key=TEST_SPACE_KEY)

        # Should get all 75 pages (50 + 25)
        assert len(result) == 75
        assert result[0]['id'] == "1"
        assert result[49]['id'] == "50"
        assert result[74]['id'] == "75"
        assert mock_fetch.call_count == 2


# ==================== Attachment Tests ====================

class TestAttachments:
    """Tests for fetching attachments."""

    @pytest.mark.asyncio
    async def test_fetch_attachments(self, confluence_client):
        """TC-011: Fetch attachments for a page."""
        confluence_client.client.get_attachments_from_content = Mock(return_value=MOCK_ATTACHMENTS)

        result = await confluence_client.fetch_attachments(page_id=TEST_PAGE_ID)

        assert result == MOCK_ATTACHMENTS
        assert len(result['results']) == 1
        assert result['results'][0]['title'] == "document.pdf"

    @pytest.mark.asyncio
    async def test_fetch_attachments_with_filename_filter(self, confluence_client):
        """TC-012: Fetch attachments with filename filter."""
        confluence_client.client.get_attachments_from_content = Mock(return_value=MOCK_ATTACHMENTS)

        await confluence_client.fetch_attachments(page_id=TEST_PAGE_ID, filename="report.pdf")

        confluence_client.client.get_attachments_from_content.assert_called_with(
            page_id=TEST_PAGE_ID,
            start=0,
            limit=50,
            filename="report.pdf"
        )


# ==================== Page History Tests ====================

class TestPageHistory:
    """Tests for fetching page history."""

    @pytest.mark.asyncio
    async def test_fetch_page_history(self, confluence_client):
        """TC-013: Fetch page version history."""
        confluence_client.client.history = Mock(return_value=MOCK_HISTORY)

        result = await confluence_client.fetch_page_history(page_id=TEST_PAGE_ID)

        assert result == MOCK_HISTORY
        assert result['latestVersion']['number'] == 3
        confluence_client.client.history.assert_called_once_with(TEST_PAGE_ID)



# ==================== Rate Limiting Tests ====================

class TestRateLimiting:
    """Tests for rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_per_second_limit(self):
        """TC-014: Rate limiter enforces per-second limit."""
        limiter = RateLimiter(max_requests_per_second=2, max_requests_per_minute=100)

        start = time.time()
        await limiter.acquire()  # 1st request
        await limiter.acquire()  # 2nd request
        await limiter.acquire()  # 3rd request - should wait
        elapsed = time.time() - start

        # Third request should wait ~1 second
        assert elapsed >= 0.9, f"Expected ~1s wait, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_within_limit(self):
        """TC-014: Rate limiter allows requests within limit."""
        limiter = RateLimiter(max_requests_per_second=5, max_requests_per_minute=100)

        start = time.time()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should complete quickly
        assert elapsed < 0.5, f"Should be fast, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_client_with_rate_limiting_enabled(self, rate_limited_client):
        """TC-016: Client respects rate limits during API calls."""
        rate_limited_client.client.get_all_spaces = Mock(return_value=MOCK_SPACES)

        # Make multiple calls
        await rate_limited_client.fetch_spaces()
        await rate_limited_client.fetch_spaces()

        # Should complete without errors (rate limiter throttles)
        assert rate_limited_client.client.get_all_spaces.call_count == 2


# ==================== Error Handling and Retry Tests ====================

class TestErrorHandling:
    """Tests for error handling and retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, confluence_client, mocker):
        """TC-017: Retry on transient HTTP 500 error."""
        mock_sleep = mocker.patch('asyncio.sleep')

        # Create proper HTTPError with response
        error_response = Mock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        http_error = HTTPError()
        http_error.response = error_response

        # Fail twice, then succeed
        confluence_client.client.get_all_spaces = Mock(
            side_effect=[http_error, http_error, MOCK_SPACES]
        )

        result = await confluence_client.fetch_spaces()

        assert result == MOCK_SPACES
        assert confluence_client.client.get_all_spaces.call_count == 3
        # Verify exponential backoff: 1s, 2s
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_fast_fail_on_401_auth_error(self, confluence_client):
        """TC-018: Fast-fail on authentication error (401)."""
        error_response = Mock()
        error_response.status_code = 401
        error_response.text = "Unauthorized"
        http_error = HTTPError()
        http_error.response = error_response

        confluence_client.client.get_all_spaces = Mock(side_effect=http_error)

        with pytest.raises(ConfluenceAuthError):
            await confluence_client.fetch_spaces()

        # Should only call once (no retries)
        assert confluence_client.client.get_all_spaces.call_count == 1

    @pytest.mark.asyncio
    async def test_fast_fail_on_403_forbidden_error(self, confluence_client):
        """TC-018: Fast-fail on forbidden error (403)."""
        error_response = Mock()
        error_response.status_code = 403
        error_response.text = "Forbidden"
        http_error = HTTPError()
        http_error.response = error_response

        confluence_client.client.get_all_spaces = Mock(side_effect=http_error)

        with pytest.raises(ConfluenceAuthError):
            await confluence_client.fetch_spaces()

        # Should only call once (no retries)
        assert confluence_client.client.get_all_spaces.call_count == 1

    @pytest.mark.asyncio
    async def test_handle_429_rate_limit(self, confluence_client, mocker):
        """TC-019: Handle 429 rate limit with Retry-After header."""
        mock_sleep = mocker.patch('asyncio.sleep')

        error_response = Mock()
        error_response.status_code = 429
        error_response.text = "Too Many Requests"
        error_response.headers = {"Retry-After": "5"}
        http_error = HTTPError()
        http_error.response = error_response

        # Fail once with 429, then succeed
        confluence_client.client.get_all_spaces = Mock(
            side_effect=[http_error, MOCK_SPACES]
        )

        result = await confluence_client.fetch_spaces()

        assert result == MOCK_SPACES
        # Should wait for Retry-After duration (5 seconds)
        mock_sleep.assert_called_with(5)

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, confluence_client, mocker):
        """TC-020: Max retries exhausted raises ConfluenceAPIError."""
        mock_sleep = mocker.patch('asyncio.sleep')

        error_response = Mock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        http_error = HTTPError()
        http_error.response = error_response

        # Always fail
        confluence_client.client.get_all_spaces = Mock(side_effect=http_error)

        with pytest.raises(ConfluenceAPIError, match="Failed after 3 retries"):
            await confluence_client.fetch_spaces()

        # Should attempt 3 times (MAX_RETRIES)
        assert confluence_client.client.get_all_spaces.call_count == 3
        assert confluence_client.failed_requests == 3

    @pytest.mark.asyncio
    async def test_network_error_triggers_retry(self, confluence_client, mocker):
        """TC-021: Network error triggers retry."""
        mock_sleep = mocker.patch('asyncio.sleep')

        network_error = RequestException("Connection timeout")

        # Fail twice, then succeed
        confluence_client.client.get_all_spaces = Mock(
            side_effect=[network_error, network_error, MOCK_SPACES]
        )

        result = await confluence_client.fetch_spaces()

        assert result == MOCK_SPACES
        assert confluence_client.client.get_all_spaces.call_count == 3


# ==================== Connection Test Cases ====================

class TestConnection:
    """Tests for connection testing functionality."""

    @pytest.mark.asyncio
    async def test_connection_success(self, confluence_client):
        """TC-022: test_connection succeeds with valid credentials."""
        confluence_client.client.get_all_spaces = Mock(return_value=MOCK_SPACES)

        result = await confluence_client.test_connection()

        assert result is True
        confluence_client.client.get_all_spaces.assert_called_once_with(start=0, limit=1)

    @pytest.mark.asyncio
    async def test_connection_fails_on_auth_error(self, confluence_client):
        """TC-023: test_connection fails with invalid credentials."""
        error_response = Mock()
        error_response.status_code = 401
        http_error = HTTPError()
        http_error.response = error_response

        confluence_client.client.get_all_spaces = Mock(side_effect=http_error)

        result = await confluence_client.test_connection()

        assert result is False


# ==================== Statistics Tracking Tests ====================

class TestStatistics:
    """Tests for request statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_track_requests(self, confluence_client):
        """TC-024: Statistics track successful and failed requests."""
        confluence_client.client.get_all_spaces = Mock(return_value=MOCK_SPACES)

        # Make successful requests
        await confluence_client.fetch_spaces()
        await confluence_client.fetch_spaces()

        stats = confluence_client.get_stats()

        assert stats['total_requests'] == 2
        assert stats['failed_requests'] == 0
        assert stats['success_rate'] == 100.0

    @pytest.mark.asyncio
    async def test_stats_with_failures(self, confluence_client):
        """TC-024: Statistics track failed requests."""
        error_response = Mock()
        error_response.status_code = 500
        http_error = HTTPError()
        http_error.response = error_response

        # One success, then failure that repeats for all retry attempts
        # Need to provide enough error instances for initial + 3 retries
        confluence_client.client.get_all_spaces = Mock(
            side_effect=[MOCK_SPACES, http_error, http_error, http_error, http_error]
        )

        await confluence_client.fetch_spaces()

        try:
            await confluence_client.fetch_spaces()
        except ConfluenceAPIError:
            pass

        stats = confluence_client.get_stats()

        assert stats['total_requests'] == 1  # Only successful counted in total
        assert stats['failed_requests'] == 3  # 3 retries for the failed one

    def test_stats_zero_requests(self, confluence_client):
        """TC-025: get_stats handles zero requests."""
        stats = confluence_client.get_stats()

        assert stats['total_requests'] == 0
        assert stats['failed_requests'] == 0
        assert stats['success_rate'] == 0  # No division by zero error

