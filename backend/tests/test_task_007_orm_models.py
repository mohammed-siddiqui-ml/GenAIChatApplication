"""
Test suite for Task 007: SQLAlchemy ORM Models

This test file validates all ORM models, relationships, enums, and database operations
for the GenAI Knowledge Retrieval System.
"""
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from pathlib import Path
import sys

# Add src directory to path
backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

# Import all models and utilities
from models import (
    Base, to_dict,
    User, UserRole,
    ChatSession, ChatMessage, MessageRole,
    DataSource, IngestionJob, DataSourceType, JobStatus,
    KnowledgeDocument, DocumentEmbedding, ContentType,
    AuditLog
)


# Fixtures for async database testing
@pytest_asyncio.fixture(scope='function')
async def engine():
    """Create test database engine - fresh for each test"""
    from sqlalchemy import event
    from sqlalchemy.schema import DDL

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )

    # Enable foreign key constraints for SQLite (CRITICAL for cascade behaviors)
    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # CRITICAL FIX: Manually create tables with proper AUTOINCREMENT for BigInteger columns
    # SQLite requires INTEGER PRIMARY KEY for auto-increment, but our models use BIGINT
    # We need to recreate tables that use BigInteger with proper autoincrement
    async with test_engine.begin() as conn:
        # Enable foreign keys for this connection
        await conn.execute(text("PRAGMA foreign_keys=ON"))

        # Create all tables first
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

        # Drop and recreate tables with BIGINT autoincrement issues
        # List of tables that have BigInteger primary keys
        tables_to_fix = [
            ('chat_messages', '''
                CREATE TABLE chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(36) NOT NULL,
                    role VARCHAR(9) NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    embedding JSON,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE,
                    CONSTRAINT message_role CHECK (role IN ('USER', 'ASSISTANT', 'SYSTEM'))
                )
            '''),
            ('knowledge_documents', '''
                CREATE TABLE knowledge_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_source_id INTEGER NOT NULL,
                    external_id VARCHAR(255),
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_type VARCHAR(17) NOT NULL,
                    url TEXT,
                    metadata JSON,
                    document_hash TEXT,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    is_deleted BOOLEAN DEFAULT 'false' NOT NULL,
                    tsvector_content TEXT,
                    FOREIGN KEY(data_source_id) REFERENCES data_sources (id) ON DELETE CASCADE,
                    CONSTRAINT content_type CHECK (content_type IN ('PAGE', 'ISSUE', 'DOCUMENT', 'VIDEO_TRANSCRIPT'))
                )
            '''),
            ('document_embeddings', '''
                CREATE TABLE document_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding TEXT,
                    token_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES knowledge_documents (id) ON DELETE CASCADE
                )
            '''),
            ('audit_logs', '''
                CREATE TABLE audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    resource_type TEXT,
                    resource_id INTEGER,
                    changes JSON,
                    ip_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
                )
            '''),
            ('ingestion_jobs', '''
                CREATE TABLE ingestion_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_source_id INTEGER NOT NULL,
                    status VARCHAR(7) NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    documents_processed INTEGER DEFAULT '0',
                    documents_failed INTEGER DEFAULT '0',
                    error_message TEXT,
                    metadata JSON,
                    FOREIGN KEY(data_source_id) REFERENCES data_sources (id) ON DELETE CASCADE,
                    CONSTRAINT job_status CHECK (status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED'))
                )
            '''),
        ]

        for table_name, create_sql in tables_to_fix:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
            await conn.execute(text(create_sql))

    yield test_engine

    # Cleanup after each test to prevent schema persistence
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture(scope='function')
async def session(engine):
    """Create test session - fresh for each test"""
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


