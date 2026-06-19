"""
Schemas module containing Pydantic models for request/response validation.
"""

# Authentication schemas
from .auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse

# Chat schemas
from .chat import QueryRequest, QueryResponse, SourceCitation, SessionResponse

# Admin schemas
from .admin import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    DataSourceListResponse,
    AuditLogResponse,
    AuditLogListResponse
)

__all__ = [
    # Authentication
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    # Chat
    "QueryRequest",
    "QueryResponse",
    "SourceCitation",
    "SessionResponse",
    # Admin
    "DataSourceCreate",
    "DataSourceUpdate",
    "DataSourceResponse",
    "DataSourceListResponse",
    "AuditLogResponse",
    "AuditLogListResponse",
]
