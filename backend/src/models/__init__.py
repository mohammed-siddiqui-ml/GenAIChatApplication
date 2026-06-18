"""
Models module containing database models and ORM definitions.

This module exports all SQLAlchemy ORM models for the GenAI Knowledge Retrieval System.
"""
# Base classes
from .base import Base, TimestampMixin, TimestampCreateMixin, to_dict

# User models
from .user import User, UserRole

# Chat models
from .chat import ChatSession, ChatMessage, MessageRole

# Data source models
from .data_source import DataSource, IngestionJob, DataSourceType, JobStatus

# Knowledge models
from .knowledge import KnowledgeDocument, DocumentEmbedding, ContentType

# Audit models
from .audit import AuditLog

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "TimestampCreateMixin",
    "to_dict",
    # User
    "User",
    "UserRole",
    # Chat
    "ChatSession",
    "ChatMessage",
    "MessageRole",
    # Data Source
    "DataSource",
    "IngestionJob",
    "DataSourceType",
    "JobStatus",
    # Knowledge
    "KnowledgeDocument",
    "DocumentEmbedding",
    "ContentType",
    # Audit
    "AuditLog",
]
