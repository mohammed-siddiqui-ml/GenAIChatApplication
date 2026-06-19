"""
Tests for Ingestion Job Management and Trigger Endpoints (Task 028)

This test suite covers:
- POST /api/v1/admin/ingestion/trigger (trigger manual ingestion)
- GET /api/v1/admin/ingestion/jobs (list jobs with filtering)
- GET /api/v1/admin/ingestion/jobs/{job_id} (get job details)
- Service layer: IngestionJobService
- Authentication: Admin role enforcement
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from models.data_source import DataSource, IngestionJob, JobStatus, DataSourceType
from models.user import User, UserRole
from services.ingestion_service import IngestionJobService, IngestionJobError
from core.security import create_access_token


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def test_data_sources(db_session, admin_user):
    """Create test data sources with various types and statuses."""
    # Confluence data source (active)
    confluence_source = DataSource(
        name="Test Wiki",
        type=DataSourceType.CONFLUENCE,
        source_config={"url": "https://wiki.test.com", "space_key": "TEST"},
        is_active=True,
        created_by=admin_user.id
    )
    
    # JIRA data source (active)
    jira_source = DataSource(
        name="Test JIRA",
        type=DataSourceType.JIRA,
        source_config={"url": "https://jira.test.com", "project_key": "TEST"},
        is_active=True,
        created_by=admin_user.id
    )

    # Inactive data source
    inactive_source = DataSource(
        name="Inactive Source",
        type=DataSourceType.CONFLUENCE,
        source_config={"url": "https://old.test.com"},
        is_active=False,
        created_by=admin_user.id
    )

    # Onboarding data source
    onboarding_source = DataSource(
        name="Onboarding Docs",
        type=DataSourceType.ONBOARDING,
        source_config={"storage_path": "/data"},
        is_active=True,
        created_by=admin_user.id
    )
    
    db_session.add_all([confluence_source, jira_source, inactive_source, onboarding_source])
    await db_session.commit()
    await db_session.refresh(confluence_source)
    await db_session.refresh(jira_source)
    await db_session.refresh(inactive_source)
    await db_session.refresh(onboarding_source)
    
    return {
        "confluence": confluence_source,
        "jira": jira_source,
        "inactive": inactive_source,
        "onboarding": onboarding_source
    }


@pytest_asyncio.fixture
async def test_jobs(db_session, test_data_sources):
    """Create test ingestion jobs with various statuses."""
    now = datetime.utcnow()
    
    jobs = [
        # Pending job
        IngestionJob(
            data_source_id=test_data_sources["confluence"].id,
            status=JobStatus.PENDING,
            started_at=None,
            completed_at=None,
            documents_processed=0,
            documents_failed=0,
            job_metadata={"sync_type": "full_sync", "triggered_manually": True}
        ),
        # Running job
        IngestionJob(
            data_source_id=test_data_sources["confluence"].id,
            status=JobStatus.RUNNING,
            started_at=now - timedelta(minutes=10),
            completed_at=None,
            documents_processed=10,
            documents_failed=0,
            job_metadata={"sync_type": "incremental"}
        ),
        # Success job
        IngestionJob(
            data_source_id=test_data_sources["jira"].id,
            status=JobStatus.SUCCESS,
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=30),
            documents_processed=42,
            documents_failed=2,
            job_metadata={"sync_type": "full_sync"}
        ),
        # Failed job
        IngestionJob(
            data_source_id=test_data_sources["jira"].id,
            status=JobStatus.FAILED,
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=1, minutes=50),
            error_message="Connection timeout",
            documents_processed=5,
            documents_failed=10,
            job_metadata={"sync_type": "incremental"}
        ),
    ]
    
    db_session.add_all(jobs)
    await db_session.commit()
    
    # Refresh all jobs
    for job in jobs:
        await db_session.refresh(job)
    
    return jobs


@pytest_asyncio.fixture
async def async_client(db_session):
    """Create async HTTP client with mocked database dependency."""
    from main import app
    from core.database import get_db

    # Override get_db dependency to use test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Use ASGITransport to wrap the FastAPI app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
def mock_celery_tasks():
    """Mock Celery task dispatch to prevent actual task execution."""
    mock_confluence_task = MagicMock()
    mock_confluence_task.delay.return_value = MagicMock(id="test-task-id-confluence")

    mock_jira_task = MagicMock()
    mock_jira_task.delay.return_value = MagicMock(id="test-task-id-jira")

    mock_onboarding_task = MagicMock()
    mock_onboarding_task.delay.return_value = MagicMock(id="test-task-id-onboarding")

    with patch("services.ingestion_service.ingest_confluence_docs", mock_confluence_task), \
         patch("services.ingestion_service.ingest_jira_issues", mock_jira_task), \
         patch("services.ingestion_service.ingest_onboarding_materials", mock_onboarding_task):
        yield {
            "confluence": mock_confluence_task,
            "jira": mock_jira_task,
            "onboarding": mock_onboarding_task
        }


# ============================================================================
# Test Case Group A: Trigger Ingestion Endpoint
# ============================================================================

@pytest.mark.asyncio
class TestTriggerIngestion:
    """Test POST /api/v1/admin/ingestion/trigger endpoint."""

    async def test_trigger_confluence_full_sync(
        self, async_client, admin_user, test_data_sources, mock_celery_tasks
    ):
        """TC-A1: Successfully trigger full_sync for Confluence data source."""
        # Create admin token
        token = create_access_token({"sub": admin_user.email})

        # Send request
        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={
                "data_source_id": test_data_sources["confluence"].id,
                "sync_type": "full_sync"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert response
        assert response.status_code == 201
        data = response.json()
        assert data["data_source_id"] == test_data_sources["confluence"].id
        assert data["status"] == "pending"
        assert data["sync_type"] == "full_sync"
        assert data["task_id"] == "test-task-id-confluence"
        assert "job_id" in data
        assert "message" in data

        # Verify Celery task was called
        mock_celery_tasks["confluence"].delay.assert_called_once()

    async def test_trigger_jira_incremental(
        self, async_client, admin_user, test_data_sources, mock_celery_tasks
    ):
        """TC-A2: Successfully trigger incremental sync for JIRA data source."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={
                "data_source_id": test_data_sources["jira"].id,
                "sync_type": "incremental"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["data_source_id"] == test_data_sources["jira"].id
        assert data["sync_type"] == "incremental"
        assert data["task_id"] == "test-task-id-jira"

        # Verify JIRA task was called
        mock_celery_tasks["jira"].delay.assert_called_once()

    async def test_trigger_default_sync_type(
        self, async_client, admin_user, test_data_sources, mock_celery_tasks
    ):
        """TC-A3: Default sync_type is 'incremental' when not specified."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={"data_source_id": test_data_sources["confluence"].id},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        assert response.json()["sync_type"] == "incremental"

    async def test_trigger_nonexistent_data_source(
        self, async_client, admin_user, mock_celery_tasks
    ):
        """TC-A4: Reject trigger for non-existent data source (404)."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={"data_source_id": 99999, "sync_type": "full_sync"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_trigger_inactive_data_source(
        self, async_client, admin_user, test_data_sources, mock_celery_tasks
    ):
        """TC-A5: Reject trigger for inactive data source (400)."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={"data_source_id": test_data_sources["inactive"].id},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        assert "not active" in response.json()["detail"].lower()

    async def test_trigger_onboarding_without_file_path(
        self, async_client, admin_user, test_data_sources, mock_celery_tasks
    ):
        """TC-A6: Reject onboarding trigger without file_path (400)."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={"data_source_id": test_data_sources["onboarding"].id},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        assert "file_path" in response.json()["detail"].lower()

    async def test_trigger_invalid_sync_type(
        self, async_client, admin_user, test_data_sources, mock_celery_tasks
    ):
        """TC-A7: Reject invalid sync_type (422)."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={
                "data_source_id": test_data_sources["confluence"].id,
                "sync_type": "invalid_type"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 422

    async def test_trigger_non_admin_rejected(
        self, async_client, regular_user, test_data_sources, mock_celery_tasks
    ):
        """TC-A8: Non-admin user cannot trigger ingestion (403)."""
        token = create_access_token({"sub": regular_user.email})

        response = await async_client.post(
            "/api/v1/admin/ingestion/trigger",
            json={"data_source_id": test_data_sources["confluence"].id},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


# ============================================================================
# Test Case Group B: List Ingestion Jobs Endpoint
# ============================================================================

@pytest.mark.asyncio
class TestListIngestionJobs:
    """Test GET /api/v1/admin/ingestion/jobs endpoint."""

    async def test_list_all_jobs(
        self, async_client, admin_user, test_jobs
    ):
        """TC-B1: List all jobs without filters."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.get(
            "/api/v1/admin/ingestion/jobs",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == len(test_jobs)
        assert len(data["items"]) == len(test_jobs)

    async def test_filter_by_status(
        self, async_client, admin_user, test_jobs
    ):
        """TC-B2: Filter jobs by status."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.get(
            "/api/v1/admin/ingestion/jobs?job_status=success",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "success" for item in data["items"])
        assert data["total"] == 1  # Only 1 success job in test data

    async def test_filter_by_data_source(
        self, async_client, admin_user, test_jobs, test_data_sources
    ):
        """TC-B3: Filter jobs by data_source_id."""
        token = create_access_token({"sub": admin_user.email})
        confluence_id = test_data_sources["confluence"].id

        response = await async_client.get(
            f"/api/v1/admin/ingestion/jobs?data_source_id={confluence_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert all(item["data_source_id"] == confluence_id for item in data["items"])

    async def test_pagination(
        self, async_client, admin_user, test_jobs
    ):
        """TC-B5: Pagination with limit and offset."""
        token = create_access_token({"sub": admin_user.email})

        # Get first 2 items
        response = await async_client.get(
            "/api/v1/admin/ingestion/jobs?limit=2&offset=0",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert data["total"] == len(test_jobs)

    async def test_empty_result_set(
        self, async_client, admin_user, test_jobs
    ):
        """TC-B7: Empty result set returns empty list."""
        token = create_access_token({"sub": admin_user.email})

        # Filter by data_source_id that doesn't exist
        response = await async_client.get(
            "/api/v1/admin/ingestion/jobs?data_source_id=99999",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_non_admin_rejected(
        self, async_client, regular_user, test_jobs
    ):
        """TC-B8: Non-admin user cannot list jobs (403)."""
        token = create_access_token({"sub": regular_user.email})

        response = await async_client.get(
            "/api/v1/admin/ingestion/jobs",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


# ============================================================================
# Test Case Group C: Get Job Details Endpoint
# ============================================================================

@pytest.mark.asyncio
class TestGetJobDetails:
    """Test GET /api/v1/admin/ingestion/jobs/{job_id} endpoint."""

    async def test_get_job_by_id(
        self, async_client, admin_user, test_jobs
    ):
        """TC-C1: Successfully retrieve job by ID."""
        token = create_access_token({"sub": admin_user.email})
        job_id = test_jobs[0].id

        response = await async_client.get(
            f"/api/v1/admin/ingestion/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert "data_source_id" in data
        assert "data_source_name" in data
        assert "data_source_type" in data
        assert "status" in data

    async def test_get_nonexistent_job(
        self, async_client, admin_user
    ):
        """TC-C3: Return 404 for non-existent job."""
        token = create_access_token({"sub": admin_user.email})

        response = await async_client.get(
            "/api/v1/admin/ingestion/jobs/99999",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404

    async def test_non_admin_rejected(
        self, async_client, regular_user, test_jobs
    ):
        """TC-C4: Non-admin user cannot get job details (403)."""
        token = create_access_token({"sub": regular_user.email})
        job_id = test_jobs[0].id

        response = await async_client.get(
            f"/api/v1/admin/ingestion/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


# ============================================================================
# Test Case Group D: Service Layer Tests
# ============================================================================

@pytest.mark.asyncio
class TestIngestionJobService:
    """Test IngestionJobService business logic."""

    async def test_trigger_creates_pending_job(
        self, db_session, test_data_sources, mock_celery_tasks
    ):
        """TC-D1: trigger_ingestion creates job with PENDING status."""
        service = IngestionJobService(db_session)

        job, task_id = await service.trigger_ingestion(
            data_source_id=test_data_sources["confluence"].id,
            sync_type="full_sync"
        )

        assert job.status == JobStatus.PENDING
        assert job.data_source_id == test_data_sources["confluence"].id
        assert job.started_at is None
        assert job.completed_at is None

    async def test_job_metadata_populated(
        self, db_session, test_data_sources, mock_celery_tasks
    ):
        """TC-D2: Job metadata populated correctly."""
        service = IngestionJobService(db_session)

        job, task_id = await service.trigger_ingestion(
            data_source_id=test_data_sources["confluence"].id,
            sync_type="full_sync"
        )

        assert job.job_metadata["sync_type"] == "full_sync"
        assert job.job_metadata["triggered_manually"] is True
        assert "triggered_at" in job.job_metadata
        assert "task_id" in job.job_metadata

    async def test_get_job_retrieves_correct_job(
        self, db_session, test_jobs
    ):
        """TC-D7: get_job retrieves correct job by ID."""
        service = IngestionJobService(db_session)

        job = await service.get_job(test_jobs[0].id)

        assert job is not None
        assert job.id == test_jobs[0].id

    async def test_get_nonexistent_job_returns_none(
        self, db_session
    ):
        """TC-D7: get_job returns None for non-existent job."""
        service = IngestionJobService(db_session)

        job = await service.get_job(99999)

        assert job is None

    async def test_list_jobs_status_filter(
        self, db_session, test_jobs
    ):
        """TC-D8: list_jobs applies status filter correctly."""
        service = IngestionJobService(db_session)

        jobs, total = await service.list_jobs(status=JobStatus.SUCCESS)

        assert total == 1
        assert all(job.status == JobStatus.SUCCESS for job in jobs)

    async def test_list_jobs_data_source_filter(
        self, db_session, test_jobs, test_data_sources
    ):
        """TC-D9: list_jobs applies data_source_id filter correctly."""
        service = IngestionJobService(db_session)

        jobs, total = await service.list_jobs(
            data_source_id=test_data_sources["jira"].id
        )

        assert total == 2  # 2 JIRA jobs in test data
        assert all(job.data_source_id == test_data_sources["jira"].id for job in jobs)

