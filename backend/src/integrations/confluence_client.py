"""
Confluence Client Integration

Provides a robust client wrapper for Confluence API with:
- Space and page fetching with pagination
- Attachment retrieval
- Page history tracking
- Rate limiting and retry logic
- Error handling for authentication and API errors
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

from atlassian import Confluence
import requests
from requests.exceptions import RequestException, HTTPError

from core.config import settings


# Logger
logger = logging.getLogger(__name__)


# Custom Exceptions
class ConfluenceError(Exception):
    """Base exception for Confluence client errors."""
    pass


class ConfluenceAuthError(ConfluenceError):
    """Raised when authentication fails."""
    pass


class ConfluenceAPIError(ConfluenceError):
    """Raised when Confluence API returns an error."""
    pass


class ConfluenceRateLimitError(ConfluenceError):
    """Raised when rate limit is exceeded."""
    pass


@dataclass
class RateLimiter:
    """
    Rate limiter to respect Confluence API limits.
    
    Confluence Cloud typically allows:
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
            ConfluenceRateLimitError: If rate limit would be exceeded
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
        
        # Check per-minute limit
        if len(self.minute_window) >= self.max_requests_per_minute:
            wait_time = 60.0 - (current_time - self.minute_window[0])
            if wait_time > 0:
                logger.warning(f"Rate limit: waiting {wait_time:.2f}s (per-minute)")
                await asyncio.sleep(wait_time)
                current_time = time.time()
        
        # Record this request
        self.second_window.append(current_time)
        self.minute_window.append(current_time)


