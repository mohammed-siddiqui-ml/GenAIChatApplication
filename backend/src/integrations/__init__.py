"""
Integration modules for external services.

This package contains client wrappers for external API integrations
including OpenAI, Confluence, and other third-party services.
"""

from integrations.openai_client import (
    OpenAIClient,
    OpenAIError,
    OpenAIRateLimitError,
    OpenAIAPIError,
    CircuitBreakerOpen,
)

from integrations.confluence_client import (
    ConfluenceClient,
    ConfluenceError,
    ConfluenceAuthError,
    ConfluenceAPIError,
    ConfluenceRateLimitError,
)

__all__ = [
    "OpenAIClient",
    "OpenAIError",
    "OpenAIRateLimitError",
    "OpenAIAPIError",
    "CircuitBreakerOpen",
    "ConfluenceClient",
    "ConfluenceError",
    "ConfluenceAuthError",
    "ConfluenceAPIError",
    "ConfluenceRateLimitError",
]
