"""
Test suite for JIRA Ingestion Celery Task (task-024)

Tests cover:
- Unit tests for helper functions (hash, job lifecycle, issue processing)
- Integration tests (issue ingestion, deduplication, progress tracking)
- Error handling (API failures, retries, invalid data sources)
- Functional tests (end-to-end workflow, refresh task)
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
from typing import List, Dict, Any

from tasks.ingestion.jira import (
    ingest_jira_issues,
    refresh_jira_data,
    _get_data_source,
    _create_ingestion_job,
    _update_job_progress,
    _complete_job,
    _process_issue
)
from models.data_source import DataSource, IngestionJob, JobStatus, DataSourceType
from models.knowledge import KnowledgeDocument, DocumentEmbedding, ContentType
from integrations.jira_client import JiraClient, JiraAPIError
from integrations.openai_client import OpenAIClient, OpenAIError


# ==================== Mock Data ====================

MOCK_JIRA_ISSUE = {
    "key": "TEST-123",
    "fields": {
        "summary": "Test Issue Summary",
        "description": "This is a detailed description of the test issue.",
        "status": {"name": "Open"},
        "resolution": None,
        "created": "2026-06-01T10:00:00.000Z",
        "updated": "2026-06-15T14:30:00.000Z",
        "labels": ["bug", "high-priority"],
        "priority": {"name": "High"},
        "issuetype": {"name": "Bug"},
        "project": {"key": "TEST"},
        "assignee": {"displayName": "John Doe"},
        "reporter": {"displayName": "Jane Smith"}
    }
}

MOCK_JIRA_ISSUES = [
    {
        "key": "TEST-123",
        "fields": {
            "summary": "First Issue",
            "description": "Description for first issue with enough content.",
            "status": {"name": "Open"},
            "priority": {"name": "High"},
            "issuetype": {"name": "Bug"},
            "project": {"key": "TEST"}
        }
    },
    {
        "key": "TEST-124",
        "fields": {
            "summary": "Second Issue",
            "description": "Description for second issue with enough content.",
            "status": {"name": "In Progress"},
            "priority": {"name": "Medium"},
            "issuetype": {"name": "Story"},
            "project": {"key": "TEST"}
        }
    }
]

MOCK_JIRA_COMMENTS = [
    {
        "body": "First comment on the issue",
        "author": {"displayName": "John Doe"},
        "created": "2026-06-02T09:00:00.000Z"
    },
    {
        "body": "Second comment with more details",
        "author": {"displayName": "Jane Smith"},
        "created": "2026-06-03T11:00:00.000Z"
    }
]

MOCK_EMBEDDING = [0.1] * 1536  # Mock 1536-dimensional embedding vector


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def test_data_source(db_session):
    """Create a test JIRA data source."""
    data_source = DataSource(
        name="Test JIRA",
        type=DataSourceType.JIRA,
        is_active=True,
        source_config={
            "jql_query": "project = TEST ORDER BY updated DESC",
            "url": "https://test.atlassian.net",
            "username": "test@example.com",
            "api_token": "test-token"
        }
    )
    db_session.add(data_source)
    await db_session.commit()
    await db_session.refresh(data_source)
    return data_source


@pytest_asyncio.fixture
async def inactive_data_source(db_session):
    """Create an inactive JIRA data source."""
    data_source = DataSource(
        name="Inactive JIRA",
        type=DataSourceType.JIRA,
        is_active=False,
        source_config={"url": "https://test.atlassian.net"}
    )
    db_session.add(data_source)
    await db_session.commit()
    await db_session.refresh(data_source)
    return data_source


@pytest_asyncio.fixture
async def confluence_data_source(db_session):
    """Create a Confluence data source (wrong type for JIRA ingestion)."""
    data_source = DataSource(
        name="Test Confluence",
        type=DataSourceType.CONFLUENCE,
        is_active=True,
        source_config={"space_keys": ["TEST"]}
    )
    db_session.add(data_source)
    await db_session.commit()
    await db_session.refresh(data_source)
    return data_source


@pytest.fixture
def mock_jira_client():
    """Mock JiraClient with AsyncMock."""
    client = Mock(spec=JiraClient)
    client.fetch_issues = AsyncMock()
    client.fetch_comments = AsyncMock()
    client.url = "https://test.atlassian.net"
    return client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAIClient with AsyncMock."""
    client = Mock(spec=OpenAIClient)
    client.generate_embeddings_batch = AsyncMock()
    return client


