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
    """
    Create test database engine - fresh for each test.

    CRITICAL: Uses function scope with checkfirst=True and proper cleanup
    to prevent "index/table already exists" errors in SQLAlchemy async tests.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy import Integer, BigInteger, event
    from models.base import Base

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )

    # CRITICAL: Enable foreign key constraints in SQLite
    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # CRITICAL: Replace BigInteger with Integer for SQLite compatibility
    # SQLite doesn't auto-increment BIGINT columns, only INTEGER PRIMARY KEY
    async with test_engine.begin() as conn:
        def create_tables_sqlite_compat(connection):
            """Create tables with BigInteger->Integer replacement for SQLite."""
            for table in Base.metadata.sorted_tables:
                for column in table.columns:
                    # Replace BigInteger with Integer for primary key autoincrement support
                    if isinstance(column.type, BigInteger) and column.primary_key:
                        column.type = Integer()
            Base.metadata.create_all(connection, checkfirst=True)

        await conn.run_sync(create_tables_sqlite_compat)

    yield test_engine

    # CRITICAL: Cleanup to prevent schema persistence across tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture(scope='function')
async def db_session(engine):
    """
    Create test database session - fresh for each test.

    Tables are already created by the engine fixture, so this just
    provides a session for interacting with the database.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    # Create session factory
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Provide session
    async with async_session() as session:
        yield session
        # Session cleanup handled by context manager


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


# ==================== Mock OpenAI Fixtures ====================

@pytest.fixture(scope="function")
def mock_openai_responses():
    """
    Provide mock responses for OpenAI API calls.

    Returns a dictionary with common mock responses that can be used
    in tests to avoid making real API calls.
    """
    return {
        "embedding": [0.1] * 1536,  # Mock embedding vector (1536 dimensions for text-embedding-ada-002)
        "chat_completion": {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a test response from the AI assistant."
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        },
        "chat_completion_stream": [
            {"choices": [{"delta": {"role": "assistant"}, "index": 0}]},
            {"choices": [{"delta": {"content": "This "}, "index": 0}]},
            {"choices": [{"delta": {"content": "is "}, "index": 0}]},
            {"choices": [{"delta": {"content": "a "}, "index": 0}]},
            {"choices": [{"delta": {"content": "test."}, "index": 0}]},
            {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}
        ]
    }


@pytest.fixture(scope="function")
def mock_openai_client(monkeypatch, mock_openai_responses):
    """
    Mock OpenAI client to avoid making real API calls.

    This patches the OpenAI client methods with mock responses.
    """
    from unittest.mock import AsyncMock, MagicMock

    async def mock_create_embedding(*args, **kwargs):
        """Mock embedding generation."""
        return mock_openai_responses["embedding"]

    async def mock_create_completion(*args, **kwargs):
        """Mock chat completion."""
        return mock_openai_responses["chat_completion"]

    async def mock_create_streaming_completion(*args, **kwargs):
        """Mock streaming chat completion."""
        for chunk in mock_openai_responses["chat_completion_stream"]:
            yield chunk

    # Create mock client
    from integrations.openai_client import OpenAIClient

    mock_client = MagicMock(spec=OpenAIClient)
    mock_client.create_embedding = AsyncMock(side_effect=mock_create_embedding)
    mock_client.create_completion = AsyncMock(side_effect=mock_create_completion)
    mock_client.create_streaming_completion = mock_create_streaming_completion

    return mock_client


# ==================== Data Source Test Fixtures ====================

@pytest_asyncio.fixture(scope='function')
async def confluence_data_source(session):
    """Create a Confluence data source for testing."""
    from models.data_source import DataSource, DataSourceType
    from utils.crypto import encrypt_config_dict

    config = {
        "url": "https://confluence.example.com",
        "username": "test_user",
        "api_token": "test_token_123",
        "space_key": "TEST"
    }

    sensitive_fields = ["api_token", "password", "api_key"]
    encrypted_config = encrypt_config_dict(config, sensitive_fields)

    data_source = DataSource(
        name="Test Confluence",
        type=DataSourceType.CONFLUENCE,
        source_config=encrypted_config,
        sync_schedule="0 0 * * *",  # Daily at midnight
        is_active=True
    )

    session.add(data_source)
    await session.commit()
    await session.refresh(data_source)

    return data_source


