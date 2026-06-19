"""
Sentry Context Middleware

Middleware to attach user context and additional metadata to Sentry events.
This helps with debugging by providing user session information in error reports.
"""

from typing import Callable
import uuid

import sentry_sdk
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SentryContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enrich Sentry events with user context and request metadata.
    
    Attaches:
    - User ID (from JWT token if authenticated)
    - Session ID (from request headers or generated)
    - Request metadata (path, method, IP)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and attach context to Sentry scope.
        
        Args:
            request: The incoming request
            call_next: The next middleware/route handler
            
        Returns:
            Response from the next handler
        """
        # Get or generate session ID
        session_id = request.headers.get("X-Session-ID")
        if not session_id:
            # Generate a session ID if not provided
            session_id = str(uuid.uuid4())
        
        # Configure Sentry scope with user context
        with sentry_sdk.push_scope() as scope:
            # Set session/user context
            scope.set_user({
                "id": session_id,
                "ip_address": request.client.host if request.client else None,
            })
            
            # Try to get user_id from request state (set by auth middleware)
            if hasattr(request.state, "user_id"):
                scope.set_user({
                    "id": str(request.state.user_id),
                    "session_id": session_id,
                    "ip_address": request.client.host if request.client else None,
                })
            
            # Add request context as tags
            scope.set_tag("http.method", request.method)
            scope.set_tag("http.url", str(request.url))
            scope.set_tag("session_id", session_id)
            
            # Add custom context
            scope.set_context("request", {
                "path": request.url.path,
                "method": request.method,
                "query_params": dict(request.query_params),
                "headers": dict(request.headers),
            })
            
            # Set transaction name for better grouping
            scope.set_transaction_name(f"{request.method} {request.url.path}")
            
            # Process the request
            response = await call_next(request)
            
            # Add response status to tags
            scope.set_tag("http.status_code", response.status_code)
            
            return response
