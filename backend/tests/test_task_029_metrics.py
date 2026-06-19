"""
Tests for Task-029: System Metrics and Monitoring Endpoints

Tests cover:
- MetricsService methods
- Admin metrics endpoint
- Authentication/authorization
- Edge cases (empty database, null values)
- Response schema validation
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport

from models.knowledge import KnowledgeDocument, ContentType
from models.chat import ChatSession, ChatMessage, MessageRole
from models.data_source import DataSource, DataSourceType, IngestionJob, JobStatus
from models.user import User, UserRole
from services.metrics_service import MetricsService, MetricsServiceError
from schemas.admin import SystemMetricsResponse
from core.security import hash_password


# ========== Test Data ==========
ADMIN_EMAIL = "admin@example.com"
REGULAR_EMAIL = "regular@example.com"
TEST_PASSWORD = "SecurePass123!"


# ========== Fixtures ==========

@pytest_asyncio.fixture
async def async_client(app, session):
    """Create async HTTP client for API testing."""
    from core.database import get_db

    async def override_get_db():
        yield session

    from main import app as main_app
    main_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    main_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_admin_user(session: AsyncSession):
    """Create an admin user for testing."""
    user = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_regular_user(session: AsyncSession):
    """Create a regular user for testing."""
    user = User(
        email=REGULAR_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.USER,
        is_active=True
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(async_client: AsyncClient, test_admin_user):
    """Get admin JWT token."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def regular_token(async_client: AsyncClient, test_regular_user):
    """Get regular user JWT token."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": REGULAR_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def test_data_source(session: AsyncSession, test_admin_user):
    """Create a test data source for knowledge documents and ingestion jobs."""
    data_source = DataSource(
        name="Test Confluence",
        type=DataSourceType.CONFLUENCE,
        is_active=True,
        created_by=test_admin_user.id
    )
    session.add(data_source)
    await session.commit()
    await session.refresh(data_source)
    return data_source


# ============================================================================
# TC-001: Get Metrics - Full Database
# ============================================================================

@pytest.mark.asyncio
async def test_get_metrics_full_database(async_client: AsyncClient, session, test_admin_user, test_data_source, admin_token):
    """TC-001: Test metrics retrieval with complete data."""
    # Create sample data
    now = datetime.utcnow()

    # Create documents (100 total: 90 active, 10 deleted)
    for i in range(90):
        doc = KnowledgeDocument(
            data_source_id=test_data_source.id,
            title=f"Active Doc {i}",
            content=f"Content {i}",
            content_type=ContentType.PAGE,
            external_id=f"page-{i}",
            is_deleted=False,
            indexed_at=now
        )
        session.add(doc)

    for i in range(10):
        doc = KnowledgeDocument(
            data_source_id=test_data_source.id,
            title=f"Deleted Doc {i}",
            content=f"Content {i}",
            content_type=ContentType.PAGE,
            external_id=f"page-del-{i}",
            is_deleted=True,
            indexed_at=now
        )
        session.add(doc)

    # Create chat sessions (50 total: 40 active, 10 ended)
    for i in range(40):
        sess = ChatSession(
            user_id=test_admin_user.id,
            session_token=f"active-session-{i}",
            started_at=now,
            ended_at=None
        )
        session.add(sess)

    for i in range(10):
        sess = ChatSession(
            user_id=test_admin_user.id,
            session_token=f"ended-session-{i}",
            started_at=now - timedelta(days=1),
            ended_at=now
        )
        session.add(sess)

    await session.commit()

    # Get first session for messages
    result = await session.execute(select(ChatSession).limit(1))
    first_session = result.scalar_one()

    # Create chat messages (200 total: 100 user, 100 assistant with duration_ms)
    for i in range(100):
        # User message
        user_msg = ChatMessage(
            session_id=first_session.id,
            role=MessageRole.USER,
            content=f"Query {i}",
            created_at=now - timedelta(minutes=i),
            message_metadata={}
        )
        session.add(user_msg)

        # Assistant message with duration_ms
        assistant_msg = ChatMessage(
            session_id=first_session.id,
            role=MessageRole.ASSISTANT,
            content=f"Response {i}",
            created_at=now - timedelta(minutes=i) + timedelta(seconds=1),
            message_metadata={"duration_ms": 1000 + (i % 500)}  # Range: 1000-1500ms
        )
        session.add(assistant_msg)

    # Create ingestion jobs (20 total: 18 successful, 2 failed)
    for i in range(18):
        job = IngestionJob(
            data_source_id=test_data_source.id,
            status=JobStatus.SUCCESS,
            started_at=now - timedelta(hours=i),
            completed_at=now - timedelta(hours=i) + timedelta(minutes=5)
        )
        session.add(job)

    for i in range(2):
        job = IngestionJob(
            data_source_id=test_data_source.id,
            status=JobStatus.FAILED,
            started_at=now - timedelta(hours=i),
            completed_at=now - timedelta(hours=i) + timedelta(minutes=2),
            error_message="Test error"
        )
        session.add(job)

    await session.commit()

    # Make API request
    response = await async_client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Verify document metrics
    assert data["total_documents"] == 100
    assert data["active_documents"] == 90

    # Verify session metrics
    assert data["sessions"]["total_all_time"] == 50
    assert data["sessions"]["active_sessions"] == 40

    # Verify query metrics exist
    assert "queries" in data
    assert data["queries"]["total_all_time"] == 100

    # Verify average response time is calculated
    assert data["average_response_time_ms"] is not None
    assert isinstance(data["average_response_time_ms"], (int, float))
    assert data["average_response_time_ms"] > 0

    # Verify ingestion metrics
    assert data["ingestion"]["total_jobs"] == 20
    assert data["ingestion"]["successful_jobs"] == 18
    assert data["ingestion"]["failed_jobs"] == 2
    assert data["ingestion"]["success_rate"] == 90.0

    # Verify timestamp exists
    assert "timestamp" in data
    assert data["timestamp"] is not None


# ============================================================================
# TC-002: Get Metrics - Empty Database
# ============================================================================

@pytest.mark.asyncio
async def test_get_metrics_empty_database(async_client: AsyncClient, session, test_admin_user, admin_token):
    """TC-002: Test metrics retrieval with empty database."""
    # Database is already empty from fixtures

    # Make API request
    response = await async_client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Verify all counts are zero
    assert data["total_documents"] == 0
    assert data["active_documents"] == 0
    assert data["sessions"]["total_all_time"] == 0
    assert data["sessions"]["active_sessions"] == 0
    assert data["queries"]["total_all_time"] == 0
    assert data["queries"]["total_today"] == 0
    assert data["queries"]["total_this_week"] == 0
    assert data["queries"]["total_this_month"] == 0

    # Verify average_response_time_ms is null
    assert data["average_response_time_ms"] is None

    # Verify database metrics
    assert data["database"]["total_embeddings"] == 0

    # Verify ingestion metrics
    assert data["ingestion"]["total_jobs"] == 0
    assert data["ingestion"]["successful_jobs"] == 0
    assert data["ingestion"]["failed_jobs"] == 0
    assert data["ingestion"]["success_rate"] == 0.0


# ============================================================================
# TC-003: Document Metrics - Active vs Deleted
# ============================================================================

@pytest.mark.asyncio
async def test_document_metrics_active_vs_deleted(session, test_data_source):
    """TC-003: Test document filtering between active and deleted."""
    now = datetime.utcnow()

    # Create 10 active documents
    for i in range(10):
        doc = KnowledgeDocument(
            data_source_id=test_data_source.id,
            title=f"Active Doc {i}",
            content=f"Content {i}",
            content_type=ContentType.PAGE,
            external_id=f"active-{i}",
            is_deleted=False,
            indexed_at=now
        )
        session.add(doc)

    # Create 5 deleted documents
    for i in range(5):
        doc = KnowledgeDocument(
            data_source_id=test_data_source.id,
            title=f"Deleted Doc {i}",
            content=f"Content {i}",
            content_type=ContentType.PAGE,
            external_id=f"deleted-{i}",
            is_deleted=True,
            indexed_at=now
        )
        session.add(doc)

    await session.commit()

    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_document_metrics()

    # Verify counts
    assert result["total_documents"] == 15
    assert result["active_documents"] == 10


# ============================================================================
# TC-004: Session Metrics - Active vs Ended
# ============================================================================

@pytest.mark.asyncio
async def test_session_metrics_active_vs_ended(session, test_admin_user):
    """TC-004: Test session filtering between active and ended."""
    now = datetime.utcnow()

    # Create 20 active sessions (ended_at=NULL)
    for i in range(20):
        sess = ChatSession(
            user_id=test_admin_user.id,
            session_token=f"active-session-{i}",
            started_at=now,
            ended_at=None
        )
        session.add(sess)

    # Create 10 ended sessions (ended_at has timestamp)
    for i in range(10):
        sess = ChatSession(
            user_id=test_admin_user.id,
            session_token=f"ended-session-{i}",
            started_at=now - timedelta(days=1),
            ended_at=now
        )
        session.add(sess)

    await session.commit()

    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_session_metrics()

    # Verify counts
    assert result["total_all_time"] == 30
    assert result["active_sessions"] == 20



# ============================================================================
# TC-005: Query Metrics - Time-Based Filtering
# ============================================================================

@pytest.mark.asyncio
async def test_query_metrics_time_based_filtering(session, test_admin_user):
    """TC-005: Test time-based query counts."""
    now = datetime.utcnow()

    # Calculate time boundaries like the implementation does
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Create session first
    sess = ChatSession(
        user_id=test_admin_user.id,
        session_token="test-session-time-based",
        started_at=now
    )
    session.add(sess)
    await session.commit()

    # Create 10 user messages from today
    for i in range(10):
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.USER,
            content=f"Today query {i}",
            created_at=today_start + timedelta(hours=i, minutes=i * 5),
            message_metadata={}
        )
        session.add(msg)

    # Create 15 user messages from this week (not today)
    # Place them between week_start and yesterday
    for i in range(15):
        # Spread across previous days of the week
        hours_back = 24 + (i * 3)  # Start from yesterday and go back
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.USER,
            content=f"Week query {i}",
            created_at=today_start - timedelta(hours=hours_back),
            message_metadata={}
        )
        session.add(msg)

    # Create 20 user messages from this month (before this week)
    for i in range(20):
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.USER,
            content=f"Month query {i}",
            created_at=week_start - timedelta(days=1, hours=i),
            message_metadata={}
        )
        session.add(msg)

    # Create 30 user messages older than this month
    for i in range(30):
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.USER,
            content=f"Old query {i}",
            created_at=month_start - timedelta(days=30 + i),
            message_metadata={}
        )
        session.add(msg)

    await session.commit()

    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_query_metrics()

    # Verify counts with realistic expectations
    # Today: should be exactly 10
    assert result["total_today"] == 10, f"Expected 10 today, got {result['total_today']}"

    # This week: should include today (10) + week messages that fall within week_start
    assert result["total_this_week"] >= 10, f"Expected at least 10 this week, got {result['total_this_week']}"

    # This month: should include all messages since month_start
    assert result["total_this_month"] >= result["total_this_week"], \
        f"This month ({result['total_this_month']}) should be >= this week ({result['total_this_week']})"

    # All time: should be exactly 75 (10 + 15 + 20 + 30)
    assert result["total_all_time"] == 75, f"Expected 75 total, got {result['total_all_time']}"


# ============================================================================
# TC-006: Response Time - With Duration Metadata
# ============================================================================

@pytest.mark.asyncio
async def test_response_time_with_duration_metadata(session, test_admin_user):
    """TC-006: Calculate average response time from metadata."""
    now = datetime.utcnow()

    # Create session
    sess = ChatSession(
        user_id=test_admin_user.id,
        session_token="test-session-duration",
        started_at=now
    )
    session.add(sess)
    await session.commit()

    # Create 5 assistant messages with duration_ms: 1000, 1200, 1500, 800, 1500
    durations = [1000, 1200, 1500, 800, 1500]
    for i, duration in enumerate(durations):
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.ASSISTANT,
            content=f"Response {i}",
            created_at=now,
            message_metadata={"duration_ms": duration}
        )
        session.add(msg)

    await session.commit()

    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_average_response_time()

    # Verify average: (1000 + 1200 + 1500 + 800 + 1500) / 5 = 1200.0
    assert result == 1200.0


# ============================================================================
# TC-007: Response Time - No Duration Metadata
# ============================================================================

@pytest.mark.asyncio
async def test_response_time_no_duration_metadata(session, test_admin_user):
    """TC-007: Handle missing duration_ms in metadata."""
    now = datetime.utcnow()

    # Create session
    sess = ChatSession(
        user_id=test_admin_user.id,
        session_token="test-session-no-duration",
        started_at=now
    )
    session.add(sess)
    await session.commit()

    # Create assistant messages without duration_ms
    for i in range(3):
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.ASSISTANT,
            content=f"Response {i}",
            created_at=now,
            message_metadata={}  # No duration_ms
        )
        session.add(msg)

    await session.commit()

    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_average_response_time()

    # Verify returns None
    assert result is None


# ============================================================================
# TC-008: Response Time - Mixed Metadata
# ============================================================================

@pytest.mark.asyncio
async def test_response_time_mixed_metadata(session, test_admin_user):
    """TC-008: Calculate average only from messages with duration_ms."""
    now = datetime.utcnow()

    # Create session
    sess = ChatSession(
        user_id=test_admin_user.id,
        session_token="test-session-mixed-duration",
        started_at=now
    )
    session.add(sess)
    await session.commit()

    # Create 3 messages WITH duration_ms: 1000, 2000, 3000
    for i, duration in enumerate([1000, 2000, 3000]):
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.ASSISTANT,
            content=f"Response with duration {i}",
            created_at=now,
            message_metadata={"duration_ms": duration}
        )
        session.add(msg)

    # Create 2 messages WITHOUT duration_ms
    for i in range(2):
        msg = ChatMessage(
            session_id=sess.id,
            role=MessageRole.ASSISTANT,
            content=f"Response without duration {i}",
            created_at=now,
            message_metadata={}
        )
        session.add(msg)

    await session.commit()

    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_average_response_time()

    # Verify average calculated only from 3 messages with data: (1000 + 2000 + 3000) / 3 = 2000.0
    assert result == 2000.0


# ============================================================================
# TC-009: Database Metrics - Size and Embeddings
# ============================================================================

@pytest.mark.asyncio
async def test_database_metrics_size_and_embeddings(session):
    """TC-009: Retrieve database size and embedding count."""
    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_database_metrics()

    # Verify database_size_mb is positive number or 0
    assert isinstance(result["database_size_mb"], (int, float))
    assert result["database_size_mb"] >= 0

    # Verify total_embeddings count (0 for empty database)
    assert result["total_embeddings"] == 0


# ============================================================================
# TC-010: Ingestion Metrics - Success Rate Calculation
# ============================================================================

@pytest.mark.asyncio
async def test_ingestion_metrics_success_rate(session, test_data_source):
    """TC-010: Calculate success rate with mixed job results."""
    now = datetime.utcnow()

    # Create 18 successful jobs
    for i in range(18):
        job = IngestionJob(
            data_source_id=test_data_source.id,
            status=JobStatus.SUCCESS,
            started_at=now - timedelta(hours=i),
            completed_at=now - timedelta(hours=i) + timedelta(minutes=5)
        )
        session.add(job)

    # Create 2 failed jobs
    for i in range(2):
        job = IngestionJob(
            data_source_id=test_data_source.id,
            status=JobStatus.FAILED,
            started_at=now - timedelta(hours=i),
            completed_at=now - timedelta(hours=i) + timedelta(minutes=2),
            error_message="Test error"
        )
        session.add(job)

    await session.commit()

    # Test MetricsService
    metrics_service = MetricsService(session)
    result = await metrics_service.get_ingestion_metrics()

    # Verify counts and success rate
    assert result["total_jobs"] == 20
    assert result["successful_jobs"] == 18
    assert result["failed_jobs"] == 2
    assert result["success_rate"] == 90.0


# ============================================================================
# TC-011: Ingestion Metrics - Zero Jobs
# ============================================================================

@pytest.mark.asyncio
async def test_ingestion_metrics_zero_jobs(session):
    """TC-011: Handle empty ingestion_jobs table."""
    # Test MetricsService with empty database
    metrics_service = MetricsService(session)
    result = await metrics_service.get_ingestion_metrics()

    # Verify graceful handling
    assert result["total_jobs"] == 0
    assert result["successful_jobs"] == 0
    assert result["failed_jobs"] == 0
    assert result["success_rate"] == 0.0
    assert result["last_successful_run"] is None
    assert result["last_failed_run"] is None


# ============================================================================
# TC-013: Authentication - Non-Admin User
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_non_admin_user(async_client: AsyncClient, test_regular_user, regular_token):
    """TC-013: Non-admin user cannot access metrics."""
    # Make API request as regular user
    response = await async_client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {regular_token}"}
    )

    # Verify access denied
    assert response.status_code == 403
    data = response.json()
    assert "admin" in data["detail"].lower() or "forbidden" in data["detail"].lower()


# ============================================================================
# TC-014: Authentication - Unauthenticated User
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_unauthenticated_user(async_client: AsyncClient):
    """TC-014: Unauthenticated user cannot access metrics."""
    # Make API request without auth token
    response = await async_client.get("/api/v1/admin/metrics")

    # Verify authentication required
    assert response.status_code == 401


# ============================================================================
# TC-017: Response Schema Validation
# ============================================================================

@pytest.mark.asyncio
async def test_response_schema_validation(async_client: AsyncClient, session, test_admin_user, test_data_source, admin_token):
    """TC-017: Verify response matches SystemMetricsResponse schema."""
    # Create minimal sample data
    now = datetime.utcnow()

    doc = KnowledgeDocument(
        data_source_id=test_data_source.id,
        title="Test Doc",
        content="Test content",
        content_type=ContentType.PAGE,
        external_id="test-1",
        is_deleted=False,
        indexed_at=now
    )
    session.add(doc)
    await session.commit()

    # Make API request
    response = await async_client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields present
    assert "total_documents" in data
    assert "active_documents" in data
    assert "sessions" in data
    assert "queries" in data
    assert "average_response_time_ms" in data
    assert "database" in data
    assert "ingestion" in data
    assert "timestamp" in data

    # Verify data types
    assert isinstance(data["total_documents"], int)
    assert isinstance(data["active_documents"], int)
    assert isinstance(data["sessions"], dict)
    assert isinstance(data["queries"], dict)
    assert isinstance(data["database"], dict)
    assert isinstance(data["ingestion"], dict)
    assert isinstance(data["timestamp"], str)

    # Verify nested structures
    assert "total_all_time" in data["sessions"]
    assert "active_sessions" in data["sessions"]
    assert "total_all_time" in data["queries"]
    assert "total_today" in data["queries"]
    assert "total_this_week" in data["queries"]
    assert "total_this_month" in data["queries"]
    assert "total_embeddings" in data["database"]
    assert "database_size_mb" in data["database"]
    assert "total_jobs" in data["ingestion"]
    assert "successful_jobs" in data["ingestion"]
    assert "failed_jobs" in data["ingestion"]
    assert "success_rate" in data["ingestion"]

    # Verify timestamp is ISO 8601 format
    try:
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    except ValueError:
        pytest.fail("Timestamp is not in ISO 8601 format")
