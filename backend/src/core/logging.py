"""
Logging Configuration

Centralized logging setup for the application with support for
both JSON and text formats.

This module provides structured JSON logging with the following fields:
- timestamp: ISO 8601 formatted timestamp
- level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- service: Service name (fastapi, celery-worker, etc.)
- message: Log message
- trace_id: Request trace ID for distributed tracing
- user_id: User ID if available in request context
- environment: Deployment environment
- application: Application name
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

from core.config import settings

# Context variables for request-scoped data
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter with additional fields for structured logging.

    This formatter adds the following fields to all log records:
    - timestamp: ISO 8601 formatted timestamp
    - level: Log level (INFO, ERROR, etc.)
    - service: Service name
    - message: Log message
    - trace_id: Request trace ID
    - user_id: User ID if available
    - environment: Deployment environment
    - application: Application name
    """

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """
        Add custom fields to log record.

        Args:
            log_record: The log record dictionary to be written
            record: The LogRecord object
            message_dict: Additional message data
        """
        super().add_fields(log_record, record, message_dict)

        # Standard fields
        log_record["timestamp"] = self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%fZ")
        log_record["level"] = record.levelname
        log_record["service"] = getattr(record, "service", "fastapi")
        log_record["message"] = record.getMessage()

        # Request context fields
        log_record["trace_id"] = getattr(record, "trace_id", trace_id_var.get() or "")
        log_record["user_id"] = getattr(record, "user_id", user_id_var.get() or "")

        # Environment fields
        log_record["environment"] = settings.ENVIRONMENT
        log_record["application"] = settings.PROJECT_NAME

        # Additional request metadata if available
        if hasattr(record, "method"):
            log_record["method"] = record.method
        if hasattr(record, "path"):
            log_record["path"] = record.path
        if hasattr(record, "status_code"):
            log_record["status_code"] = record.status_code
        if hasattr(record, "duration"):
            log_record["duration"] = record.duration


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """
    Set the trace ID for the current request context.

    Args:
        trace_id: Optional trace ID. If not provided, generates a new UUID.

    Returns:
        The trace ID that was set
    """
    if trace_id is None:
        trace_id = str(uuid.uuid4())
    trace_id_var.set(trace_id)
    return trace_id


def set_user_id(user_id: Optional[str]) -> None:
    """
    Set the user ID for the current request context.

    Args:
        user_id: User ID to set
    """
    user_id_var.set(user_id)


def get_trace_id() -> Optional[str]:
    """
    Get the current trace ID from context.

    Returns:
        The current trace ID or None
    """
    return trace_id_var.get()


def get_user_id() -> Optional[str]:
    """
    Get the current user ID from context.

    Returns:
        The current user ID or None
    """
    return user_id_var.get()


def setup_logging() -> logging.Logger:
    """
    Configure application logging with appropriate format and level.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Set formatter based on configuration
    if settings.LOG_FORMAT == "json":
        formatter = CustomJsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return logger
