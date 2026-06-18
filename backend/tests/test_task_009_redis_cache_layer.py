"""
Test Suite for Redis Client and Cache Layer (Task 009)

Tests cover:
- Connection pool and client management
- Lifecycle management (init, health check, close)
- Cache utilities (get, set, delete, expire)
- Session management
- Rate limiting
- Celery helper functions
- FastAPI integration
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

# Import functions under test
from core.redis import (
    get_redis_pool,
    get_redis_client,
    init_redis,
    close_redis,
    check_redis_health,
    cache_get,
    cache_set,
    cache_delete,
    cache_expire,
    session_set,
    session_get,
    session_delete,
    session_extend,
    rate_limit_increment,
    rate_limit_check,
    rate_limit_reset,
    rate_limit_get_remaining,
    get_celery_broker_url,
    get_celery_result_backend_url,
)


# ==================== Test Class A: Connection Pool & Client Management ====================

class TestConnectionManagement:
    """Test connection pool creation and Redis client singleton pattern"""

    @pytest.mark.asyncio
    async def test_tc_a1_connection_pool_creation(self, clean_redis):
        """TC-A1: Redis connection pool creation with correct configuration"""
        pool = get_redis_pool()
        
        assert pool is not None
        assert hasattr(pool, 'max_connections')
        
        # Test singleton pattern - same pool returned
        pool2 = get_redis_pool()
        assert pool is pool2

    @pytest.mark.asyncio
    async def test_tc_a2_redis_client_singleton(self, clean_redis):
        """TC-A2: Redis client singleton pattern"""
        client1 = get_redis_client()
        client2 = get_redis_client()
        
        assert client1 is not None
        assert client1 is client2  # Same instance


# ==================== Test Class B: Lifecycle Management ====================

class TestLifecycleManagement:
    """Test Redis initialization, health checks, and shutdown"""

    @pytest.mark.asyncio
    async def test_tc_b1_init_redis_success(self, clean_redis):
        """TC-B1: Application startup with Redis initialization"""
        await init_redis()
        
        # Verify Redis is accessible
        client = get_redis_client()
        result = await client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_tc_b2_redis_health_check_pass(self, clean_redis):
        """TC-B2: Redis health check passes when Redis is available"""
        result = await check_redis_health()
        assert result is True

    @pytest.mark.asyncio
    async def test_tc_b3_redis_health_check_fail(self):
        """TC-B3: Redis health check fails when Redis is unavailable"""
        with patch('core.redis.get_redis_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.ping.side_effect = RedisConnectionError("Connection failed")
            mock_get_client.return_value = mock_client
            
            result = await check_redis_health()
            assert result is False


# ==================== Test Class C: Cache Utility Functions ====================

class TestCacheUtilities:
    """Test cache get, set, delete, and expire operations"""

    @pytest.mark.asyncio
    async def test_tc_c1_cache_get_hit(self, clean_redis):
        """TC-C1: cache_get returns value for existing key"""
        await cache_set("test:key", "test_value")
        result = await cache_get("test:key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_tc_c2_cache_get_miss(self, clean_redis):
        """TC-C2: cache_get returns None for non-existent key"""
        result = await cache_get("missing:key")
        assert result is None

    @pytest.mark.asyncio
    async def test_tc_c3_cache_set_without_expiration(self, clean_redis):
        """TC-C3: cache_set stores value without expiration"""
        result = await cache_set("persist:key", "value", expire=None)
        assert result is True
        
        # Verify value stored
        value = await cache_get("persist:key")
        assert value == "value"
        
        # Check TTL is -1 (no expiration)
        client = get_redis_client()
        ttl = await client.ttl("persist:key")
        assert ttl == -1

    @pytest.mark.asyncio
    async def test_tc_c4_cache_set_with_expiration(self, clean_redis):
        """TC-C4: cache_set stores value with expiration (TTL)"""
        result = await cache_set("temp:key", "value", expire=60)
        assert result is True
        
        # Verify value stored
        value = await cache_get("temp:key")
        assert value == "value"
        
        # Check TTL is approximately 60 seconds (allow 58-60 range)
        client = get_redis_client()
        ttl = await client.ttl("temp:key")
        assert 58 <= ttl <= 60


# ==================== Test Class D: Session Token Storage ====================

class TestSessionManagement:
    """Test session set, get, delete, and extend operations"""

    @pytest.mark.asyncio
    async def test_tc_d1_session_set_with_default_expiration(self, clean_redis):
        """TC-D1: session_set stores session with default 1-hour expiration"""
        result = await session_set("token123", '{"user_id": 1}')
        assert result is True

        # Retrieve session
        data = await session_get("token123")
        assert data == '{"user_id": 1}'

        # Check TTL is approximately 3600 seconds (default 1 hour)
        client = get_redis_client()
        ttl = await client.ttl("session:token123")
        assert 3590 <= ttl <= 3600  # Allow 10-second tolerance

    @pytest.mark.asyncio
    async def test_tc_d5_session_delete_logout(self, clean_redis):
        """TC-D5: session_delete removes session (logout)"""
        await session_set("token456", "data")

        result = await session_delete("token456")
        assert result == 1  # One key deleted

        # Verify session no longer exists
        data = await session_get("token456")
        assert data is None


# ==================== Test Class E: Rate Limiting ====================

class TestRateLimiting:
    """Test rate limiting increment, check, reset, and remaining quota"""

    @pytest.mark.asyncio
    async def test_tc_e1_rate_limit_first_request(self, clean_redis):
        """TC-E1: rate_limit_increment creates counter on first request"""
        count = await rate_limit_increment("192.168.1.1", window_seconds=60)
        assert count == 1

        # Check TTL is approximately 60 seconds
        client = get_redis_client()
        ttl = await client.ttl("ratelimit:192.168.1.1")
        assert 58 <= ttl <= 60

    @pytest.mark.asyncio
    async def test_tc_e2_rate_limit_increment_existing(self, clean_redis):
        """TC-E2: rate_limit_increment increments existing counter"""
        count1 = await rate_limit_increment("192.168.1.2", 60)
        assert count1 == 1

        count2 = await rate_limit_increment("192.168.1.2", 60)
        assert count2 == 2

    @pytest.mark.asyncio
    async def test_tc_e4_rate_limit_check_allow(self, clean_redis):
        """TC-E4: rate_limit_check allows requests under limit"""
        # Make 5 requests
        for _ in range(5):
            await rate_limit_increment("user123", 60)

        allowed = await rate_limit_check("user123", max_requests=10)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_tc_e5_rate_limit_check_block(self, clean_redis):
        """TC-E5: rate_limit_check blocks requests over limit"""
        # Make 10 requests
        for _ in range(10):
            await rate_limit_increment("user456", 60)

        allowed = await rate_limit_check("user456", max_requests=10)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_tc_e7_rate_limit_get_remaining(self, clean_redis):
        """TC-E7: rate_limit_get_remaining calculates correct remaining quota"""
        # Make 7 requests
        for _ in range(7):
            await rate_limit_increment("api_client", 60)

        remaining = await rate_limit_get_remaining("api_client", max_requests=10)
        assert remaining == 3

    @pytest.mark.asyncio
    async def test_tc_e9_rate_limit_counter_expires(self, clean_redis):
        """TC-E9: Rate limit counter expires after window"""
        # Increment with short window
        count1 = await rate_limit_increment("temp", window_seconds=2)
        assert count1 == 1

        # Wait for expiration
        await asyncio.sleep(3)

        # Counter should reset
        count2 = await rate_limit_increment("temp", window_seconds=60)
        assert count2 == 1


# ==================== Test Class F: Celery Integration ====================

class TestCeleryIntegration:
    """Test Celery broker and result backend URL generation"""

    @pytest.mark.asyncio
    async def test_tc_f1_celery_broker_url(self):
        """TC-F1: get_celery_broker_url returns Redis URL for db 1"""
        url = get_celery_broker_url()
        assert url.endswith("/1")

    @pytest.mark.asyncio
    async def test_tc_f2_celery_result_backend_url(self):
        """TC-F2: get_celery_result_backend_url returns Redis URL for db 2"""
        url = get_celery_result_backend_url()
        assert url.endswith("/2")


# ==================== Test Class H: FastAPI Integration ====================

class TestFastAPIIntegration:
    """Test /ready endpoint Redis health integration"""

    @pytest.mark.asyncio
    async def test_tc_h1_ready_endpoint_healthy_redis(self, test_client):
        """TC-H1: /ready endpoint returns 200 when Redis is healthy"""
        from unittest.mock import AsyncMock

        with patch('main.check_redis_health', new_callable=AsyncMock, return_value=True):
            with patch('main.check_db_health', new_callable=AsyncMock, return_value=True):
                response = test_client.get("/ready")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ready"
                assert data["redis"] == "connected"

    @pytest.mark.asyncio
    async def test_tc_h2_ready_endpoint_unhealthy_redis(self, test_client):
        """TC-H2: /ready endpoint returns 503 when Redis is unhealthy"""
        from unittest.mock import AsyncMock

        with patch('main.check_redis_health', new_callable=AsyncMock, return_value=False):
            with patch('main.check_db_health', new_callable=AsyncMock, return_value=True):
                response = test_client.get("/ready")

                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "not ready"
                assert data["redis"] == "disconnected"

