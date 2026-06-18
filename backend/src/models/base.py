"""
Base model class and utilities for SQLAlchemy ORM models.

This module provides the declarative base and common mixins for all database models.
"""
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import TIMESTAMP, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    
    This class provides the foundation for all database models using
    SQLAlchemy 2.0 declarative style with type hints.
    """
    pass


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp columns.
    
    These columns are automatically managed by the database with NOW() defaults
    and triggers for updated_at.
    """
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the record was last updated"
    )


class TimestampCreateMixin:
    """
    Mixin that adds only created_at timestamp column.
    
    Used for immutable records that don't need an updated_at field.
    """
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the record was created"
    )


def to_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert a SQLAlchemy model instance to a dictionary.
    
    Args:
        obj: SQLAlchemy model instance
        
    Returns:
        Dictionary representation of the model instance
    """
    return {
        column.name: getattr(obj, column.name)
        for column in obj.__table__.columns
    }