# TC-001: Verify All Models Are Registered
class TestModelStructure:
    """Test model structure and registration"""
    
    def test_all_models_registered(self):
        """Verify all 8 models are registered in Base.metadata"""
        table_names = set(Base.metadata.tables.keys())
        expected_tables = {
            'users', 'chat_sessions', 'chat_messages', 'data_sources',
            'ingestion_jobs', 'knowledge_documents', 'document_embeddings', 'audit_logs'
        }
        assert table_names == expected_tables, f"Missing or extra tables. Got: {table_names}"
    
    def test_user_model_columns(self):
        """Verify User model has correct columns"""
        user_table = Base.metadata.tables['users']
        column_names = {col.name for col in user_table.columns}
        
        expected_columns = {'id', 'email', 'password_hash', 'role', 'is_active', 'created_at', 'updated_at'}
        assert expected_columns.issubset(column_names), f"Missing columns in users table"
        
        # Verify unique constraint on email
        assert user_table.c.email.unique, "email should have unique constraint"
    
    def test_enum_definitions(self):
        """Verify all enums are correctly defined"""
        # UserRole enum
        assert hasattr(UserRole, 'ADMIN')
        assert hasattr(UserRole, 'USER')
        assert UserRole.ADMIN.value == 'admin'
        assert UserRole.USER.value == 'user'
        
        # MessageRole enum
        assert hasattr(MessageRole, 'USER')
        assert hasattr(MessageRole, 'ASSISTANT')
        assert hasattr(MessageRole, 'SYSTEM')
        
        # DataSourceType enum
        assert hasattr(DataSourceType, 'CONFLUENCE')
        assert hasattr(DataSourceType, 'JIRA')
        assert hasattr(DataSourceType, 'ONBOARDING')
        assert hasattr(DataSourceType, 'CUSTOM')
        
        # JobStatus enum
        assert hasattr(JobStatus, 'PENDING')
        assert hasattr(JobStatus, 'RUNNING')
        assert hasattr(JobStatus, 'SUCCESS')
        assert hasattr(JobStatus, 'FAILED')
        
        # ContentType enum
        assert hasattr(ContentType, 'PAGE')
        assert hasattr(ContentType, 'ISSUE')
        assert hasattr(ContentType, 'DOCUMENT')
        assert hasattr(ContentType, 'VIDEO_TRANSCRIPT')


# TC-007 & TC-002: Test User Model Methods
class TestModelMethods:
    """Test model instance methods"""
    
    def test_user_has_role(self):
        """Test User.has_role() method"""
        admin_user = User(email="admin@test.com", password_hash="hash123", role=UserRole.ADMIN)
        regular_user = User(email="user@test.com", password_hash="hash456", role=UserRole.USER)
        
        assert admin_user.has_role(UserRole.ADMIN) is True
        assert admin_user.has_role(UserRole.USER) is False
        assert regular_user.has_role(UserRole.USER) is True
        assert regular_user.has_role(UserRole.ADMIN) is False
    
    def test_user_is_admin(self):
        """Test User.is_admin() method"""
        admin_user = User(email="admin@test.com", password_hash="hash123", role=UserRole.ADMIN)
        regular_user = User(email="user@test.com", password_hash="hash456", role=UserRole.USER)

        assert admin_user.is_admin() is True
        assert regular_user.is_admin() is False

    def test_ingestion_job_is_complete(self):
        """Test IngestionJob.is_complete() method"""
        from models.data_source import IngestionJob

        success_job = IngestionJob(data_source_id=1, status=JobStatus.SUCCESS)
        failed_job = IngestionJob(data_source_id=1, status=JobStatus.FAILED)
        running_job = IngestionJob(data_source_id=1, status=JobStatus.RUNNING)
        pending_job = IngestionJob(data_source_id=1, status=JobStatus.PENDING)

        assert success_job.is_complete() is True
        assert failed_job.is_complete() is True
        assert running_job.is_complete() is False
        assert pending_job.is_complete() is False

    def test_ingestion_job_is_running(self):
        """Test IngestionJob.is_running() method"""
        from models.data_source import IngestionJob

        running_job = IngestionJob(data_source_id=1, status=JobStatus.RUNNING)
        success_job = IngestionJob(data_source_id=1, status=JobStatus.SUCCESS)

        assert running_job.is_running() is True
        assert success_job.is_running() is False

    def test_to_dict_utility(self):
        """Test to_dict() utility function"""
        user = User(email="test@test.com", password_hash="hash123", role=UserRole.USER, is_active=True)
        user.id = 1  # Manually set ID for testing

        user_dict = to_dict(user)

        assert isinstance(user_dict, dict)
        assert 'id' in user_dict
        assert 'email' in user_dict
        assert 'password_hash' in user_dict
        assert 'role' in user_dict
        assert 'is_active' in user_dict
        assert user_dict['email'] == 'test@test.com'


