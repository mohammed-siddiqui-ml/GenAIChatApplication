"""
Chat models for managing chat sessions and messages.

This module defines models for chat sessions and individual messages
in the conversational interface.
"""
from datetime import datetime
from typing import List, Optional
import enum
import uuid

from sqlalchemy import (
    BigInteger, Integer, String, Text, TIMESTAMP, ForeignKey,
    Enum as SQLEnum, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .types import INET, JSONB, UUID


class MessageRole(str, enum.Enum):
    """Enumeration of message roles in a chat conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSession(Base):
    """
    Chat session model representing a user's conversation.
    
    Tracks individual chat sessions for both authenticated and anonymous users.
    
    Attributes:
        id: Primary key (UUID)
        user_id: Optional foreign key to users table
        session_token: Unique token for session identification
        ip_address: IP address of the user
        user_agent: Browser user agent string
        started_at: When the session was started
        last_activity_at: Last activity timestamp
        ended_at: When the session ended (if applicable)
        
    Relationships:
        user: Associated user (if authenticated)
        messages: List of messages in this session
    """
    __tablename__ = "chat_sessions"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique session identifier (UUID)"
    )
    
    # Foreign keys
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated user ID (null for anonymous users)"
    )
    
    # Session attributes
    session_token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique session token"
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        comment="IP address of the user"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Browser user agent string"
    )
    
    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        comment="Session start timestamp"
    )
    
    last_activity_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last activity timestamp"
    )
    
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
        comment="Session end timestamp"
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="chat_sessions",
        lazy="selectin"
    )
    
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        """String representation of the ChatSession model."""
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, started_at={self.started_at})>"


class ChatMessage(Base):
    """
    Chat message model representing individual messages in a conversation.

    Stores messages from users, AI assistant responses, and system messages.

    Attributes:
        id: Primary key
        session_id: Foreign key to chat_sessions table
        role: Message role (user, assistant, or system)
        content: Message text content
        metadata: Additional metadata (JSON)
        created_at: Message creation timestamp
        embedding: Optional embedding vector for semantic search

    Relationships:
        session: Associated chat session
    """
    __tablename__ = "chat_messages"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique message identifier"
    )

    # Foreign keys
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated chat session ID"
    )

    # Message attributes
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Message role (user, assistant, or system)"
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message text content"
    )

    message_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",  # Database column name
        JSONB,
        nullable=True,
        comment="Additional metadata (sources, tokens, etc.)"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Message creation timestamp"
    )

    embedding: Mapped[Optional[List[float]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Optional embedding vector for semantic search (stored as JSON array)"
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="messages",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """String representation of the ChatMessage model."""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(id={self.id}, role='{self.role.value}', content='{content_preview}')>"
