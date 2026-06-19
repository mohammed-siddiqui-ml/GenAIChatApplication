"""
Logging Middleware for Request Context

This middleware captures request context information and makes it available
for structured logging throughout the request lifecycle.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import set_trace_id, set_user_id

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for capturing request context and logging requests.
    
    This middleware:
    - Generates or extracts a trace ID for each request
    - Extracts user ID from request context (if authenticated)
    - Logs request and response information
    - Measures request duration
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and add logging context.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
        
        Returns:
            The response from the route handler
        """
        # Generate or extract trace ID
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        set_trace_id(trace_id)
        
        # Extract user ID if available (from authenticated user)
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = str(request.state.user.id)
        set_user_id(user_id)
        
        # Record start time
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "trace_id": trace_id,
                "user_id": user_id,
                "service": "fastapi",
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration": f"{duration_ms:.2f}ms",
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "service": "fastapi",
                }
            )
            
            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            
            return response
            
        except Exception as exc:
            # Calculate duration even on error
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {exc}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration": f"{duration_ms:.2f}ms",
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "service": "fastapi",
                    "error": str(exc),
                },
                exc_info=True
            )
            raise


class CeleryLoggingContextFilter(logging.Filter):
    """
    Logging filter for Celery tasks to add structured logging context.
    
    This filter adds:
    - Service identifier (celery-worker)
    - Task ID and name from Celery task context
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add Celery context to log record.
        
        Args:
            record: The log record to modify
        
        Returns:
            True to allow the record to be logged
        """
        # Set service name
        if not hasattr(record, "service"):
            record.service = "celery-worker"
        
        # Try to get Celery task context
        try:
            from celery import current_task
            if current_task and current_task.request:
                record.task_id = current_task.request.id
                record.task_name = current_task.name
                # Use task ID as trace ID for task tracking
                if not hasattr(record, "trace_id"):
                    record.trace_id = current_task.request.id
        except (ImportError, AttributeError):
            pass
        
        return True
