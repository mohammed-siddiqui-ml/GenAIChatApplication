"""
JIRA Client Integration

Provides a robust client wrapper for JIRA API with:
- Issue fetching with JQL query support and pagination
- Fetch issue details (description, comments, attachments)
- Issue history tracking for status changes
- Rate limiting and retry logic
- Error handling for authentication and API errors
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

from atlassian import Jira
import requests
from requests.exceptions import RequestException, HTTPError

from core.config import settings


# Logger
logger = logging.getLogger(__name__)


# Custom Exceptions
class JiraError(Exception):
    """Base exception for JIRA client errors."""
    pass


class JiraAuthError(JiraError):
    """Raised when authentication fails."""
    pass


class JiraAPIError(JiraError):
    """Raised when JIRA API returns an error."""
    pass


class JiraRateLimitError(JiraError):
    """Raised when rate limit is exceeded."""
    pass


@dataclass
class RateLimiter:
    """
    Rate limiter to respect JIRA API limits.

    JIRA Cloud typically allows:
    - 10 requests per second per user
    - 100 requests per minute per user
    """

    max_requests_per_second: int = 8  # Conservative limit
    max_requests_per_minute: int = 80  # Conservative limit

    def __init__(
        self,
        max_requests_per_second: int = 8,
        max_requests_per_minute: int = 80
    ):
        """Initialize rate limiter."""
        self.max_requests_per_second = max_requests_per_second
        self.max_requests_per_minute = max_requests_per_minute

        self.second_window: List[float] = []
        self.minute_window: List[float] = []

        logger.info(
            f"Rate limiter initialized: {max_requests_per_second} req/s, "
            f"{max_requests_per_minute} req/min"
        )

    async def acquire(self) -> None:
        """
        Wait if necessary to respect rate limits.

        Raises:
            JiraRateLimitError: If rate limit would be exceeded
        """
        current_time = time.time()

        # Clean up old entries
        self.second_window = [t for t in self.second_window if current_time - t < 1.0]
        self.minute_window = [t for t in self.minute_window if current_time - t < 60.0]

        # Check per-second limit
        if len(self.second_window) >= self.max_requests_per_second:
            wait_time = 1.0 - (current_time - self.second_window[0])
            if wait_time > 0:
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s (per-second)")
                await asyncio.sleep(wait_time)
                current_time = time.time()
                self.second_window = [t for t in self.second_window if current_time - t < 1.0]

        # Check per-minute limit
        if len(self.minute_window) >= self.max_requests_per_minute:
            wait_time = 60.0 - (current_time - self.minute_window[0])
            if wait_time > 0:
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s (per-minute)")
                await asyncio.sleep(wait_time)
                current_time = time.time()
                self.minute_window = [t for t in self.minute_window if current_time - t < 60.0]

        # Record this request
        self.second_window.append(current_time)
        self.minute_window.append(current_time)


class JiraClient:
    """
    Robust JIRA API client with pagination and rate limiting.

    Features:
    - Fetch issues with JQL queries and pagination
    - Fetch issue by key with full details
    - Fetch comments for issues
    - Fetch issue history for status changes
    - Fetch attachments
    - Rate limiting (8 req/s, 80 req/min)
    - Retry logic with exponential backoff
    - Error handling for auth and API errors
    """

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 10.0  # seconds

    # Pagination defaults
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 100

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        enable_rate_limiting: bool = True
    ):
        """
        Initialize JIRA client.

        Args:
            url: JIRA instance URL (e.g., https://yourcompany.atlassian.net)
            username: JIRA username (email for Cloud)
            api_token: JIRA API token
            enable_rate_limiting: Enable rate limiting

        Raises:
            JiraAuthError: If credentials are missing or invalid
        """
        # Use environment variables if not provided
        self.url = url or settings.JIRA_URL
        self.username = username or settings.JIRA_USERNAME
        self.api_token = api_token or settings.JIRA_API_TOKEN

        # Validate credentials
        if not self.url:
            raise JiraAuthError("JIRA URL is required")
        if not self.username:
            raise JiraAuthError("JIRA username is required")
        if not self.api_token:
            raise JiraAuthError("JIRA API token is required")

        # Remove trailing slash from URL
        self.url = self.url.rstrip('/')

        # Initialize JIRA client
        try:
            self.client = Jira(
                url=self.url,
                username=self.username,
                password=self.api_token,
                cloud=True  # Use JIRA Cloud API
            )
            logger.info(f"JIRA client initialized: {self.url}")
        except Exception as e:
            logger.error(f"Failed to initialize JIRA client: {e}")
            raise JiraAuthError(f"Failed to initialize client: {e}")

        # Rate limiter
        self.rate_limiter = RateLimiter() if enable_rate_limiting else None

        # Request statistics
        self.total_requests = 0
        self.failed_requests = 0

    async def _retry_with_backoff(self, func, *args, **kwargs) -> Any:
        """
        Execute function with exponential backoff retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            JiraError: If all retries fail
        """
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Apply rate limiting
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                # Track all attempts
                self.total_requests += 1

                # Execute function in thread pool (sync to async)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))

                return result

            except HTTPError as e:
                last_exception = e
                self.failed_requests += 1

                # Check for authentication errors
                if e.response.status_code in (401, 403):
                    logger.error(f"Authentication failed: {e}")
                    raise JiraAuthError(f"Authentication failed: {e}")

                # Check for rate limit errors
                if e.response.status_code == 429:
                    logger.warning(f"Rate limit exceeded (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    retry_after = int(e.response.headers.get('Retry-After', 60))

                    if attempt < self.MAX_RETRIES - 1:
                        logger.info(f"Retrying after {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise JiraRateLimitError(f"Rate limit exceeded: {e}")

                # Other HTTP errors - retry with backoff
                logger.warning(f"HTTP error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    delay = min(
                        self.BASE_RETRY_DELAY * (2 ** attempt),
                        self.MAX_RETRY_DELAY
                    )
                    logger.info(f"Retrying after {delay}s...")
                    await asyncio.sleep(delay)

            except RequestException as e:
                last_exception = e
                self.failed_requests += 1
                logger.warning(f"Request error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

                if attempt < self.MAX_RETRIES - 1:
                    delay = min(
                        self.BASE_RETRY_DELAY * (2 ** attempt),
                        self.MAX_RETRY_DELAY
                    )
                    await asyncio.sleep(delay)

            except Exception as e:
                last_exception = e
                self.failed_requests += 1
                logger.error(f"Unexpected error: {e}")
                raise JiraAPIError(f"Unexpected error: {e}")

        # All retries exhausted
        if isinstance(last_exception, HTTPError):
            raise JiraAPIError(f"HTTP error after {self.MAX_RETRIES} retries: {last_exception}")
        else:
            raise JiraError(f"Request failed after {self.MAX_RETRIES} retries: {last_exception}")

    async def fetch_issues(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        start_at: int = 0,
        max_results: int = 50,
        expand: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch issues using JQL query with pagination support.

        Args:
            jql: JQL query string (e.g., "project = PROJ AND status = Open")
            fields: List of fields to include (default: all fields)
            start_at: Index of the first issue to return (for pagination)
            max_results: Maximum number of issues to return (default: 50, max: 100)
            expand: List of entities to expand (e.g., ["changelog", "renderedFields"])

        Returns:
            Dictionary with:
                - issues: List of issue objects
                - total: Total number of matching issues
                - start_at: Index of first returned issue
                - max_results: Maximum results per page

        Raises:
            JiraAPIError: If API request fails
            JiraAuthError: If authentication fails
        """
        # Validate max_results
        max_results = min(max_results, self.MAX_PAGE_SIZE)

        # Default fields if not specified
        if fields is None:
            fields = [
                "summary", "description", "status", "priority", "assignee",
                "reporter", "created", "updated", "resolutiondate",
                "issuetype", "project", "labels", "components"
            ]

        logger.info(f"Fetching issues with JQL: {jql} (start_at={start_at}, max_results={max_results})")

        try:
            # Build search parameters
            search_params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": fields,
            }

            if expand:
                search_params["expand"] = expand

            # Execute search
            result = await self._retry_with_backoff(
                self.client.jql,
                jql,
                start=start_at,
                limit=max_results,
                fields=",".join(fields) if isinstance(fields, list) else fields
            )

            logger.info(
                f"Fetched {len(result.get('issues', []))} issues "
                f"(total: {result.get('total', 0)})"
            )

            return result

        except JiraAuthError:
            raise
        except JiraRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch issues: {e}")
            raise JiraAPIError(f"Failed to fetch issues: {e}")

    async def fetch_issue_by_key(
        self,
        issue_key: str,
        fields: Optional[List[str]] = None,
        expand: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch full details of a specific issue by its key.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")
            fields: List of fields to include (default: all fields)
            expand: List of entities to expand (e.g., ["changelog", "renderedFields"])

        Returns:
            Dictionary containing issue details including:
                - key: Issue key
                - fields: Issue fields (summary, description, status, etc.)
                - changelog: Issue history (if expanded)
                - renderedFields: Rendered HTML fields (if expanded)

        Raises:
            JiraAPIError: If issue not found or API request fails
            JiraAuthError: If authentication fails
        """
        logger.info(f"Fetching issue: {issue_key}")

        try:
            # Default expand to include changelog and rendered fields
            if expand is None:
                expand = ["changelog", "renderedFields"]

            # Execute issue fetch
            result = await self._retry_with_backoff(
                self.client.issue,
                issue_key,
                fields=",".join(fields) if fields and isinstance(fields, list) else "*all",
                expand=",".join(expand) if isinstance(expand, list) else expand
            )

            logger.info(f"Successfully fetched issue: {issue_key}")
            return result

        except HTTPError as e:
            if e.response.status_code == 404:
                raise JiraAPIError(f"Issue not found: {issue_key}")
            raise
        except JiraAuthError:
            raise
        except JiraRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch issue {issue_key}: {e}")
            raise JiraAPIError(f"Failed to fetch issue: {e}")

    async def fetch_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Fetch all comments for a specific issue.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")

        Returns:
            List of comment dictionaries containing:
                - id: Comment ID
                - author: Comment author details
                - body: Comment text
                - created: Creation timestamp
                - updated: Last update timestamp

        Raises:
            JiraAPIError: If API request fails
            JiraAuthError: If authentication fails
        """
        logger.info(f"Fetching comments for issue: {issue_key}")

        try:
            # Execute comments fetch
            result = await self._retry_with_backoff(
                self.client.issue_get_comments,
                issue_key
            )

            # Extract comments from result
            comments = result.get("comments", [])
            logger.info(f"Fetched {len(comments)} comments for issue: {issue_key}")

            return comments

        except HTTPError as e:
            if e.response.status_code == 404:
                raise JiraAPIError(f"Issue not found: {issue_key}")
            raise
        except JiraAuthError:
            raise
        except JiraRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch comments for {issue_key}: {e}")
            raise JiraAPIError(f"Failed to fetch comments: {e}")

    async def fetch_issue_history(
        self,
        issue_key: str,
        filter_status_changes: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch issue history, particularly status changes.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")
            filter_status_changes: If True, return only status changes

        Returns:
            List of history items containing:
                - id: Change ID
                - author: User who made the change
                - created: When the change was made
                - items: List of field changes (field, from, to)

        Raises:
            JiraAPIError: If API request fails
            JiraAuthError: If authentication fails
        """
        logger.info(f"Fetching history for issue: {issue_key}")

        try:
            # Fetch issue with changelog expansion
            result = await self._retry_with_backoff(
                self.client.issue,
                issue_key,
                expand="changelog"
            )

            # Extract changelog
            changelog = result.get("changelog", {})
            histories = changelog.get("histories", [])

            if filter_status_changes:
                # Filter to only status changes
                status_changes = []
                for history in histories:
                    # Check if this history entry contains status changes
                    status_items = [
                        item for item in history.get("items", [])
                        if item.get("field") == "status"
                    ]

                    if status_items:
                        status_changes.append({
                            "id": history.get("id"),
                            "author": history.get("author"),
                            "created": history.get("created"),
                            "items": status_items
                        })

                logger.info(
                    f"Fetched {len(status_changes)} status changes "
                    f"for issue: {issue_key}"
                )
                return status_changes
            else:
                logger.info(
                    f"Fetched {len(histories)} history entries "
                    f"for issue: {issue_key}"
                )
                return histories

        except HTTPError as e:
            if e.response.status_code == 404:
                raise JiraAPIError(f"Issue not found: {issue_key}")
            raise
        except JiraAuthError:
            raise
        except JiraRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch history for {issue_key}: {e}")
            raise JiraAPIError(f"Failed to fetch history: {e}")

    async def fetch_attachments(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Fetch attachments for a specific issue.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")

        Returns:
            List of attachment dictionaries containing:
                - id: Attachment ID
                - filename: File name
                - size: File size in bytes
                - mimeType: MIME type
                - content: Download URL
                - created: Upload timestamp
                - author: Uploader details

        Raises:
            JiraAPIError: If API request fails
            JiraAuthError: If authentication fails
        """
        logger.info(f"Fetching attachments for issue: {issue_key}")

        try:
            # Fetch issue with attachment field
            result = await self._retry_with_backoff(
                self.client.issue,
                issue_key,
                fields="attachment"
            )

            # Extract attachments
            fields = result.get("fields", {})
            attachments = fields.get("attachment", [])

            logger.info(f"Fetched {len(attachments)} attachments for issue: {issue_key}")
            return attachments

        except HTTPError as e:
            if e.response.status_code == 404:
                raise JiraAPIError(f"Issue not found: {issue_key}")
            raise
        except JiraAuthError:
            raise
        except JiraRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch attachments for {issue_key}: {e}")
            raise JiraAPIError(f"Failed to fetch attachments: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get client statistics.

        Returns:
            Dictionary with:
                - total_requests: Total number of requests made
                - failed_requests: Number of failed requests
                - success_rate: Percentage of successful requests
        """
        total = self.total_requests
        failed = self.failed_requests
        success_rate = ((total - failed) / total * 100) if total > 0 else 0.0

        return {
            "total_requests": total,
            "failed_requests": failed,
            "success_rate": round(success_rate, 2)
        }