class ConfluenceClient:
    """
    Robust Confluence API client with pagination and rate limiting.
    
    Features:
    - Fetch spaces with pagination
    - Fetch pages with content
    - Fetch page by ID with HTML content
    - Fetch attachments for pages
    - Rate limiting (8 req/s, 80 req/min)
    - Retry logic with exponential backoff
    - Error handling for auth and API errors
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 10.0  # seconds
    
    # Pagination defaults
    DEFAULT_PAGE_LIMIT = 50
    MAX_PAGE_LIMIT = 100

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        enable_rate_limiting: bool = True
    ):
        """
        Initialize Confluence client.

        Args:
            url: Confluence instance URL (defaults to settings.CONFLUENCE_URL)
            username: Confluence username/email (defaults to settings.CONFLUENCE_USERNAME)
            api_token: Confluence API token (defaults to settings.CONFLUENCE_API_TOKEN)
            enable_rate_limiting: Whether to enable rate limiting

        Raises:
            ConfluenceAuthError: If credentials are missing
        """
        self.url = url or settings.CONFLUENCE_URL
        self.username = username or settings.CONFLUENCE_USERNAME
        self.api_token = api_token or settings.CONFLUENCE_API_TOKEN

        if not self.url:
            raise ConfluenceAuthError("Confluence URL not provided")
        if not self.username:
            raise ConfluenceAuthError("Confluence username not provided")
        if not self.api_token:
            raise ConfluenceAuthError("Confluence API token not provided")

        # Remove trailing slash from URL
        self.url = self.url.rstrip('/')

        # Initialize Confluence client
        try:
            self.client = Confluence(
                url=self.url,
                username=self.username,
                password=self.api_token,
                cloud=True  # Use Confluence Cloud API
            )
            logger.info(f"Confluence client initialized: {self.url}")
        except Exception as e:
            logger.error(f"Failed to initialize Confluence client: {e}")
            raise ConfluenceAuthError(f"Failed to initialize client: {e}")

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
            ConfluenceError: If all retries fail
        """
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Apply rate limiting
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                # Execute function in thread pool (sync to async)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))

                self.total_requests += 1
                return result

            except HTTPError as e:
                last_exception = e
                self.failed_requests += 1

                # Check for authentication errors
                if e.response.status_code in (401, 403):
                    logger.error(f"Authentication failed: {e}")
                    raise ConfluenceAuthError(f"Authentication failed: {e}")

                # Check for rate limit errors
                if e.response.status_code == 429:
                    logger.warning(f"Rate limit exceeded (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    retry_after = int(e.response.headers.get('Retry-After', 60))

                    if attempt < self.MAX_RETRIES - 1:
                        logger.info(f"Retrying after {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise ConfluenceRateLimitError(f"Rate limit exceeded: {e}")

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
                raise ConfluenceAPIError(f"Unexpected error: {e}")

        # All retries failed
        raise ConfluenceAPIError(f"Failed after {self.MAX_RETRIES} retries: {last_exception}")

    async def fetch_spaces(
        self,
        start: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
        space_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch Confluence spaces with pagination.

        Args:
            start: Pagination start index
            limit: Number of spaces to fetch (max 100)
            space_type: Filter by space type ('global' or 'personal')

        Returns:
            Dictionary with 'results', 'start', 'limit', 'size', '_links'

        Raises:
            ConfluenceAPIError: If fetch fails
        """
        try:
            limit = min(limit, self.MAX_PAGE_LIMIT)
            logger.debug(f"Fetching spaces: start={start}, limit={limit}, type={space_type}")

            # Build parameters
            params = {
                'start': start,
                'limit': limit
            }
            if space_type:
                params['type'] = space_type

            # Fetch spaces using atlassian-python-api
            result = await self._retry_with_backoff(
                self.client.get_all_spaces,
                start=start,
                limit=limit,
                space_type=space_type
            )

            logger.info(f"Fetched {len(result.get('results', []))} spaces")
            return result

        except (ConfluenceAuthError, ConfluenceRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Failed to fetch spaces: {e}")
            raise ConfluenceAPIError(f"Failed to fetch spaces: {e}")

    async def fetch_pages(
        self,
        space_key: str,
        start: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
        expand: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch pages from a Confluence space with content.

        Args:
            space_key: The space key to fetch pages from
            start: Pagination start index
            limit: Number of pages to fetch (max 100)
            expand: List of fields to expand (e.g., ['body.storage', 'version', 'history'])

        Returns:
            Dictionary with 'results', 'start', 'limit', 'size', '_links'

        Raises:
            ConfluenceAPIError: If fetch fails
        """
        try:
            limit = min(limit, self.MAX_PAGE_LIMIT)
            expand = expand or ['body.storage', 'version', 'metadata.labels']
            expand_str = ','.join(expand)

            logger.debug(f"Fetching pages from space '{space_key}': start={start}, limit={limit}")

            # Fetch pages using atlassian-python-api
            result = await self._retry_with_backoff(
                self.client.get_all_pages_from_space,
                space=space_key,
                start=start,
                limit=limit,
                expand=expand_str
            )

            pages_count = len(result.get('results', []))
            logger.info(f"Fetched {pages_count} pages from space '{space_key}'")
            return result

        except (ConfluenceAuthError, ConfluenceRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Failed to fetch pages from space '{space_key}': {e}")
            raise ConfluenceAPIError(f"Failed to fetch pages: {e}")

    async def fetch_page_by_id(
        self,
        page_id: str,
        expand: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch a specific page by ID with HTML content extraction.

        Args:
            page_id: The Confluence page ID
            expand: List of fields to expand

        Returns:
            Dictionary with page details including body.storage (HTML content)

        Raises:
            ConfluenceAPIError: If fetch fails
        """
        try:
            expand = expand or ['body.storage', 'body.view', 'version', 'history', 'metadata.labels']
            expand_str = ','.join(expand)

            logger.debug(f"Fetching page by ID: {page_id}")

            # Fetch page by ID
            result = await self._retry_with_backoff(
                self.client.get_page_by_id,
                page_id=page_id,
                expand=expand_str
            )

            logger.info(f"Fetched page: {page_id} - {result.get('title', 'Unknown')}")
            return result

        except (ConfluenceAuthError, ConfluenceRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Failed to fetch page {page_id}: {e}")
            raise ConfluenceAPIError(f"Failed to fetch page: {e}")

    async def fetch_attachments(
        self,
        page_id: str,
        start: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch attachments for a Confluence page.

        Args:
            page_id: The Confluence page ID
            start: Pagination start index
            limit: Number of attachments to fetch
            filename: Optional filename filter

        Returns:
            Dictionary with attachment details including download links

        Raises:
            ConfluenceAPIError: If fetch fails
        """
        try:
            limit = min(limit, self.MAX_PAGE_LIMIT)
            logger.debug(f"Fetching attachments for page {page_id}: start={start}, limit={limit}")

            # Fetch attachments
            result = await self._retry_with_backoff(
                self.client.get_attachments_from_content,
                page_id=page_id,
                start=start,
                limit=limit,
                filename=filename
            )

            attachments_count = len(result.get('results', []))
            logger.info(f"Fetched {attachments_count} attachments for page {page_id}")
            return result

        except (ConfluenceAuthError, ConfluenceRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Failed to fetch attachments for page {page_id}: {e}")
            raise ConfluenceAPIError(f"Failed to fetch attachments: {e}")

    async def fetch_page_history(
        self,
        page_id: str,
        start: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT
    ) -> Dict[str, Any]:
        """
        Fetch version history for a Confluence page.

        Args:
            page_id: The Confluence page ID
            start: Pagination start index
            limit: Number of versions to fetch

        Returns:
            Dictionary with version history

        Raises:
            ConfluenceAPIError: If fetch fails
        """
        try:
            limit = min(limit, self.MAX_PAGE_LIMIT)
            logger.debug(f"Fetching history for page {page_id}: start={start}, limit={limit}")

            # Fetch page history
            result = await self._retry_with_backoff(
                self.client.history,
                page_id
            )

            logger.info(f"Fetched history for page {page_id}")
            return result

        except (ConfluenceAuthError, ConfluenceRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Failed to fetch history for page {page_id}: {e}")
            raise ConfluenceAPIError(f"Failed to fetch page history: {e}")

    async def get_all_pages_from_space(
        self,
        space_key: str,
        expand: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all pages from a space using pagination.

        Args:
            space_key: The space key to fetch pages from
            expand: List of fields to expand

        Returns:
            List of all pages in the space

        Raises:
            ConfluenceAPIError: If fetch fails
        """
        all_pages = []
        start = 0
        limit = self.DEFAULT_PAGE_LIMIT

        try:
            while True:
                result = await self.fetch_pages(
                    space_key=space_key,
                    start=start,
                    limit=limit,
                    expand=expand
                )

                pages = result.get('results', [])
                if not pages:
                    break

                all_pages.extend(pages)

                # Check if there are more pages
                size = result.get('size', 0)
                if size < limit:
                    break

                start += limit
                logger.debug(f"Fetched {len(all_pages)} pages so far from space '{space_key}'")

            logger.info(f"Fetched total {len(all_pages)} pages from space '{space_key}'")
            return all_pages

        except (ConfluenceAuthError, ConfluenceRateLimitError, ConfluenceAPIError):
            raise
        except Exception as e:
            logger.error(f"Failed to fetch all pages from space '{space_key}': {e}")
            raise ConfluenceAPIError(f"Failed to fetch all pages: {e}")

    async def test_connection(self) -> bool:
        """
        Test Confluence connection and authentication.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            logger.info("Testing Confluence connection...")
            await self._retry_with_backoff(self.client.get_all_spaces, start=0, limit=1)
            logger.info("Confluence connection test successful")
            return True
        except ConfluenceAuthError:
            logger.error("Confluence authentication failed")
            return False
        except Exception as e:
            logger.error(f"Confluence connection test failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get client statistics.

        Returns:
            Dictionary with request statistics
        """
        return {
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'success_rate': (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0 else 0
            )
        }
