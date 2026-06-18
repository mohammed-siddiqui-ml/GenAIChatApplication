"""
Redis Client and Cache Layer

This module provides async Redis client configuration with connection pooling,
cache utilities, session management, and rate limiting functions.
"""

import logging
from typing import Any, Optional
from datetime import timedelta

import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from core.config import settings

# Logger
logger = logging.getLogger(__name__)

# Global Redis client and connection pool
_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


def get_redis_pool() -> ConnectionPool:
    """
    Get or create the Redis connection pool.
    
    The connection pool is configured with:
    - max_connections: Maximum number of connections in the pool
    - decode_responses: Automatically decode byte responses to strings
    - Connection URL from settings (includes password authentication)
    
    Returns:
        ConnectionPool: Configured Redis connection pool instance
    """
    global _redis_pool
    
    if _redis_pool is None:
        logger.info("Creating Redis connection pool...")
        logger.info(f"Redis URL: {settings.REDIS_URL.split('@')[1] if '@' in settings.REDIS_URL else 'configured'}")
        
        _redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            encoding="utf-8",
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        
        logger.info(
            f"Redis connection pool created with max_connections={settings.REDIS_MAX_CONNECTIONS}"
        )
    
    return _redis_pool


def get_redis_client() -> Redis:
    """
    Get or create the async Redis client.
    
    The Redis client uses a connection pool for efficient connection management
    and supports password authentication as configured in settings.
    
    Returns:
        Redis: Configured async Redis client instance
    """
    global _redis_client
    
    if _redis_client is None:
        pool = get_redis_pool()
        _redis_client = Redis(connection_pool=pool)
        logger.info("Redis client created")
    
    return _redis_client


async def init_redis() -> None:
    """
    Initialize Redis on application startup.
    
    This function should be called during application startup to:
    - Verify Redis connectivity
    - Test authentication
    - Log connection pool status
    
    Raises:
        Exception: If Redis initialization fails
    """
    try:
        client = get_redis_client()
        
        # Test Redis connectivity
        await client.ping()
        
        logger.info("Redis initialized successfully")
        logger.info(f"Redis connection pool: max_connections={settings.REDIS_MAX_CONNECTIONS}")
        
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {str(e)}")
        raise


async def check_redis_health() -> bool:
    """
    Check Redis health for readiness probes.
    
    This function executes a PING command to verify that:
    - Redis is reachable
    - Authentication is working
    - Connection pool has available connections
    
    Used by the /ready endpoint for Kubernetes/Docker health checks.
    
    Returns:
        bool: True if Redis is healthy, False otherwise
    """
    try:
        client = get_redis_client()
        await client.ping()
        logger.debug("Redis health check passed")
        return True
        
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return False


async def close_redis() -> None:
    """
    Close Redis connections on application shutdown.

    This function should be called during application shutdown to:
    - Close all active connections in the pool
    - Release Redis resources
    - Ensure clean shutdown
    """
    global _redis_client, _redis_pool

    if _redis_client is not None:
        logger.info("Closing Redis connections...")
        await _redis_client.aclose()
        _redis_client = None

    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None

    logger.info("Redis connections closed")


# ============================================================================
# Cache Utility Functions
# ============================================================================

async def cache_get(key: str) -> Optional[str]:
    """
    Get a value from Redis cache.

    Args:
        key: Cache key to retrieve

    Returns:
        Optional[str]: Cached value as string, or None if key doesn't exist

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()
        value = await client.get(key)
        logger.debug(f"Cache GET: {key} -> {'HIT' if value else 'MISS'}")
        return value
    except RedisError as e:
        logger.error(f"Cache GET failed for key '{key}': {str(e)}")
        raise


async def cache_set(
    key: str,
    value: str,
    expire: Optional[int] = None
) -> bool:
    """
    Set a value in Redis cache with optional expiration.

    Args:
        key: Cache key to set
        value: Value to store (will be converted to string)
        expire: Optional expiration time in seconds

    Returns:
        bool: True if successful, False otherwise

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()

        if expire is not None:
            result = await client.setex(key, expire, value)
        else:
            result = await client.set(key, value)

        logger.debug(f"Cache SET: {key} (expire={expire}s)")
        return bool(result)
    except RedisError as e:
        logger.error(f"Cache SET failed for key '{key}': {str(e)}")
        raise