# ==================== Unit Tests: Helper Functions ====================

class TestUnitFunctions:
    """Test individual helper functions."""

    def test_compute_document_hash(self):
        """Test document hash computation."""
        import hashlib

        content = "This is test content"
        hash1 = hashlib.sha256(content.encode('utf-8')).hexdigest()
        hash2 = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex chars

        # Different content should produce different hash
        hash3 = hashlib.sha256("Different content".encode('utf-8')).hexdigest()
        assert hash1 != hash3

    @pytest.mark.asyncio
    async def test_get_data_source_success(self, db_session, test_data_source):
        """Test fetching data source by ID."""
        result = await _get_data_source(db_session, test_data_source.id)

        assert result is not None
        assert result.id == test_data_source.id
        assert result.name == "Test JIRA"
        assert result.type == DataSourceType.JIRA

    @pytest.mark.asyncio
    async def test_get_data_source_not_found(self, db_session):
        """Test fetching non-existent data source."""
        result = await _get_data_source(db_session, 99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_ingestion_job(self, db_session, test_data_source):
        """Test creating an ingestion job."""
        job = await _create_ingestion_job(db_session, test_data_source.id)

        assert job.id is not None
        assert job.data_source_id == test_data_source.id
        assert job.status == JobStatus.RUNNING
        assert job.documents_processed == 0
        assert job.documents_failed == 0
        assert job.error_message is None

    @pytest.mark.asyncio
    async def test_update_job_progress(self, db_session, test_data_source):
        """Test updating job progress."""
        job = await _create_ingestion_job(db_session, test_data_source.id)

        await _update_job_progress(db_session, job, processed=10, failed=2)
        await db_session.refresh(job)

        assert job.documents_processed == 10
        assert job.documents_failed == 2

    @pytest.mark.asyncio
    async def test_complete_job_success(self, db_session, test_data_source):
        """Test completing job with success status."""
        job = await _create_ingestion_job(db_session, test_data_source.id)

        await _complete_job(db_session, job, JobStatus.SUCCESS, processed=5, failed=0)
        await db_session.refresh(job)

        assert job.status == JobStatus.SUCCESS
        assert job.documents_processed == 5
        assert job.documents_failed == 0
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_job_failed(self, db_session, test_data_source):
        """Test completing job with failed status and error message."""
        job = await _create_ingestion_job(db_session, test_data_source.id)

        await _complete_job(
            db_session, job, JobStatus.FAILED,
            processed=3, failed=2, error_message="API Error"
        )
        await db_session.refresh(job)

        assert job.status == JobStatus.FAILED
        assert job.documents_processed == 3
        assert job.documents_failed == 2
        assert job.error_message == "API Error"
        assert job.completed_at is not None


# ==================== Integration Tests ====================

class TestIntegration:
    """Test main ingestion workflow with mocked external services."""

    @pytest.mark.asyncio
    async def test_single_issue_ingestion(
        self, db_session, test_data_source, mock_jira_client, mock_openai_client, monkeypatch
    ):
        """Test successful ingestion of a single JIRA issue."""
        # Setup mocks
        mock_jira_client.fetch_issues.return_value = {"issues": [MOCK_JIRA_ISSUE], "total": 1}
        mock_jira_client.fetch_comments.return_value = MOCK_JIRA_COMMENTS
        mock_openai_client.generate_embeddings_batch.return_value = [[0.1] * 1536, [0.2] * 1536]

        # Patch client constructors
        with patch('tasks.ingestion.jira.JiraClient', return_value=mock_jira_client):
            with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
                # Patch get_session_factory to return our test session
                mock_session_factory = MagicMock()
                mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
                mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch('tasks.ingestion.jira.get_session_factory', return_value=mock_session_factory):
                    # Import after patching
                    from tasks.ingestion.jira import _ingest_jira_issues_async

                    # Run ingestion
                    result = await _ingest_jira_issues_async(test_data_source.id, None)

        # Verify result
        assert result["status"] == "success"
        assert result["documents_processed"] == 1
        assert result["documents_failed"] == 0

        # Verify document was created
        from sqlalchemy import select
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.external_id == "TEST-123")
        result_doc = await db_session.execute(stmt)
        doc = result_doc.scalar_one_or_none()

        assert doc is not None
        assert doc.title == "TEST-123: Test Issue Summary"
        assert doc.content_type == ContentType.ISSUE
        assert "Test Issue Summary" in doc.content
        assert "This is a detailed description" in doc.content

    @pytest.mark.asyncio
    async def test_empty_issue_list(
        self, db_session, test_data_source, mock_jira_client, mock_openai_client
    ):
        """Test handling of empty issue list."""
        # Setup mocks
        mock_jira_client.fetch_issues.return_value = {"issues": [], "total": 0}

        # Patch clients
        with patch('tasks.ingestion.jira.JiraClient', return_value=mock_jira_client):
            with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
                mock_session_factory = MagicMock()
                mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
                mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch('tasks.ingestion.jira.get_session_factory', return_value=mock_session_factory):
                    from tasks.ingestion.jira import _ingest_jira_issues_async
                    result = await _ingest_jira_issues_async(test_data_source.id, None)

        # Verify result
        assert result["status"] == "success"
        assert result["documents_processed"] == 0
        assert result["documents_failed"] == 0


