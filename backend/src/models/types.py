"""
Custom SQLAlchemy types for cross-database compatibility.

This module provides type adapters that handle PostgreSQL-specific types
(INET, TSVECTOR, Vector, JSONB) and provide SQLite-compatible fallbacks for testing.
"""
from typing import Any
from sqlalchemy import String, Text, TypeDecorator, JSON
import uuid as uuid_module
from sqlalchemy.dialects.postgresql import INET as PG_INET, TSVECTOR as PG_TSVECTOR, JSONB as PG_JSONB


class INET(TypeDecorator):
    """
    Cross-database INET type.

    Uses PostgreSQL INET for PostgreSQL databases and VARCHAR for others (e.g., SQLite).
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_INET())
        else:
            return dialect.type_descriptor(String(45))  # Max length for IPv6

    def process_bind_param(self, value, dialect):
        """Convert Python value to database value."""
        return value

    def process_result_value(self, value, dialect):
        """Convert database value to Python value."""
        return value


class TSVECTOR(TypeDecorator):
    """
    Cross-database TSVECTOR type.

    Uses PostgreSQL TSVECTOR for PostgreSQL databases and TEXT for others (e.g., SQLite).
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_TSVECTOR())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        """Convert Python value to database value."""
        return value

    def process_result_value(self, value, dialect):
        """Convert database value to Python value."""
        return value


class Vector(TypeDecorator):
    """
    Cross-database Vector type for pgvector compatibility.

    Uses pgvector Vector type for PostgreSQL databases and TEXT (JSON array) for others.
    """
    impl = Text
    cache_ok = True

    def __init__(self, dim=None):
        """Initialize Vector type with dimension."""
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            try:
                from pgvector.sqlalchemy import Vector as PGVector
                return dialect.type_descriptor(PGVector(self.dim))
            except ImportError:
                # Fallback if pgvector not installed
                return dialect.type_descriptor(Text())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        """Convert Python value to database value."""
        if value is None:
            return value

        if dialect.name != 'postgresql':
            # For SQLite, store as JSON array string
            import json
            if isinstance(value, list):
                return json.dumps(value)
            return value
        return value

    def process_result_value(self, value, dialect):
        """Convert database value to Python value."""
        if value is None:
            return value

        if dialect.name != 'postgresql':
            # For SQLite, parse JSON array string
            import json
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    return value
        return value



class JSONB(TypeDecorator):
    """
    Cross-database JSONB type.

    Uses PostgreSQL JSONB for PostgreSQL databases and JSON for others (e.g., SQLite).
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_JSONB())
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        """Convert Python value to database value."""
        return value

    def process_result_value(self, value, dialect):
        """Convert database value to Python value."""
        return value





class UUID(TypeDecorator):
    """
    Cross-database UUID type.

    Uses PostgreSQL UUID for PostgreSQL databases and CHAR(36) for others (e.g., SQLite).
    """
    impl = String(36)
    cache_ok = True

    def __init__(self, as_uuid=True):
        """Initialize UUID type."""
        super().__init__()
        self.as_uuid = as_uuid

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        """Convert Python value to database value."""
        if value is None:
            return value

        if dialect.name != 'postgresql':
            # For SQLite, store as string
            if isinstance(value, uuid_module.UUID):
                return str(value)
            elif isinstance(value, str):
                return value
            else:
                return str(value)
        else:
            # For PostgreSQL, return as UUID
            if isinstance(value, str):
                return uuid_module.UUID(value) if self.as_uuid else value
            return value

    def process_result_value(self, value, dialect):
        """Convert database value to Python value."""
        if value is None:
            return value

        if dialect.name != 'postgresql' and self.as_uuid:
            # For SQLite, convert string to UUID
            if isinstance(value, str):
                return uuid_module.UUID(value)

        return value