async def cache_delete(key: str) -> int:
    """
    Delete a key from Redis cache.

    Args:
        key: Cache key to delete

    Returns:
        int: Number of keys deleted (0 or 1)

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()
        result = await client.delete(key)
        logger.debug(f"Cache DELETE: {key} -> {result} keys deleted")
        return result
    except RedisError as e:
        logger.error(f"Cache DELETE failed for key '{key}': {str(e)}")
        raise


async def cache_expire(key: str, seconds: int) -> bool:
    """
    Set expiration time on an existing key.

    Args:
        key: Cache key to set expiration on
        seconds: Expiration time in seconds

    Returns:
        bool: True if expiration was set, False if key doesn't exist

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()
        result = await client.expire(key, seconds)
        logger.debug(f"Cache EXPIRE: {key} -> {seconds}s (success={result})")
        return bool(result)
    except RedisError as e:
        logger.error(f"Cache EXPIRE failed for key '{key}': {str(e)}")
        raise


# ============================================================================
# Session Token Storage Functions
# ============================================================================

async def session_set(session_token: str, session_data: str, expire_seconds: int = 3600) -> bool:
    """
    Store session token and associated data in Redis.

    Sessions are stored with a default expiration of 1 hour.
    Used for JWT token management and user session tracking.

    Args:
        session_token: Unique session token (e.g., JWT token, session ID)
        session_data: Session data to store (typically JSON string)
        expire_seconds: Expiration time in seconds (default: 3600 = 1 hour)

    Returns:
        bool: True if successful, False otherwise

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        key = f"session:{session_token}"
        return await cache_set(key, session_data, expire=expire_seconds)
    except RedisError as e:
        logger.error(f"Session SET failed for token '{session_token}': {str(e)}")
        raise


async def session_get(session_token: str) -> Optional[str]:
    """
    Retrieve session data from Redis by session token.

    Args:
        session_token: Session token to look up

    Returns:
        Optional[str]: Session data as string, or None if session doesn't exist or expired

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        key = f"session:{session_token}"
        return await cache_get(key)
    except RedisError as e:
        logger.error(f"Session GET failed for token '{session_token}': {str(e)}")
        raise


async def session_delete(session_token: str) -> int:
    """
    Delete session from Redis (used for logout).

    Args:
        session_token: Session token to delete

    Returns:
        int: Number of keys deleted (0 or 1)

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        key = f"session:{session_token}"
        return await cache_delete(key)
    except RedisError as e:
        logger.error(f"Session DELETE failed for token '{session_token}': {str(e)}")
        raise


async def session_extend(session_token: str, expire_seconds: int = 3600) -> bool:
    """
    Extend session expiration time (refresh session).

    Args:
        session_token: Session token to extend
        expire_seconds: New expiration time in seconds (default: 3600 = 1 hour)

    Returns:
        bool: True if expiration was extended, False if session doesn't exist

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        key = f"session:{session_token}"
        return await cache_expire(key, expire_seconds)
    except RedisError as e:
        logger.error(f"Session EXTEND failed for token '{session_token}': {str(e)}")
        raise


# ============================================================================
# Rate Limiting Functions
# ============================================================================

