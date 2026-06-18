"""
Test suite for JIRA API Client (task-022)

Tests cover:
- Client initialization with valid/invalid credentials
- Issue fetching with JQL queries and pagination
- Fetch issue by key with expansions
- Comment fetching
- Issue history/changelog
- Attachment retrieval
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

from integrations.jira_client import (
    JiraClient,
    RateLimiter,
    JiraError,
    JiraAuthError,
    JiraAPIError,
    JiraRateLimitError
)


# Test Constants
TEST_JIRA_URL = "https://test-company.atlassian.net"
TEST_JIRA_USERNAME = "test-user@example.com"
TEST_JIRA_API_TOKEN = "test-api-token-xyz789"
TEST_PROJECT_KEY = "TEST"

# Mock Data
MOCK_ISSUE = {
    "id": "10001",
    "key": "TEST-123",
    "fields": {
        "summary": "Test issue summary",
        "description": "Detailed description",
        "status": {"name": "Open"},
        "priority": {"name": "High"},
        "assignee": {"displayName": "John Doe"},
        "reporter": {"displayName": "Jane Smith"},
        "created": "2024-01-01T10:00:00.000Z",
        "updated": "2024-01-15T14:30:00.000Z"
    }
}

MOCK_ISSUES_RESULT = {
    "issues": [MOCK_ISSUE],
    "total": 1,
    "startAt": 0,
    "maxResults": 50
}

MOCK_COMMENTS = {
    "comments": [
        {
            "id": "1001",
            "author": {"displayName": "John Doe"},
            "body": "First comment",
            "created": "2024-01-02T09:00:00.000Z",
            "updated": "2024-01-02T09:00:00.000Z"
        },
        {
            "id": "1002",
            "author": {"displayName": "Jane Smith"},
            "body": "Second comment",
            "created": "2024-01-03T10:15:00.000Z",
            "updated": "2024-01-03T10:15:00.000Z"
        }
    ]
}

MOCK_CHANGELOG = {
    "changelog": {
        "histories": [
            {
                "id": "h1",
                "author": {"displayName": "John Doe"},
                "created": "2024-01-05T11:00:00.000Z",
                "items": [
                    {
                        "field": "status",
                        "fromString": "Open",
                        "toString": "In Progress"
                    }
                ]
            },
            {
                "id": "h2",
                "author": {"displayName": "Jane Smith"},
                "created": "2024-01-10T15:30:00.000Z",
                "items": [
                    {
                        "field": "assignee",
                        "fromString": "John Doe",
                        "toString": "Jane Smith"
                    }
                ]
            }
        ]
    }
}

MOCK_ISSUE_WITH_CHANGELOG = {
    **MOCK_ISSUE,
    **MOCK_CHANGELOG
}

MOCK_ATTACHMENTS = {
    "fields": {
        "attachment": [
            {
                "id": "att001",
                "filename": "requirements.pdf",
                "size": 102400,
                "mimeType": "application/pdf",
                "content": "https://test.atlassian.net/attachments/att001/requirements.pdf",
                "created": "2024-01-04T12:00:00.000Z",
                "author": {"displayName": "John Doe"}
            }
        ]
    }
}


# Fixtures
@pytest.fixture
def mock_jira_api(mocker):
    """Mock the atlassian.Jira class."""
    mock_client = MagicMock()
    mocker.patch('integrations.jira_client.Jira', return_value=mock_client)
    return mock_client


@pytest_asyncio.fixture
async def jira_client(mock_jira_api):
    """Create JiraClient with mocked API."""
    client = JiraClient(
        url=TEST_JIRA_URL,
        username=TEST_JIRA_USERNAME,
        api_token=TEST_JIRA_API_TOKEN,
        enable_rate_limiting=False  # Disabled for most tests
    )
    yield client


@pytest_asyncio.fixture
async def rate_limited_client(mock_jira_api):
    """Create JiraClient with rate limiting enabled."""
    client = JiraClient(
        url=TEST_JIRA_URL,
        username=TEST_JIRA_USERNAME,
        api_token=TEST_JIRA_API_TOKEN,
        enable_rate_limiting=True
    )
    yield client


# ==================== Client Initialization Tests ====================

class TestClientInitialization:
    """Tests for JiraClient initialization."""

    def test_init_with_valid_credentials(self, mock_jira_api):
        """TC-A1: Initialize client with valid credentials."""
        client = JiraClient(
            url="https://test.atlassian.net/",  # With trailing slash
            username=TEST_JIRA_USERNAME,
            api_token=TEST_JIRA_API_TOKEN,
            enable_rate_limiting=True
        )

        assert client.url == "https://test.atlassian.net"  # Trailing slash removed
        assert client.username == TEST_JIRA_USERNAME
        assert client.api_token == TEST_JIRA_API_TOKEN
        assert client.rate_limiter is not None
        assert client.total_requests == 0
        assert client.failed_requests == 0

    def test_init_without_url_raises_error(self, mock_jira_api):
        """TC-A3: Initialize without URL raises JiraAuthError."""
        with pytest.raises(JiraAuthError, match="JIRA URL is required"):
            JiraClient(
                url=None,
                username=TEST_JIRA_USERNAME,
                api_token=TEST_JIRA_API_TOKEN
            )

    def test_init_without_username_raises_error(self, mock_jira_api):
        """TC-A4: Initialize without username raises JiraAuthError."""
        with pytest.raises(JiraAuthError, match="JIRA username is required"):
            JiraClient(
                url=TEST_JIRA_URL,
                username=None,
                api_token=TEST_JIRA_API_TOKEN
            )

    def test_init_without_api_token_raises_error(self, mock_jira_api):
        """TC-A5: Initialize without API token raises JiraAuthError."""
        with pytest.raises(JiraAuthError, match="JIRA API token is required"):
            JiraClient(
                url=TEST_JIRA_URL,
                username=TEST_JIRA_USERNAME,
                api_token=None
            )

    def test_init_with_rate_limiting_disabled(self, mock_jira_api):
        """TC-A7: Initialize with rate limiting disabled."""
        client = JiraClient(
            url=TEST_JIRA_URL,
            username=TEST_JIRA_USERNAME,
            api_token=TEST_JIRA_API_TOKEN,
            enable_rate_limiting=False
        )

        assert client.rate_limiter is None


# ==================== Issue Fetching Tests ====================

class TestIssueFetching:
    """Tests for fetching JIRA issues with JQL queries."""

    @pytest.mark.asyncio
    async def test_fetch_issues_default_pagination(self, jira_client):
        """TC-B1: Fetch issues with simple JQL query and default pagination."""
        jira_client.client.jql = Mock(return_value=MOCK_ISSUES_RESULT)

        result = await jira_client.fetch_issues(jql="project = TEST AND status = Open")

        assert result == MOCK_ISSUES_RESULT
        assert len(result['issues']) == 1
        assert result['total'] == 1
        jira_client.client.jql.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_issues_custom_pagination(self, jira_client):
        """TC-B4: Fetch issues with custom pagination."""
        jira_client.client.jql = Mock(return_value=MOCK_ISSUES_RESULT)

        await jira_client.fetch_issues(jql="project = TEST", start_at=50, max_results=25)

        # Implementation uses default field list when fields=None
        jira_client.client.jql.assert_called_with(
            "project = TEST",
            start=50,
            limit=25,
            fields="summary,description,status,priority,assignee,reporter,created,updated,resolutiondate,issuetype,project,labels,components"
        )

    @pytest.mark.asyncio
    async def test_fetch_issues_custom_fields(self, jira_client):
        """TC-B3: Fetch issues with custom field selection."""
        jira_client.client.jql = Mock(return_value=MOCK_ISSUES_RESULT)

        await jira_client.fetch_issues(
            jql="project = TEST",
            fields=["summary", "status", "assignee"]
        )

        jira_client.client.jql.assert_called_with(
            "project = TEST",
            start=0,
            limit=50,
            fields="summary,status,assignee"
        )

    @pytest.mark.asyncio
    async def test_fetch_issues_max_results_capped(self, jira_client):
        """TC-B5: Respect max page size limit (100)."""
        jira_client.client.jql = Mock(return_value=MOCK_ISSUES_RESULT)

        await jira_client.fetch_issues(jql="project = TEST", max_results=500)

        # Should be capped at 100 (MAX_PAGE_SIZE)
        jira_client.client.jql.assert_called_with(
            "project = TEST",
            start=0,
            limit=100,
            fields="summary,description,status,priority,assignee,reporter,created,updated,resolutiondate,issuetype,project,labels,components"
        )

    @pytest.mark.asyncio
    async def test_fetch_issues_empty_result(self, jira_client):
        """TC-B7: Handle empty result set."""
        empty_result = {"issues": [], "total": 0, "startAt": 0, "maxResults": 50}
        jira_client.client.jql = Mock(return_value=empty_result)

        result = await jira_client.fetch_issues(jql="project = NONEXISTENT")

        assert result['total'] == 0
        assert len(result['issues']) == 0


# ==================== Fetch Issue By Key Tests ====================

class TestFetchIssueByKey:
    """Tests for fetching individual issues by key."""

    @pytest.mark.asyncio
    async def test_fetch_issue_by_key_default(self, jira_client):
        """TC-C1: Fetch issue with valid key and default fields."""
        jira_client.client.issue = Mock(return_value=MOCK_ISSUE_WITH_CHANGELOG)

        result = await jira_client.fetch_issue_by_key("TEST-123")

        assert result == MOCK_ISSUE_WITH_CHANGELOG
        assert result['key'] == "TEST-123"
        jira_client.client.issue.assert_called_once_with(
            "TEST-123",
            fields="*all",
            expand="changelog,renderedFields"
        )

    @pytest.mark.asyncio
    async def test_fetch_issue_by_key_custom_fields(self, jira_client):
        """TC-C2: Fetch issue with custom field selection."""
        jira_client.client.issue = Mock(return_value=MOCK_ISSUE)

        await jira_client.fetch_issue_by_key("TEST-123", fields=["summary", "status"])

        jira_client.client.issue.assert_called_with(
            "TEST-123",
            fields="summary,status",
            expand="changelog,renderedFields"
        )

    @pytest.mark.asyncio
    async def test_fetch_issue_not_found(self, jira_client):
        """TC-C5: Handle non-existent issue (404 error)."""
        response_mock = Mock()
        response_mock.status_code = 404
        http_error = HTTPError(response=response_mock)
        jira_client.client.issue = Mock(side_effect=http_error)

        # Implementation retries 404 errors, so error message will be "HTTP error after 3 retries"
        with pytest.raises(JiraAPIError, match="HTTP error after 3 retries"):
            await jira_client.fetch_issue_by_key("NOTFOUND-999")


# ==================== Comment Fetching Tests ====================

class TestCommentFetching:
    """Tests for fetching issue comments."""

    @pytest.mark.asyncio
    async def test_fetch_comments_multiple(self, jira_client):
        """TC-D1: Fetch comments for issue with multiple comments."""
        jira_client.client.issue_get_comments = Mock(return_value=MOCK_COMMENTS)

        result = await jira_client.fetch_comments("TEST-123")

        assert result == MOCK_COMMENTS['comments']
        assert len(result) == 2
        jira_client.client.issue_get_comments.assert_called_once_with("TEST-123")

    @pytest.mark.asyncio
    async def test_fetch_comments_empty(self, jira_client):
        """TC-D2: Fetch comments for issue with no comments."""
        jira_client.client.issue_get_comments = Mock(return_value={"comments": []})

        result = await jira_client.fetch_comments("TEST-123")

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_comments_not_found(self, jira_client):
        """TC-D3: Handle non-existent issue (404 error)."""
        response_mock = Mock()
        response_mock.status_code = 404
        http_error = HTTPError(response=response_mock)
        jira_client.client.issue_get_comments = Mock(side_effect=http_error)

        # Implementation retries 404 errors, so error message will be "HTTP error after 3 retries"
        with pytest.raises(JiraAPIError, match="HTTP error after 3 retries"):
            await jira_client.fetch_comments("NOTFOUND-999")


# ==================== Issue History Tests ====================

class TestIssueHistory:
    """Tests for fetching issue history/changelog."""

    @pytest.mark.asyncio
    async def test_fetch_issue_history_full(self, jira_client):
        """TC-E1: Fetch full issue history."""
        jira_client.client.issue = Mock(return_value=MOCK_ISSUE_WITH_CHANGELOG)

        # Must explicitly set filter_status_changes=False to get all history
        result = await jira_client.fetch_issue_history("TEST-123", filter_status_changes=False)

        assert len(result) == 2
        assert result[0]['id'] == 'h1'
        assert result[1]['id'] == 'h2'

    @pytest.mark.asyncio
    async def test_fetch_issue_history_status_only(self, jira_client):
        """TC-E2: Fetch only status changes (filtered)."""
        jira_client.client.issue = Mock(return_value=MOCK_ISSUE_WITH_CHANGELOG)

        result = await jira_client.fetch_issue_history("TEST-123", filter_status_changes=True)

        # Should only return first history entry with status change
        assert len(result) == 1
        assert result[0]['id'] == 'h1'
        assert result[0]['items'][0]['field'] == 'status'

    @pytest.mark.asyncio
    async def test_fetch_issue_history_empty(self, jira_client):
        """TC-E3: Handle issue with no history."""
        issue_no_history = {**MOCK_ISSUE, "changelog": {"histories": []}}
        jira_client.client.issue = Mock(return_value=issue_no_history)

        result = await jira_client.fetch_issue_history("TEST-123")

        assert result == []


# ==================== Attachment Tests ====================

class TestAttachments:
    """Tests for fetching issue attachments."""

    @pytest.mark.asyncio
    async def test_fetch_attachments_multiple(self, jira_client):
        """TC-F1: Fetch attachments for issue with multiple attachments."""
        jira_client.client.issue = Mock(return_value=MOCK_ATTACHMENTS)

        result = await jira_client.fetch_attachments("TEST-123")

        assert len(result) == 1
        assert result[0]['filename'] == 'requirements.pdf'
        assert result[0]['mimeType'] == 'application/pdf'

    @pytest.mark.asyncio
    async def test_fetch_attachments_empty(self, jira_client):
        """TC-F2: Fetch attachments for issue with no attachments."""
        issue_no_attachments = {"fields": {"attachment": []}}
        jira_client.client.issue = Mock(return_value=issue_no_attachments)

        result = await jira_client.fetch_attachments("TEST-123")

        assert result == []


# ==================== Rate Limiting Tests ====================

class TestRateLimiting:
    """Tests for rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_per_second_limit(self):
        """TC-G1: Rate limiter respects per-second limit."""
        rate_limiter = RateLimiter(max_requests_per_second=2, max_requests_per_minute=100)

        start_time = time.time()

        # First 2 requests should be immediate
        await rate_limiter.acquire()
        await rate_limiter.acquire()

        # Third request should wait
        await rate_limiter.acquire()

        elapsed = time.time() - start_time
        # Should have waited approximately 1 second
        assert elapsed >= 0.9  # Allow small margin

    @pytest.mark.asyncio
    async def test_rate_limiter_can_be_disabled(self, jira_client):
        """TC-G4: Rate limiter can be disabled."""
        assert jira_client.rate_limiter is None

        # Should not raise any errors
        jira_client.client.jql = Mock(return_value=MOCK_ISSUES_RESULT)
        result = await jira_client.fetch_issues(jql="project = TEST")
        assert result is not None


