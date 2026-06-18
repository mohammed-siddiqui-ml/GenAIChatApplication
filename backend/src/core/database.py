"""
Database Session Management and Connection Pooling

This module provides async database session management using SQLAlchemy AsyncSession,
connection pooling configuration, and dependency injection utilities for FastAPI routes.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from core.config import settings
from models.base import Base

# Logger
logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine.
    
    The engine is configured with connection pooling parameters from settings:
    - pool_size: Maximum number of database connections to maintain in the pool
    - max_overflow: Maximum number of connections that can be created beyond pool_size
    - pool_pre_ping: Verify connections before using them (helps with stale connections)
    - echo: Log all SQL statements (useful for debugging)
    
    Returns:
        AsyncEngine: Configured SQLAlchemy async engine instance
    """
    global _engine
    
    if _engine is None:
        logger.info("Creating database engine...")
        logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'unknown'}")
        
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,  # Log SQL statements in debug mode
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,  # Verify connection health before using
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
        
        logger.info(
            f"Database engine created with pool_size={settings.DATABASE_POOL_SIZE}, "
            f"max_overflow={settings.DATABASE_MAX_OVERFLOW}"
        )
    
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory.
    
    The session factory is configured to:
    - Not auto-commit (explicit control over transactions)
    - Not auto-flush (explicit control over when changes are sent to DB)
    - Expire on commit (refresh objects after commit to reflect DB state)
    
    Returns:
        async_sessionmaker[AsyncSession]: Configured session factory
    """
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_engine()
        
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Keep objects usable after commit
            autocommit=False,  # Explicit transaction control
            autoflush=False,  # Explicit flush control
        )
        
        logger.info("Session factory created")
    
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session injection.
    
    This async generator provides a database session to route handlers and
    automatically manages the session lifecycle:
    - Creates a new session for each request
    - Commits the transaction on success
    - Rolls back on errors
    - Always closes the session
    
    Usage in FastAPI routes:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    
    Yields:
        AsyncSession: Database session for the request
    """
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            logger.debug("Database session created")
            yield session
            await session.commit()
            logger.debug("Database session committed")
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error occurred, rolling back: {str(e)}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error occurred, rolling back: {str(e)}")
            raise
        finally:
            await session.close()
            logger.debug("Database session closed")


async def init_db() -> None:
    """
    Initialize database on application startup.
    
    This function should be called during application startup to:
    - Verify database connectivity
    - Log connection pool status
    - Optionally create tables (if not using migrations)
    
    Note: In production, use Alembic migrations instead of create_all()
    
    Raises:
        Exception: If database initialization fails
    """
    try:
        engine = get_engine()

        # Test database connectivity
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("Database initialized successfully")

        # Log pool info only if pool supports size() and overflow() methods
        # StaticPool (used by SQLite) doesn't have these methods
        try:
            pool_size = engine.pool.size()
            pool_overflow = engine.pool.overflow()
            logger.info(f"Connection pool: size={pool_size}, overflow={pool_overflow}")
        except (AttributeError, TypeError):
            # Some pool types don't support size()/overflow()
            logger.info(f"Connection pool type: {engine.pool.__class__.__name__}")

    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


async def check_db_health() -> bool:
    """
    Check database health for readiness probes.
    
    This function executes a simple query to verify that:
    - Database is reachable
    - Connection pool has available connections
    - Database is accepting queries
    
    Used by the /ready endpoint for Kubernetes/Docker health checks.
    
    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        engine = get_engine()
        
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        
        logger.debug("Database health check passed")
        return True
        
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False


async def close_db() -> None:
    """
    Close database connections on application shutdown.
    
    This function should be called during application shutdown to:
    - Close all active connections in the pool
    - Release database resources
    - Ensure clean shutdown
    """
    global _engine, _async_session_factory
    
    if _engine is not None:
        logger.info("Closing database connections...")
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database connections closed")