async def rate_limit_increment(
    identifier: str,
    window_seconds: int = 60,
    max_requests: Optional[int] = None
) -> int:
    """
    Increment rate limit counter for an identifier (IP address, user ID, etc.).

    Uses a simple counter with expiration for rate limiting.
    The counter resets after the window expires.

    Args:
        identifier: Unique identifier for rate limiting (e.g., IP address, user ID)
        window_seconds: Time window in seconds (default: 60 = 1 minute)
        max_requests: Optional max requests limit (for logging purposes)

    Returns:
        int: Current request count for this identifier in the current window

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()
        key = f"ratelimit:{identifier}"

        # Increment counter
        count = await client.incr(key)

        # Set expiration on first request in the window
        if count == 1:
            await client.expire(key, window_seconds)

        logger.debug(
            f"Rate limit INCR: {identifier} -> {count}"
            f"{f'/{max_requests}' if max_requests else ''} in {window_seconds}s window"
        )

        return count
    except RedisError as e:
        logger.error(f"Rate limit INCREMENT failed for '{identifier}': {str(e)}")
        raise


async def rate_limit_check(identifier: str, max_requests: int) -> bool:
    """
    Check if rate limit has been exceeded for an identifier.

    Args:
        identifier: Unique identifier to check (e.g., IP address, user ID)
        max_requests: Maximum allowed requests in the current window

    Returns:
        bool: True if under the limit (request allowed), False if limit exceeded

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()
        key = f"ratelimit:{identifier}"

        # Get current count
        count_str = await client.get(key)
        count = int(count_str) if count_str else 0

        allowed = count < max_requests

        logger.debug(
            f"Rate limit CHECK: {identifier} -> {count}/{max_requests} "
            f"({'ALLOWED' if allowed else 'BLOCKED'})"
        )

        return allowed
    except RedisError as e:
        logger.error(f"Rate limit CHECK failed for '{identifier}': {str(e)}")
        raise


async def rate_limit_reset(identifier: str) -> int:
    """
    Reset rate limit counter for an identifier.

    Useful for administrative purposes or testing.

    Args:
        identifier: Unique identifier to reset

    Returns:
        int: Number of keys deleted (0 or 1)

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()
        key = f"ratelimit:{identifier}"
        result = await client.delete(key)
        logger.debug(f"Rate limit RESET: {identifier}")
        return result
    except RedisError as e:
        logger.error(f"Rate limit RESET failed for '{identifier}': {str(e)}")
        raise


async def rate_limit_get_remaining(identifier: str, max_requests: int) -> int:
    """
    Get remaining requests allowed for an identifier in current window.

    Args:
        identifier: Unique identifier to check
        max_requests: Maximum allowed requests in the window

    Returns:
        int: Number of remaining requests allowed (0 if limit exceeded)

    Raises:
        RedisError: If Redis operation fails
    """
    try:
        client = get_redis_client()
        key = f"ratelimit:{identifier}"

        count_str = await client.get(key)
        count = int(count_str) if count_str else 0

        remaining = max(0, max_requests - count)

        logger.debug(f"Rate limit REMAINING: {identifier} -> {remaining}/{max_requests}")

        return remaining
    except RedisError as e:
        logger.error(f"Rate limit GET_REMAINING failed for '{identifier}': {str(e)}")
        raise


# ============================================================================
# Celery Broker Configuration Helpers
# ============================================================================

def get_celery_broker_url() -> str:
    """
    Get Celery broker URL from settings.

    Celery uses a separate Redis database (db 1) for task queue management.
    This is configured in the REDIS_URL environment variable.

    For Celery configuration, use:
        CELERY_BROKER_URL=redis://:password@host:port/1

    Returns:
        str: Redis URL for Celery broker (typically db 1)
    """
    # Celery broker typically uses Redis db 1
    # This can be configured via CELERY_BROKER_URL environment variable
    # For now, we'll return the base Redis URL which can be modified in Celery config
    base_url = settings.REDIS_URL

    # If URL points to db 0, suggest using db 1 for Celery
    if base_url.endswith('/0'):
        celery_url = base_url[:-1] + '1'
        logger.info(f"Celery broker URL (suggested): db 1 for task queue")
        return celery_url

    return base_url


def get_celery_result_backend_url() -> str:
    """
    Get Celery result backend URL from settings.

    Celery uses a separate Redis database (db 2) for storing task results.

    For Celery configuration, use:
        CELERY_RESULT_BACKEND=redis://:password@host:port/2

    Returns:
        str: Redis URL for Celery result backend (typically db 2)
    """
    base_url = settings.REDIS_URL

    # If URL points to db 0, suggest using db 2 for results
    if base_url.endswith('/0'):
        result_url = base_url[:-1] + '2'
        logger.info(f"Celery result backend URL (suggested): db 2 for task results")
        return result_url

    return base_url