@pytest_asyncio.fixture(scope='function')
async def jira_data_source(session):
    """Create a JIRA data source for testing."""
    from models.data_source import DataSource, DataSourceType
    from utils.crypto import encrypt_config_dict

    config = {
        "url": "https://jira.example.com",
        "username": "test_user",
        "api_token": "test_token_456",
        "project_key": "PROJ"
    }

    sensitive_fields = ["api_token", "password", "api_key"]
    encrypted_config = encrypt_config_dict(config, sensitive_fields)

    data_source = DataSource(
        name="Test JIRA",
        type=DataSourceType.JIRA,
        source_config=encrypted_config,
        sync_schedule="0 */6 * * *",  # Every 6 hours
        is_active=True
    )

    session.add(data_source)
    await session.commit()
    await session.refresh(data_source)

    return data_source


# ==================== Chat Session Test Fixtures ====================

@pytest_asyncio.fixture(scope='function')
async def chat_session(session):
    """Create a chat session for testing."""
    from models.chat import ChatSession
    import secrets

    chat_session_obj = ChatSession(
        session_token=secrets.token_urlsafe(32),
        user_id=None  # Anonymous session
    )

    session.add(chat_session_obj)
    await session.commit()
    await session.refresh(chat_session_obj)

    return chat_session_obj


@pytest_asyncio.fixture(scope='function')
async def chat_session_with_messages(session, chat_session):
    """Create a chat session with sample messages."""
    from models.chat import ChatMessage, MessageRole

    # Add user message
    user_msg = ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.USER,
        content="What is the onboarding process?"
    )
    session.add(user_msg)

    # Add assistant message
    assistant_msg = ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.ASSISTANT,
        content="The onboarding process includes...",
        message_metadata={
            "sources": [{
                "document_id": 1,
                "title": "Onboarding Guide",
                "url": "https://example.com/onboarding"
            }]
        }
    )
    session.add(assistant_msg)

    await session.commit()

    return chat_session


# ==================== Knowledge Document Fixtures ====================

@pytest_asyncio.fixture(scope='function')
async def knowledge_documents(session, confluence_data_source):
    """Create sample knowledge documents for testing."""
    from models.knowledge import KnowledgeDocument, ContentType

    docs = []

    # Document 1
    doc1 = KnowledgeDocument(
        data_source_id=confluence_data_source.id,
        external_id="page-123",
        title="Getting Started Guide",
        content="This is a comprehensive guide to getting started with the platform.",
        content_type=ContentType.PAGE,  # Fixed: Use PAGE instead of CONFLUENCE_PAGE
        url="https://confluence.example.com/display/TEST/getting-started",
        metadata_={"space": "TEST", "author": "admin"}
    )
    docs.append(doc1)

    # Document 2
    doc2 = KnowledgeDocument(
        data_source_id=confluence_data_source.id,
        external_id="page-456",
        title="FAQ",
        content="Frequently asked questions and answers.",
        content_type=ContentType.PAGE,  # Fixed: Use PAGE instead of CONFLUENCE_PAGE
        url="https://confluence.example.com/display/TEST/faq",
        metadata_={"space": "TEST", "author": "support"}
    )
    docs.append(doc2)

    for doc in docs:
        session.add(doc)

    await session.commit()

    for doc in docs:
        await session.refresh(doc)

    return docs


@pytest_asyncio.fixture(scope='function')
async def document_embeddings(session, knowledge_documents):
    """Create sample document embeddings for testing."""
    from models.knowledge import DocumentEmbedding
    import numpy as np

    embeddings = []

    for i, doc in enumerate(knowledge_documents):
        # Create a mock embedding vector
        embedding_vector = np.random.rand(1536).tolist()

        emb = DocumentEmbedding(
            document_id=doc.id,
            chunk_index=0,
            chunk_text=doc.content[:500],  # First 500 chars as chunk
            embedding=embedding_vector,
            token_count=100
        )
        embeddings.append(emb)
        session.add(emb)

    await session.commit()

    for emb in embeddings:
        await session.refresh(emb)

    return embeddings


# ==================== Celery Mock Fixtures ====================

@pytest.fixture(scope="function")
def mock_celery_task():
    """Mock Celery task for testing without requiring Redis/broker."""
    from unittest.mock import MagicMock

    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="test-task-id-123")
    mock_task.apply_async.return_value = MagicMock(id="test-task-id-456")

    return mock_task
