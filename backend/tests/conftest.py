"""
Pytest configuration and fixtures for backend tests.

⚠️ CRITICAL: Set EMBEDDING_MODEL environment variable BEFORE any imports
to prevent SSL certificate errors during EmbeddingService module loading.
"""

import os

# CRITICAL: Set this BEFORE importing any app modules
os.environ['EMBEDDING_MODEL'] = 'openai'

import sys
from pathlib import Path

# Add src directory to Python path
backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def test_env_vars():
    """Set up test environment variables."""
    test_vars = {
        "PROJECT_NAME": "ChatApp Test",
        "ENVIRONMENT": "development",
        "API_V1_PREFIX": "/api/v1",
        "DEBUG": "true",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/chatapp_test",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-minimum-32-characters-long-for-jwt",
        "ALGORITHM": "HS256",
        "OPENAI_API_KEY": "sk-test-key-1234567890",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "text",
    }
    
    # Set environment variables
    for key, value in test_vars.items():
        os.environ[key] = value
    
    yield test_vars
    
    # Cleanup (optional - tests usually don't need cleanup for env vars)


@pytest.fixture(scope="module")
def app(test_env_vars):
    """Create FastAPI application instance for testing."""
    # Import after environment variables are set
    from main import app
    return app


@pytest.fixture(scope="module")
def client(app):
    """Create TestClient for making requests to the app."""
    return TestClient(app)


@pytest.fixture(scope="module")
def test_client(app):
    """Alias for client fixture - used in some tests."""
    return TestClient(app)


# ==================== Redis Test Fixtures ====================

@pytest_asyncio.fixture(scope="function")
async def redis_client():
    """
    Provide fake Redis client for testing.

    Uses fakeredis to provide an in-memory Redis instance for fast,
    isolated tests without requiring a real Redis server.
    """
    import fakeredis.aioredis as fakeredis_async

    # Create FakeRedis client
    client = fakeredis_async.FakeRedis(
        decode_responses=True
    )

    yield client

    # Cleanup
    try:
        await client.flushall()
    except:
        pass
    await client.aclose()


@pytest_asyncio.fixture(scope="function")
async def clean_redis(redis_client, monkeypatch):
    """
    Provide clean Redis instance for each test.

    This fixture:
    1. Flushes all data before the test
    2. Patches get_redis_client to use the fake Redis client
    3. Ensures test isolation
    """
    # Clear all data
    await redis_client.flushall()

    # Patch get_redis_client to return our fake client
    import core.redis
    monkeypatch.setattr(core.redis, '_redis_client', redis_client)

    # Also patch get_redis_client function directly
    def mock_get_redis_client():
        return redis_client

    monkeypatch.setattr(core.redis, 'get_redis_client', mock_get_redis_client)

    yield redis_client

    # Cleanup after test
    await redis_client.flushall()


# ==================== Database Test Fixtures ====================

@pytest_asyncio.fixture(scope='function')
async def engine():
    """Create test database engine - fresh for each test."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )

    yield test_engine

    await test_engine.dispose()


@pytest_asyncio.fixture(scope='function')
async def db_session(engine):
    """Create test database session - fresh for each test."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from models.base import Base

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    # Create session factory
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Provide session
    async with async_session() as session:
        yield session

    # Cleanup: Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope='function')
async def session(db_session):
    """Alias for db_session fixture - used in auth tests."""
    return db_session


# ==================== User Test Fixtures ====================

@pytest_asyncio.fixture(scope='function')
async def admin_user(session):
    """Create admin user for testing."""
    from models.user import User, UserRole
    from core.security import hash_password

    # Create admin user
    user = User(
        email="admin@test.com",
        password_hash=hash_password("Admin123!@#"),
        role=UserRole.ADMIN,
        is_active=True
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@pytest_asyncio.fixture(scope='function')
async def regular_user(session):
    """Create regular user for testing."""
    from models.user import User, UserRole
    from core.security import hash_password

    # Create regular user
    user = User(
        email="user@test.com",
        password_hash=hash_password("User123!@#"),
        role=UserRole.USER,
        is_active=True
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@pytest_asyncio.fixture(scope='function')
async def inactive_user(session):
    """Create inactive user for testing."""
    from models.user import User, UserRole
    from core.security import hash_password

    # Create inactive user
    user = User(
        email="inactive@test.com",
        password_hash=hash_password("Test123!@#"),
        role=UserRole.USER,
        is_active=False
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user
