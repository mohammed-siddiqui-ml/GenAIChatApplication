"""
Middleware module containing custom middleware components.
"""

from middleware.auth import (
    get_current_user,
    get_current_active_user,
    require_admin,
    set_auth_cookie,
    clear_auth_cookie,
    get_token_from_request,
)
from middleware.logging_middleware import LoggingMiddleware, CeleryLoggingContextFilter

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "set_auth_cookie",
    "clear_auth_cookie",
    "get_token_from_request",
    "LoggingMiddleware",
    "CeleryLoggingContextFilter",
]