# TC-020: Test Async Database Operations
class TestAsyncDatabaseOperations:
    """Test async database operations with models"""

    @pytest.mark.asyncio
    async def test_create_user(self, session):
        """Test creating a user in the database"""
        user = User(
            email="admin@test.com",
            password_hash="hashed_password_123",
            role=UserRole.ADMIN,
            is_active=True
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        assert user.id is not None
        assert user.email == "admin@test.com"
        assert user.role == UserRole.ADMIN
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_chat_session_anonymous(self, session):
        """Test creating an anonymous chat session"""
        from models.chat import ChatSession

        chat_session = ChatSession(
            user_id=None,
            session_token="anon_token_12345",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Test Browser"
        )

        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)

        assert chat_session.id is not None  # UUID should be auto-generated
        assert chat_session.user_id is None
        assert chat_session.session_token == "anon_token_12345"
        assert chat_session.started_at is not None
        assert chat_session.last_activity_at is not None

    @pytest.mark.asyncio
    async def test_create_chat_message_with_metadata(self, session):
        """Test creating a chat message with JSONB metadata"""
        from models.chat import ChatSession, ChatMessage

        # First create a chat session
        chat_session = ChatSession(
            user_id=None,
            session_token="test_token_123",
            ip_address="127.0.0.1",
            user_agent="Test Agent"
        )
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)

        # Create a message with metadata
        message = ChatMessage(
            session_id=chat_session.id,
            role=MessageRole.USER,
            content="What is the onboarding process?",
            message_metadata={
                "sources": ["doc1", "doc2"],
                "token_count": 42
            }
        )

        session.add(message)
        await session.commit()
        await session.refresh(message)

        assert message.id is not None
        assert message.role == MessageRole.USER
        assert message.content == "What is the onboarding process?"
        assert message.message_metadata == {"sources": ["doc1", "doc2"], "token_count": 42}
        assert message.created_at is not None

    @pytest.mark.asyncio
    async def test_create_data_source_with_config(self, session):
        """Test creating a data source with JSONB config"""
        # First create a user
        user = User(email="admin@test.com", password_hash="hash123", role=UserRole.ADMIN)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create data source
        data_source = DataSource(
            name="Engineering Confluence",
            type=DataSourceType.CONFLUENCE,
            source_config={
                "url": "https://confluence.example.com",
                "space_keys": ["ENG", "PROD"]
            },
            is_active=True,
            sync_schedule="0 0 * * *",
            created_by=user.id
        )

        session.add(data_source)
        await session.commit()
        await session.refresh(data_source)

        assert data_source.id is not None
        assert data_source.name == "Engineering Confluence"
        assert data_source.type == DataSourceType.CONFLUENCE
        assert data_source.source_config == {
            "url": "https://confluence.example.com",
            "space_keys": ["ENG", "PROD"]
        }
        assert data_source.created_by == user.id

    @pytest.mark.asyncio
    async def test_create_knowledge_document(self, session):
        """Test creating a knowledge document"""
        # Create user and data source first
        user = User(email="admin@test.com", password_hash="hash123", role=UserRole.ADMIN)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        data_source = DataSource(
            name="Test Source",
            type=DataSourceType.CONFLUENCE,
            source_config={},
            created_by=user.id
        )
        session.add(data_source)
        await session.commit()
        await session.refresh(data_source)

        # Create knowledge document
        doc = KnowledgeDocument(
            data_source_id=data_source.id,
            external_id="CONF-12345",
            title="Onboarding Guide",
            content="Welcome to the company...",
            content_type=ContentType.PAGE,
            url="https://confluence.example.com/page/12345",
            doc_metadata={
                "author": "John Doe",
                "tags": ["onboarding", "hr"]
            },
            document_hash="abc123def456",
            is_deleted=False
        )

        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        assert doc.id is not None
        assert doc.title == "Onboarding Guide"
        assert doc.content_type == ContentType.PAGE
        assert doc.doc_metadata == {"author": "John Doe", "tags": ["onboarding", "hr"]}
        assert doc.indexed_at is not None

    @pytest.mark.asyncio
    async def test_create_audit_log(self, session):
        """Test creating an audit log entry"""
        # Create user first
        user = User(email="admin@test.com", password_hash="hash123", role=UserRole.ADMIN)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            action="create_data_source",
            resource_type="data_source",
            resource_id=5,
            audit_changes={
                "before": None,
                "after": {"name": "New Source", "type": "confluence"}
            },
            ip_address="10.0.0.5"
        )

        session.add(audit)
        await session.commit()
        await session.refresh(audit)

        assert audit.id is not None
        assert audit.user_id == user.id
        assert audit.action == "create_data_source"
        assert audit.audit_changes == {
            "before": None,
            "after": {"name": "New Source", "type": "confluence"}
        }
        assert audit.created_at is not None


