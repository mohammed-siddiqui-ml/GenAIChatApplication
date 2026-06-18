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

__all__ = [
    "OpenAIClient",
    "OpenAIError",
    "OpenAIRateLimitError",
    "OpenAIAPIError",
    "CircuitBreakerOpen",
]
