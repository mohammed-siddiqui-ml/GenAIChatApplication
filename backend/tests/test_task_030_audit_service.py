"""
Tests for Task-030: Audit Log Service and Endpoints

Tests cover:
- AuditService methods (create_audit_log, get_audit_logs)
- Audit log querying with filtering and pagination
- Automatic audit logging on data source CRUD operations
- GET /api/v1/admin/audit-logs endpoint
- Authentication/authorization
- IP address extraction
- Data integrity and immutability
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport

from models.audit import AuditLog
from models.user import User, UserRole
from models.data_source import DataSource, DataSourceType
from services.audit_service import AuditService, AuditServiceError
from schemas.admin import AuditLogResponse, AuditLogListResponse
from core.security import hash_password


# ========== Test Data ==========
ADMIN_EMAIL = "admin@test.com"
REGULAR_EMAIL = "user@test.com"
TEST_PASSWORD = "TestPass123!"


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
async def audit_service(session: AsyncSession):
    """Create AuditService instance."""
    return AuditService(session)


# ========== Unit Tests: AuditService ==========

class TestAuditServiceCreation:
    """Test audit log creation functionality."""

    @pytest.mark.asyncio
    async def test_create_audit_log_full_data(self, session: AsyncSession, test_admin_user, audit_service):
        """TC-001: Create audit log with all fields populated."""
        # Create audit log with all fields
        audit_log = await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="create",
            resource_type="data_source",
            resource_id=5,
            changes={"name": "Test Wiki", "type": "confluence", "is_active": True},
            ip_address="192.168.1.100"
        )
        await session.commit()

        # Verify audit log created
        assert audit_log.id is not None
        assert audit_log.user_id == test_admin_user.id
        assert audit_log.action == "create"
        assert audit_log.resource_type == "data_source"
        assert audit_log.resource_id == 5
        assert audit_log.audit_changes == {"name": "Test Wiki", "type": "confluence", "is_active": True}
        assert audit_log.ip_address == "192.168.1.100"
        assert audit_log.created_at is not None
        assert isinstance(audit_log.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_audit_log_minimal_data(self, session: AsyncSession, audit_service):
        """TC-002: Create audit log with minimal fields (system action)."""
        # Create audit log with minimal fields
        audit_log = await audit_service.create_audit_log(
            user_id=None,
            action="system_backup"
        )
        await session.commit()

        # Verify audit log created
        assert audit_log.id is not None
        assert audit_log.user_id is None
        assert audit_log.action == "system_backup"
        assert audit_log.resource_type is None
        assert audit_log.resource_id is None
        assert audit_log.audit_changes is None
        assert audit_log.ip_address is None
        assert audit_log.created_at is not None

    @pytest.mark.asyncio
    async def test_create_audit_log_complex_jsonb_changes(self, session: AsyncSession, test_admin_user, audit_service):
        """TC-020: Test complex JSONB changes storage."""
        # Create audit log with complex nested changes
        changes = {
            "before": {
                "config": {"url": "old.com", "token": "xxx"},
                "schedule": "0 1 * * *"
            },
            "after": {
                "config": {"url": "new.com", "token": "yyy"},
                "schedule": "0 2 * * *"
            }
        }

        audit_log = await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="update",
            resource_type="data_source",
            resource_id=1,
            changes=changes
        )
        await session.commit()

        # Verify JSONB stored correctly
        assert audit_log.audit_changes == changes
        assert audit_log.audit_changes["before"]["config"]["url"] == "old.com"
        assert audit_log.audit_changes["after"]["schedule"] == "0 2 * * *"


class TestAuditServiceQuerying:
    """Test audit log querying functionality."""

    @pytest.mark.asyncio
    async def test_filter_by_user_id(self, session: AsyncSession, test_admin_user, test_regular_user, audit_service):
        """TC-003: Filter audit logs by user ID."""
        # Create audit logs for different users
        for i in range(5):
            await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="create",
                resource_type="data_source",
                resource_id=i
            )

        for i in range(3):
            await audit_service.create_audit_log(
                user_id=test_regular_user.id,
                action="update",
                resource_type="data_source",
                resource_id=i
            )

        for i in range(2):
            await audit_service.create_audit_log(
                user_id=None,
                action="system_backup"
            )

        await session.commit()

        # Query logs for admin user
        logs, total = await audit_service.get_audit_logs(user_id=test_admin_user.id, limit=50, offset=0)

        # Verify results
        assert len(logs) == 5
        assert total == 5
        assert all(log.user_id == test_admin_user.id for log in logs)

    @pytest.mark.asyncio
    async def test_filter_by_action(self, session: AsyncSession, test_admin_user, audit_service):
        """TC-004: Filter audit logs by action type."""
        # Create audit logs with different actions
        for i in range(4):
            await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="create",
                resource_id=i
            )

        for i in range(3):
            await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="update",
                resource_id=i
            )

        for i in range(3):
            await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="delete",
                resource_id=i
            )

        await session.commit()

        # Query logs for delete action
        logs, total = await audit_service.get_audit_logs(action="delete", limit=50, offset=0)

        # Verify results
        assert len(logs) == 3
        assert total == 3
        assert all(log.action == "delete" for log in logs)

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, session: AsyncSession, test_admin_user, audit_service):
        """TC-005: Filter audit logs by date range."""
        # Create audit logs with different timestamps
        base_date = datetime(2024, 1, 1, 10, 0, 0)

        # Create logs at different dates
        log1 = await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="create",
            resource_id=1
        )
        log1.created_at = base_date

        log2 = await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="create",
            resource_id=2
        )
        log2.created_at = base_date + timedelta(days=5)

        log3 = await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="create",
            resource_id=3
        )
        log3.created_at = base_date + timedelta(days=15)

        log4 = await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="create",
            resource_id=4
        )
        log4.created_at = base_date + timedelta(days=20)

        await session.commit()

        # Query logs in date range (Jan 3 to Jan 18)
        start = datetime(2024, 1, 3)
        end = datetime(2024, 1, 18)
        logs, total = await audit_service.get_audit_logs(
            start_date=start,
            end_date=end,
            limit=50,
            offset=0
        )

        # Verify results (should get logs 2 and 3)
        assert len(logs) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_pagination(self, session: AsyncSession, test_admin_user, audit_service):
        """TC-006: Test pagination with limit and offset."""
        # Create 25 audit logs
        for i in range(25):
            await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="create",
                resource_id=i
            )
        await session.commit()

        # Get page 1
        page1_logs, total = await audit_service.get_audit_logs(limit=10, offset=0)
        assert len(page1_logs) == 10
        assert total == 25

        # Get page 2
        page2_logs, total = await audit_service.get_audit_logs(limit=10, offset=10)
        assert len(page2_logs) == 10
        assert total == 25

        # Get page 3 (last page)
        page3_logs, total = await audit_service.get_audit_logs(limit=10, offset=20)
        assert len(page3_logs) == 5
        assert total == 25

        # Verify no duplicates
        page1_ids = {log.id for log in page1_logs}
        page2_ids = {log.id for log in page2_logs}
        page3_ids = {log.id for log in page3_logs}

        assert len(page1_ids & page2_ids) == 0
        assert len(page2_ids & page3_ids) == 0
        assert len(page1_ids & page3_ids) == 0

    @pytest.mark.asyncio
    async def test_combined_filters(self, session: AsyncSession, test_admin_user, test_regular_user, audit_service):
        """TC-007: Test combining multiple filters."""
        # Create various audit logs
        await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="update",
            resource_type="data_source",
            resource_id=1
        )

        await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="update",
            resource_type="user",
            resource_id=2
        )

        await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="create",
            resource_type="data_source",
            resource_id=3
        )

        await audit_service.create_audit_log(
            user_id=test_regular_user.id,
            action="update",
            resource_type="data_source",
            resource_id=4
        )

        await session.commit()

        # Query with combined filters
        logs, total = await audit_service.get_audit_logs(
            user_id=test_admin_user.id,
            action="update",
            resource_type="data_source",
            limit=50,
            offset=0
        )

        # Verify only logs matching ALL criteria
        assert len(logs) == 1
        assert total == 1
        assert logs[0].user_id == test_admin_user.id
        assert logs[0].action == "update"
        assert logs[0].resource_type == "data_source"

    @pytest.mark.asyncio
    async def test_results_ordered_by_created_at_desc(self, session: AsyncSession, test_admin_user, audit_service):
        """Test that results are ordered by created_at DESC (newest first)."""
        # Create logs with different timestamps
        base_date = datetime(2024, 1, 1, 10, 0, 0)

        for i in range(5):
            log = await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="create",
                resource_id=i
            )
            log.created_at = base_date + timedelta(hours=i)

        await session.commit()

        # Get all logs
        logs, total = await audit_service.get_audit_logs(limit=50, offset=0)

        # Verify ordered by created_at DESC
        assert len(logs) == 5
        for i in range(len(logs) - 1):
            assert logs[i].created_at >= logs[i + 1].created_at


# ========== Integration Tests: Automatic Audit Logging ==========

class TestAutomaticAuditLogging:
    """Test automatic audit logging on admin operations."""

    @pytest.mark.asyncio
    async def test_data_source_create_logging(
        self,
        session: AsyncSession,
        async_client: AsyncClient,
        test_admin_user,
        admin_token
    ):
        """TC-008: Automatic logging on data source create."""
        # Create data source via API
        response = await async_client.post(
            "/api/v1/admin/data-sources",
            json={
                "name": "Test Wiki",
                "type": "confluence",
                "config": {
                    "url": "https://wiki.example.com",
                    "username": "admin@example.com",
                    "api_token": "test-token",
                    "space_key": "DOCS"
                },
                "sync_schedule": "0 2 * * *"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201
        data_source_id = response.json()["id"]

        # Query audit logs
        stmt = select(AuditLog).where(AuditLog.action == "create")
        result = await session.execute(stmt)
        audit_logs = result.scalars().all()

        # Verify audit log created
        assert len(audit_logs) >= 1
        audit_log = audit_logs[0]
        assert audit_log.user_id == test_admin_user.id
        assert audit_log.action == "create"
        assert audit_log.resource_type == "data_source"
        assert audit_log.resource_id == data_source_id
        assert audit_log.audit_changes is not None
        assert "name" in audit_log.audit_changes
        assert audit_log.ip_address is not None

    @pytest.mark.asyncio
    async def test_data_source_update_logging(
        self,
        session: AsyncSession,
        async_client: AsyncClient,
        test_admin_user,
        admin_token
    ):
        """TC-009: Automatic logging on data source update with before/after state."""
        # Create data source first
        create_response = await async_client.post(
            "/api/v1/admin/data-sources",
            json={
                "name": "Old Name",
                "type": "confluence",
                "config": {
                    "url": "https://wiki.example.com",
                    "username": "admin@example.com",
                    "api_token": "test-token",
                    "space_key": "DOCS"
                },
                "sync_schedule": "0 1 * * *"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert create_response.status_code == 201
        data_source_id = create_response.json()["id"]

        # Update data source
        update_response = await async_client.put(
            f"/api/v1/admin/data-sources/{data_source_id}",
            json={
                "name": "New Name",
                "is_active": False
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert update_response.status_code == 200

        # Query audit logs for update action
        stmt = select(AuditLog).where(AuditLog.action == "update")
        result = await session.execute(stmt)
        audit_logs = result.scalars().all()

        # Verify audit log created with before/after
        assert len(audit_logs) >= 1
        audit_log = audit_logs[0]
        assert audit_log.user_id == test_admin_user.id
        assert audit_log.action == "update"
        assert audit_log.resource_type == "data_source"
        assert audit_log.resource_id == data_source_id
        assert audit_log.audit_changes is not None
        assert "before" in audit_log.audit_changes
        assert "after" in audit_log.audit_changes

    @pytest.mark.asyncio
    async def test_data_source_delete_logging(
        self,
        session: AsyncSession,
        async_client: AsyncClient,
        test_admin_user,
        admin_token
    ):
        """TC-010: Automatic logging on data source delete."""
        # Create data source first
        create_response = await async_client.post(
            "/api/v1/admin/data-sources",
            json={
                "name": "Wiki to Delete",
                "type": "confluence",
                "config": {
                    "url": "https://wiki.example.com",
                    "username": "admin@example.com",
                    "api_token": "test-token",
                    "space_key": "DOCS"
                },
                "sync_schedule": "0 2 * * *"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert create_response.status_code == 201
        data_source_id = create_response.json()["id"]

        # Delete data source
        delete_response = await async_client.delete(
            f"/api/v1/admin/data-sources/{data_source_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_response.status_code == 200

        # Query audit logs for delete action
        stmt = select(AuditLog).where(AuditLog.action == "delete")
        result = await session.execute(stmt)
        audit_logs = result.scalars().all()

        # Verify audit log exists and persists after resource deletion
        assert len(audit_logs) >= 1
        audit_log = audit_logs[0]
        assert audit_log.user_id == test_admin_user.id
        assert audit_log.action == "delete"
        assert audit_log.resource_type == "data_source"
        assert audit_log.resource_id == data_source_id
        assert audit_log.audit_changes is not None

    @pytest.mark.asyncio
    async def test_ip_address_extraction_x_forwarded_for(
        self,
        session: AsyncSession,
        async_client: AsyncClient,
        test_admin_user,
        admin_token
    ):
        """TC-011: IP address extraction from X-Forwarded-For header."""
        # Create data source with X-Forwarded-For header
        response = await async_client.post(
            "/api/v1/admin/data-sources",
            json={
                "name": "Test Wiki",
                "type": "confluence",
                "config": {
                    "url": "https://wiki.example.com",
                    "username": "admin@example.com",
                    "api_token": "test-token",
                    "space_key": "DOCS"
                },
                "sync_schedule": "0 2 * * *"
            },
            headers={
                "Authorization": f"Bearer {admin_token}",
                "X-Forwarded-For": "203.0.113.45, 198.51.100.1"
            }
        )

        assert response.status_code == 201

        # Query audit logs
        stmt = select(AuditLog).where(AuditLog.action == "create")
        result = await session.execute(stmt)
        audit_logs = result.scalars().all()

        # Verify IP address captured (should be first IP in chain)
        assert len(audit_logs) >= 1
        audit_log = audit_logs[0]
        assert audit_log.ip_address == "203.0.113.45"


# ========== API Tests: GET /api/v1/admin/audit-logs ==========

class TestAuditLogsEndpoint:
    """Test GET /api/v1/admin/audit-logs endpoint."""

    @pytest.mark.asyncio
    async def test_authentication_required(self, async_client: AsyncClient):
        """TC-012: Request without token returns 401."""
        response = await async_client.get("/api/v1/admin/audit-logs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_role_required(
        self,
        async_client: AsyncClient,
        test_regular_user,
        regular_token
    ):
        """TC-013: Request with regular user token returns 403."""
        response = await async_client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_successful_retrieval(
        self,
        session: AsyncSession,
        async_client: AsyncClient,
        test_admin_user,
        admin_token,
        audit_service
    ):
        """TC-014: Successful retrieval with admin token."""
        # Create some audit logs
        for i in range(15):
            await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="create",
                resource_type="data_source",
                resource_id=i
            )
        await session.commit()

        # Get audit logs
        response = await async_client.get(
            "/api/v1/admin/audit-logs?limit=10&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["limit"] == 10
        assert data["offset"] == 0

        # Verify each item has user_email
        for item in data["items"]:
            assert "user_email" in item
            assert item["user_email"] == test_admin_user.email

    @pytest.mark.asyncio
    async def test_filter_by_user(
        self,
        session: AsyncSession,
        async_client: AsyncClient,
        test_admin_user,
        test_regular_user,
        admin_token,
        audit_service
    ):
        """TC-015: Filter by user_id."""
        # Create audit logs for different users
        for i in range(5):
            await audit_service.create_audit_log(
                user_id=test_admin_user.id,
                action="create",
                resource_id=i
            )

        for i in range(3):
            await audit_service.create_audit_log(
                user_id=test_regular_user.id,
                action="update",
                resource_id=i
            )
        await session.commit()

        # Filter by admin user
        response = await async_client.get(
            f"/api/v1/admin/audit-logs?user_id={test_admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5
        assert all(item["user_id"] == test_admin_user.id for item in data["items"])

    @pytest.mark.asyncio
    async def test_invalid_limit(self, async_client: AsyncClient, admin_token):
        """TC-016: Invalid limit returns 422."""
        response = await async_client.get(
            "/api/v1/admin/audit-logs?limit=150",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_format(self, async_client: AsyncClient, admin_token):
        """TC-017: Invalid date format returns 422."""
        response = await async_client.get(
            "/api/v1/admin/audit-logs?start_date=invalid-date",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_no_put_endpoint_exists(self, async_client: AsyncClient, admin_token):
        """TC-018: Verify no PUT endpoint exists (immutability)."""
        response = await async_client.put(
            "/api/v1/admin/audit-logs/1",
            json={"action": "modified"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should return 404 or 405 (method not allowed)
        assert response.status_code in [404, 405]

    @pytest.mark.asyncio
    async def test_no_delete_endpoint_exists(self, async_client: AsyncClient, admin_token):
        """TC-018: Verify no DELETE endpoint exists (immutability)."""
        response = await async_client.delete(
            "/api/v1/admin/audit-logs/1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should return 404 or 405 (method not allowed)
        assert response.status_code in [404, 405]

    @pytest.mark.asyncio
    async def test_empty_results(self, async_client: AsyncClient, admin_token):
        """TC-005 Edge Case: No audit logs returns empty list."""
        response = await async_client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    @pytest.mark.asyncio
    async def test_filtering_multiple_criteria(
        self,
        session: AsyncSession,
        async_client: AsyncClient,
        test_admin_user,
        admin_token,
        audit_service
    ):
        """Test filtering with multiple query parameters."""
        # Create varied audit logs
        await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="create",
            resource_type="data_source",
            resource_id=1
        )

        await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="update",
            resource_type="data_source",
            resource_id=2
        )

        await audit_service.create_audit_log(
            user_id=test_admin_user.id,
            action="update",
            resource_type="user",
            resource_id=3
        )

        await session.commit()

        # Filter by action and resource_type
        response = await async_client.get(
            "/api/v1/admin/audit-logs?action=update&resource_type=data_source",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["action"] == "update"
        assert data["items"][0]["resource_type"] == "data_source"


# ========== Data Integrity Tests ==========

class TestDataIntegrity:
    """Test data integrity and immutability."""

    @pytest.mark.asyncio
    async def test_user_deletion_preserves_audit_logs(
        self,
        session: AsyncSession,
        audit_service
    ):
        """TC-019: Audit logs persist after user deletion."""
        # Create a user
        from models.user import User, UserRole
        from core.security import hash_password

        user = User(
            email="deleteme@test.com",
            password_hash=hash_password("Test123!"),
            role=UserRole.USER,
            is_active=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

        # Create audit logs for this user
        for i in range(5):
            await audit_service.create_audit_log(
                user_id=user_id,
                action="create",
                resource_id=i
            )
        await session.commit()

        # Delete the user
        await session.delete(user)
        await session.commit()

        # Query audit logs
        logs, total = await audit_service.get_audit_logs(user_id=user_id, limit=50, offset=0)

        # Verify audit logs still exist (user_id may be NULL due to ON DELETE SET NULL)
        # Since we're using user_id filter, logs should exist but user relationship will be null
        stmt = select(AuditLog)
        result = await session.execute(stmt)
        all_logs = result.scalars().all()

        # At least some logs should exist
        assert len(all_logs) >= 5