# TC-015, TC-016: Test Relationships and Cascades
class TestRelationships:
    """Test model relationships and cascade behaviors"""

    @pytest.mark.asyncio
    async def test_user_to_chat_sessions_relationship(self, session):
        """Test User to ChatSessions bidirectional relationship"""
        from models.chat import ChatSession
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        # Create user
        user = User(email="test@test.com", password_hash="hash123", role=UserRole.USER)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create 3 chat sessions
        for i in range(3):
            chat_session = ChatSession(
                user_id=user.id,
                session_token=f"token_{i}",
                ip_address="127.0.0.1",
                user_agent="Test Agent"
            )
            session.add(chat_session)

        await session.commit()

        # Refresh user with chat_sessions relationship loaded
        # This is the proper async pattern for loading relationships
        await session.refresh(user, ['chat_sessions'])

        assert len(user.chat_sessions) == 3
        assert all(s.user_id == user.id for s in user.chat_sessions)

    @pytest.mark.asyncio
    async def test_chat_session_cascade_delete_messages(self, session):
        """Test ChatSession cascade deletes ChatMessages"""
        from models.chat import ChatSession, ChatMessage
        from sqlalchemy import select

        # Create chat session
        chat_session = ChatSession(
            user_id=None,
            session_token="test_token",
            ip_address="127.0.0.1",
            user_agent="Test"
        )
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)

        # Create 5 messages
        for i in range(5):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            message = ChatMessage(
                session_id=chat_session.id,
                role=role,
                content=f"Message {i}",
                message_metadata={}
            )
            session.add(message)

        await session.commit()

        # Verify 5 messages exist
        result = await session.execute(select(ChatMessage))
        messages_before = result.scalars().all()
        assert len(messages_before) == 5

        # Delete chat session
        await session.delete(chat_session)
        await session.commit()

        # Verify messages are cascade deleted
        result = await session.execute(select(ChatMessage))
        messages_after = result.scalars().all()
        assert len(messages_after) == 0

    @pytest.mark.asyncio
    async def test_data_source_set_null_on_user_delete(self, session):
        """Test DataSource.created_by set to NULL when User is deleted"""
        from sqlalchemy import select

        # Create user
        user = User(email="admin@test.com", password_hash="hash123", role=UserRole.ADMIN)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create data source
        data_source = DataSource(
            name="Test Source",
            type=DataSourceType.CONFLUENCE,
            source_config={},
            created_by=user.id
        )
        session.add(data_source)
        await session.commit()
        await session.refresh(data_source)

        data_source_id = data_source.id

        # Delete user
        await session.delete(user)
        await session.commit()

        # Expire all objects to force fresh query from database
        session.expire_all()

        # Verify data source still exists but created_by is NULL
        result = await session.execute(select(DataSource).where(DataSource.id == data_source_id))
        data_source_after = result.scalar_one()
        assert data_source_after.created_by is None

    @pytest.mark.asyncio
    async def test_data_source_cascade_delete_ingestion_jobs(self, session):
        """Test DataSource cascade deletes IngestionJobs"""
        from sqlalchemy import select

        # Create user and data source
        user = User(email="admin@test.com", password_hash="hash123", role=UserRole.ADMIN)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        data_source = DataSource(
            name="Test Source",
            type=DataSourceType.CONFLUENCE,
            source_config={},
            created_by=user.id
        )
        session.add(data_source)
        await session.commit()
        await session.refresh(data_source)

        # Create ingestion job
        job = IngestionJob(
            data_source_id=data_source.id,
            status=JobStatus.PENDING,
            documents_processed=0,
            documents_failed=0
        )
        session.add(job)
        await session.commit()

        # Verify job exists
        result = await session.execute(select(IngestionJob))
        jobs_before = result.scalars().all()
        assert len(jobs_before) == 1

        # Delete data source
        await session.delete(data_source)
        await session.commit()

        # Verify job is cascade deleted
        result = await session.execute(select(IngestionJob))
        jobs_after = result.scalars().all()
        assert len(jobs_after) == 0