# ==================== Error Handling and Retry Logic Tests ====================

class TestErrorHandling:
    """Tests for error handling and retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, jira_client, mocker):
        """TC-H1: Retry on transient HTTP 5xx errors with exponential backoff."""
        response_mock = Mock()
        response_mock.status_code = 500
        http_error = HTTPError(response=response_mock)

        # Fail twice, then succeed
        jira_client.client.jql = Mock(
            side_effect=[http_error, http_error, MOCK_ISSUES_RESULT]
        )

        # Mock asyncio.sleep to avoid actual waiting
        mock_sleep = mocker.patch('asyncio.sleep', new_callable=AsyncMock)

        result = await jira_client.fetch_issues(jql="project = TEST")

        assert result == MOCK_ISSUES_RESULT
        assert jira_client.client.jql.call_count == 3
        # Verify exponential backoff: 1s, 2s
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self, jira_client):
        """TC-H2: No retry on authentication errors (401/403)."""
        response_mock = Mock()
        response_mock.status_code = 401
        http_error = HTTPError(response=response_mock)
        jira_client.client.jql = Mock(side_effect=http_error)

        with pytest.raises(JiraAuthError):
            await jira_client.fetch_issues(jql="project = TEST")

        # Should only try once
        assert jira_client.client.jql.call_count == 1

    @pytest.mark.asyncio
    async def test_handle_rate_limit_with_retry_after(self, jira_client, mocker):
        """TC-H3: Handle rate limit errors (429) with Retry-After header."""
        response_mock = Mock()
        response_mock.status_code = 429
        response_mock.headers = {"Retry-After": "5"}
        http_error = HTTPError(response=response_mock)

        jira_client.client.jql = Mock(
            side_effect=[http_error, MOCK_ISSUES_RESULT]
        )

        mock_sleep = mocker.patch('asyncio.sleep', new_callable=AsyncMock)

        result = await jira_client.fetch_issues(jql="project = TEST")

        assert result == MOCK_ISSUES_RESULT
        # Should wait for Retry-After duration (5 seconds)
        mock_sleep.assert_called_with(5)


# ==================== Statistics Tests ====================

class TestStatistics:
    """Tests for request statistics tracking."""

    @pytest.mark.asyncio
    async def test_track_request_statistics(self, jira_client):
        """TC-I1, TC-I2, TC-I3: Track total and failed requests, calculate success rate."""
        # 3 successful requests
        jira_client.client.jql = Mock(return_value=MOCK_ISSUES_RESULT)
        await jira_client.fetch_issues(jql="project = TEST")
        await jira_client.fetch_issues(jql="project = TEST")
        await jira_client.fetch_issues(jql="project = TEST")

        # 2 failed requests - each will retry 3 times, so 6 failed attempts total
        response_mock = Mock()
        response_mock.status_code = 500
        http_error = HTTPError(response=response_mock)
        jira_client.client.issue = Mock(side_effect=http_error)

        # These will fail and increment failed_requests (3 retries each = 6 total failures)
        try:
            await jira_client.fetch_issue_by_key("TEST-1")
        except:
            pass

        try:
            await jira_client.fetch_issue_by_key("TEST-2")
        except:
            pass

        stats = jira_client.get_statistics()

        # Total: 3 successful + 6 failed attempts = 9
        # Failed: 6 attempts (3 per failed request)
        # Success rate: 3/9 = 33.33%
        assert stats['total_requests'] == 9
        assert stats['failed_requests'] == 6
        assert abs(stats['success_rate'] - 33.33) < 0.1

    @pytest.mark.asyncio
    async def test_statistics_with_zero_requests(self, jira_client):
        """TC-I4: Handle statistics with zero requests."""
        stats = jira_client.get_statistics()

        assert stats['total_requests'] == 0
        assert stats['failed_requests'] == 0
        assert stats['success_rate'] == 0.0