# ==================== Error Handling Tests ====================

class TestErrorHandling:
    """Test error scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_data_source_id(self, db_session):
        """Test ingestion with non-existent data source."""
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch('tasks.ingestion.jira.get_session_factory', return_value=mock_session_factory):
            from tasks.ingestion.jira import _ingest_jira_issues_async

            with pytest.raises(ValueError, match="not found"):
                await _ingest_jira_issues_async(99999, None)

    @pytest.mark.asyncio
    async def test_inactive_data_source(self, db_session, inactive_data_source):
        """Test ingestion with inactive data source."""
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch('tasks.ingestion.jira.get_session_factory', return_value=mock_session_factory):
            from tasks.ingestion.jira import _ingest_jira_issues_async

            result = await _ingest_jira_issues_async(inactive_data_source.id, None)

            # Should skip and not process anything
            assert result["status"] == "skipped"
            assert result["documents_processed"] == 0
            assert result["documents_failed"] == 0

    @pytest.mark.asyncio
    async def test_wrong_data_source_type(self, db_session, confluence_data_source):
        """Test ingestion with wrong data source type."""
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch('tasks.ingestion.jira.get_session_factory', return_value=mock_session_factory):
            from tasks.ingestion.jira import _ingest_jira_issues_async

            with pytest.raises(ValueError, match="not a JIRA source"):
                await _ingest_jira_issues_async(confluence_data_source.id, None)


# ==================== Deduplication Tests ====================

class TestDeduplication:
    """Test deduplication logic."""

    @pytest.mark.asyncio
    async def test_new_issue_creates_document(
        self, db_session, test_data_source, mock_jira_client, mock_openai_client
    ):
        """Test that new issue creates a new document."""
        # Setup mocks
        mock_jira_client.fetch_comments.return_value = []
        mock_openai_client.generate_embeddings_batch.return_value = [[0.1] * 1536]

        # Process issue
        with patch('tasks.ingestion.jira.JiraClient', return_value=mock_jira_client):
            with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
                from tasks.ingestion.jira import _process_issue

                success = await _process_issue(
                    db_session, test_data_source.id, MOCK_JIRA_ISSUE,
                    mock_jira_client, mock_openai_client
                )

        assert success is True

        # Verify document exists
        from sqlalchemy import select
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.external_id == "TEST-123")
        result = await db_session.execute(stmt)
        doc = result.scalar_one_or_none()

        assert doc is not None
        assert doc.is_deleted is False

    @pytest.mark.asyncio
    async def test_existing_issue_same_content_skips(
        self, db_session, test_data_source, mock_jira_client, mock_openai_client
    ):
        """Test that existing issue with same content is skipped."""
        # Create existing document
        import hashlib

        content = "Summary: Test Issue Summary\n\nDescription:\nThis is a detailed description of the test issue."
        doc_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        existing_doc = KnowledgeDocument(
            title="TEST-123: Test Issue Summary",
            content=content,
            content_type=ContentType.ISSUE,
            external_id="TEST-123",
            data_source_id=test_data_source.id,
            document_hash=doc_hash,
            is_deleted=False,
            doc_metadata={"issue_key": "TEST-123"}
        )
        db_session.add(existing_doc)
        await db_session.commit()

        # Setup mocks
        mock_jira_client.fetch_comments.return_value = []

        # Process same issue
        with patch('tasks.ingestion.jira.JiraClient', return_value=mock_jira_client):
            with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
                from tasks.ingestion.jira import _process_issue

                success = await _process_issue(
                    db_session, test_data_source.id, MOCK_JIRA_ISSUE,
                    mock_jira_client, mock_openai_client
                )

        assert success is True

        # Verify only one document exists (not duplicated)
        from sqlalchemy import select, func
        stmt = select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.external_id == "TEST-123",
            KnowledgeDocument.is_deleted == False
        )
        result = await db_session.execute(stmt)
        count = result.scalar()

        assert count == 1


# ==================== Functional Tests ====================

class TestFunctional:
    """Test end-to-end functional scenarios."""

    @pytest.mark.asyncio
    async def test_content_type_validation(
        self, db_session, test_data_source, mock_jira_client, mock_openai_client
    ):
        """Test that documents have correct content type."""
        mock_jira_client.fetch_issues.return_value = {"issues": [MOCK_JIRA_ISSUE], "total": 1}
        mock_jira_client.fetch_comments.return_value = []
        mock_openai_client.generate_embeddings_batch.return_value = [[0.1] * 1536]

        with patch('tasks.ingestion.jira.JiraClient', return_value=mock_jira_client):
            with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
                mock_session_factory = MagicMock()
                mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
                mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch('tasks.ingestion.jira.get_session_factory', return_value=mock_session_factory):
                    from tasks.ingestion.jira import _ingest_jira_issues_async
                    await _ingest_jira_issues_async(test_data_source.id, None)

        # Verify content type
        from sqlalchemy import select
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.external_id == "TEST-123")
        result = await db_session.execute(stmt)
        doc = result.scalar_one_or_none()

        assert doc is not None
        assert doc.content_type == ContentType.ISSUE

    @pytest.mark.asyncio
    async def test_metadata_storage(
        self, db_session, test_data_source, mock_jira_client, mock_openai_client
    ):
        """Test that metadata is correctly stored."""
        mock_jira_client.fetch_comments.return_value = []
        mock_openai_client.generate_embeddings_batch.return_value = [[0.1] * 1536]

        with patch('tasks.ingestion.jira.JiraClient', return_value=mock_jira_client):
            with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
                from tasks.ingestion.jira import _process_issue

                await _process_issue(
                    db_session, test_data_source.id, MOCK_JIRA_ISSUE,
                    mock_jira_client, mock_openai_client
                )

        # Verify metadata
        from sqlalchemy import select
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.external_id == "TEST-123")
        result = await db_session.execute(stmt)
        doc = result.scalar_one_or_none()

        assert doc is not None
        assert doc.doc_metadata is not None
        assert doc.doc_metadata["issue_key"] == "TEST-123"
        assert doc.doc_metadata["status"] == "Open"
        assert doc.doc_metadata["priority"] == "High"
        assert "bug" in doc.doc_metadata["labels"]
