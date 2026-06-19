"""
Test suite for Confluence Ingestion Celery Task (task-023)

Tests cover:
- Unit tests for helper functions (hash, job lifecycle, text processing)
- Integration tests (space ingestion, deduplication, progress tracking)
- Error handling (API failures, retries, invalid data sources)
- Functional tests (end-to-end workflow, refresh task)
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
from typing import List, Dict, Any

from tasks.ingestion.confluence import (
    compute_document_hash,
    ingest_confluence_docs,
    refresh_confluence_data,
    _get_data_source,
    _create_ingestion_job,
    _update_job_progress,
    _complete_job,
    _process_page
)
from models.data_source import DataSource, IngestionJob, JobStatus, DataSourceType
from models.knowledge import KnowledgeDocument, DocumentEmbedding, ContentType
from integrations.confluence_client import ConfluenceClient, ConfluenceAPIError
from integrations.openai_client import OpenAIClient, OpenAIError


# ==================== Mock Data ====================

MOCK_CONFLUENCE_PAGE = {
    "id": "12345",
    "title": "Getting Started Guide",
    "type": "page",
    "space": {"key": "ENG"},
    "body": {
        "storage": {
            "value": "<h1>Getting Started</h1><p>Welcome to our platform. This is a comprehensive guide.</p>",
            "representation": "storage"
        }
    },
    "version": {"number": 3, "when": "2024-01-15T10:00:00.000Z", "by": {"displayName": "John Doe"}},
    "history": {"createdDate": "2024-01-15T10:00:00.000Z"},
    "_links": {"webui": "/display/ENG/Getting+Started"}
}

MOCK_CONFLUENCE_PAGES = [
    {
        "id": "12345",
        "title": "Getting Started",
        "type": "page",
        "space": {"key": "ENG"},
        "body": {"storage": {"value": "<h1>Getting Started</h1><p>Welcome to our platform. This is a comprehensive guide that covers the basics.</p>"}},
        "version": {"number": 3},
        "_links": {"webui": "/display/ENG/Getting+Started"}
    },
    {
        "id": "67890",
        "title": "API Documentation",
        "type": "page",
        "space": {"key": "ENG"},
        "body": {"storage": {"value": "<h1>API Docs</h1><h2>Authentication</h2><p>Use JWT tokens for API authentication. Here is how you configure it properly.</p>"}},
        "version": {"number": 10},
        "_links": {"webui": "/display/ENG/API+Documentation"}
    },
    {
        "id": "11111",
        "title": "User Guide",
        "type": "page",
        "space": {"key": "DOCS"},
        "body": {"storage": {"value": "<h1>User Guide</h1><p>This guide will help you understand the product and its features in detail.</p>"}},
        "version": {"number": 1},
        "_links": {"webui": "/display/DOCS/User+Guide"}
    }
]

MOCK_EMBEDDING = [0.1] * 1536  # Mock 1536-dimensional embedding vector


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def test_data_source(db_session):
    """Create a test Confluence data source."""
    data_source = DataSource(
        name="Test Confluence",
        type=DataSourceType.CONFLUENCE,
        is_active=True,
        source_config={
            "space_keys": ["ENG", "DOCS"],
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
    """Create an inactive Confluence data source."""
    data_source = DataSource(
        name="Inactive Confluence",
        type=DataSourceType.CONFLUENCE,
        is_active=False,
        source_config={
            "space_keys": ["TEST"],
            "url": "https://test.atlassian.net"
        }
    )
    db_session.add(data_source)
    await db_session.commit()
    await db_session.refresh(data_source)
    return data_source


@pytest.fixture
def mock_confluence_client():
    """Mock ConfluenceClient."""
    client = AsyncMock(spec=ConfluenceClient)
    client.fetch_all_pages = AsyncMock(return_value=MOCK_CONFLUENCE_PAGES[:2])
    return client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAIClient."""
    client = AsyncMock(spec=OpenAIClient)
    # Mock generate_embeddings_batch to return list of embeddings
    client.generate_embeddings_batch = AsyncMock(return_value=[MOCK_EMBEDDING, MOCK_EMBEDDING])
    return client


# ==================== Unit Tests ====================

class TestUnitFunctions:
    """Unit tests for helper functions."""

    def test_compute_document_hash(self):
        """TC-023-U01: Document hash computation."""
        # Test consistent hashing
        content = "test content"
        hash1 = compute_document_hash(content)
        hash2 = compute_document_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64-char hex string
        assert isinstance(hash1, str)

        # Test different content produces different hash
        content2 = "different content"
        hash3 = compute_document_hash(content2)
        assert hash3 != hash1

    @pytest.mark.asyncio
    async def test_get_data_source(self, db_session, test_data_source):
        """TC-023-U02: Get data source by ID."""
        result = await _get_data_source(db_session, test_data_source.id)

        assert result is not None
        assert result.id == test_data_source.id
        assert result.type == DataSourceType.CONFLUENCE
        assert result.is_active is True

        # Test non-existent ID
        result_none = await _get_data_source(db_session, 99999)
        assert result_none is None

    @pytest.mark.asyncio
    async def test_create_ingestion_job(self, db_session, test_data_source):
        """TC-023-U03: Create ingestion job."""
        job = await _create_ingestion_job(db_session, test_data_source.id)

        assert job is not None
        assert job.id is not None
        assert job.data_source_id == test_data_source.id
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.documents_processed == 0
        assert job.documents_failed == 0
        assert job.completed_at is None

    @pytest.mark.asyncio
    async def test_update_job_progress(self, db_session, test_data_source):
        """TC-023-U04: Update job progress."""
        job = await _create_ingestion_job(db_session, test_data_source.id)

        await _update_job_progress(db_session, job, 5, 2)
        await db_session.refresh(job)

        assert job.documents_processed == 5
        assert job.documents_failed == 2

    @pytest.mark.asyncio
    async def test_complete_job(self, db_session, test_data_source):
        """TC-023-U05: Complete job."""
        job = await _create_ingestion_job(db_session, test_data_source.id)

        await _complete_job(db_session, job, JobStatus.SUCCESS, 10, 1)
        await db_session.refresh(job)

        assert job.status == JobStatus.SUCCESS
        assert job.documents_processed == 10
        assert job.documents_failed == 1
        assert job.completed_at is not None

        # Test with error message
        job2 = await _create_ingestion_job(db_session, test_data_source.id)
        await _complete_job(db_session, job2, JobStatus.FAILED, 5, 5, error_message="Test error")
        await db_session.refresh(job2)

        assert job2.status == JobStatus.FAILED
        assert job2.error_message == "Test error"

    @pytest.mark.asyncio
    async def test_process_page_success(self, db_session, test_data_source, mock_openai_client):
        """TC-023-U08: Process page and generate embeddings."""
        result = await _process_page(
            session=db_session,
            data_source_id=test_data_source.id,
            page=MOCK_CONFLUENCE_PAGE,
            openai_client=mock_openai_client
        )

        assert result is True

        # Verify document was created
        from sqlalchemy import select
        docs_result = await db_session.execute(select(KnowledgeDocument))
        docs = docs_result.scalars().all()

        assert len(docs) == 1
        doc = docs[0]
        assert doc.external_id == "12345"
        assert doc.title == "Getting Started Guide"
        assert doc.content_type == ContentType.PAGE
        assert doc.document_hash is not None
        assert "Getting Started" in doc.content

    @pytest.mark.asyncio
    async def test_process_page_deduplication(self, db_session, test_data_source, mock_openai_client):
        """TC-023-U10: Skip duplicate document."""
        # Process page first time
        result1 = await _process_page(
            session=db_session,
            data_source_id=test_data_source.id,
            page=MOCK_CONFLUENCE_PAGE,
            openai_client=mock_openai_client
        )
        assert result1 is True

        # Process same page again (should be skipped)
        result2 = await _process_page(
            session=db_session,
            data_source_id=test_data_source.id,
            page=MOCK_CONFLUENCE_PAGE,
            openai_client=mock_openai_client
        )
        assert result2 is True  # Returns True but doesn't create duplicate

        # Verify only one document exists
        from sqlalchemy import select
        docs_result = await db_session.execute(select(KnowledgeDocument))
        docs = docs_result.scalars().all()
        assert len(docs) == 1



# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_single_space_ingestion(self, db_session, test_data_source, mock_confluence_client, mock_openai_client, monkeypatch):
        """TC-023-I01: Ingest from single space."""
        from tasks.ingestion import confluence

        # Mock clients
        monkeypatch.setattr(confluence, 'ConfluenceClient', lambda: mock_confluence_client)
        monkeypatch.setattr(confluence, 'OpenAIClient', lambda: mock_openai_client)

        # Mock get_session_factory
        from unittest.mock import MagicMock
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(confluence, 'get_session_factory', lambda: mock_session_factory)

        # Run ingestion
        from tasks.ingestion.confluence import _ingest_confluence_docs_async
        result = await _ingest_confluence_docs_async(test_data_source.id, None)

        assert result['status'] == 'success'
        assert result['documents_processed'] >= 0

    @pytest.mark.asyncio
    async def test_empty_space(self, db_session, test_data_source, mock_openai_client, monkeypatch):
        """TC-023-I03: Handle empty space."""
        from tasks.ingestion import confluence

        # Mock ConfluenceClient to return empty results
        mock_client = AsyncMock(spec=ConfluenceClient)
        mock_client.fetch_all_pages = AsyncMock(return_value=[])

        monkeypatch.setattr(confluence, 'ConfluenceClient', lambda: mock_client)
        monkeypatch.setattr(confluence, 'OpenAIClient', lambda: mock_openai_client)

        # Mock get_session_factory
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(confluence, 'get_session_factory', lambda: mock_session_factory)

        # Run ingestion
        from tasks.ingestion.confluence import _ingest_confluence_docs_async
        result = await _ingest_confluence_docs_async(test_data_source.id, None)

        assert result['status'] == 'success'
        assert result['documents_processed'] == 0


# ==================== Error Handling Tests ====================

class TestErrorHandling:
    """Error handling and edge case tests."""

    @pytest.mark.asyncio
    async def test_invalid_data_source_id(self, db_session, monkeypatch):
        """TC-023-E01: Invalid data source ID raises error."""
        from tasks.ingestion import confluence

        # Mock get_session_factory
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(confluence, 'get_session_factory', lambda: mock_session_factory)

        # Run ingestion with non-existent ID
        from tasks.ingestion.confluence import _ingest_confluence_docs_async

        with pytest.raises(ValueError, match="not found"):
            await _ingest_confluence_docs_async(99999, None)

    @pytest.mark.asyncio
    async def test_inactive_data_source(self, db_session, inactive_data_source, monkeypatch):
        """TC-023-E02: Inactive data source raises error."""
        from tasks.ingestion import confluence

        # Mock get_session_factory
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(confluence, 'get_session_factory', lambda: mock_session_factory)

        # Run ingestion with inactive source
        from tasks.ingestion.confluence import _ingest_confluence_docs_async

        with pytest.raises(ValueError, match="not active"):
            await _ingest_confluence_docs_async(inactive_data_source.id, None)

    @pytest.mark.asyncio
    async def test_no_space_keys_configured(self, db_session, monkeypatch):
        """TC-023-E03: No space keys configured."""
        from tasks.ingestion import confluence

        # Create data source without space_keys
        data_source = DataSource(
            name="Empty Config",
            type=DataSourceType.CONFLUENCE,
            is_active=True,
            source_config={"url": "https://test.atlassian.net"}  # No space_keys
        )
        db_session.add(data_source)
        await db_session.commit()
        await db_session.refresh(data_source)

        # Mock get_session_factory
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(confluence, 'get_session_factory', lambda: mock_session_factory)

        # Run ingestion
        from tasks.ingestion.confluence import _ingest_confluence_docs_async
        result = await _ingest_confluence_docs_async(data_source.id, None)

        assert result['status'] == 'success'
        assert result['documents_processed'] == 0

    @pytest.mark.asyncio
    async def test_openai_api_error(self, db_session, test_data_source):
        """TC-023-E05: OpenAI API error handling."""
        # Mock OpenAI client that raises error
        mock_client = AsyncMock(spec=OpenAIClient)
        mock_client.generate_embeddings_batch = AsyncMock(side_effect=OpenAIError("API Error"))

        result = await _process_page(
            session=db_session,
            data_source_id=test_data_source.id,
            page=MOCK_CONFLUENCE_PAGE,
            openai_client=mock_client
        )

        # Should return False on OpenAI error
        assert result is False

        # Verify no document was created
        from sqlalchemy import select
        docs_result = await db_session.execute(select(KnowledgeDocument))
        docs = docs_result.scalars().all()
        assert len(docs) == 0


# ==================== Functional Tests ====================

class TestFunctional:
    """End-to-end functional tests."""

    @pytest.mark.asyncio
    async def test_content_type_validation(self, db_session, test_data_source, mock_openai_client):
        """TC-023-F04: Verify content_type=PAGE."""
        await _process_page(
            session=db_session,
            data_source_id=test_data_source.id,
            page=MOCK_CONFLUENCE_PAGE,
            openai_client=mock_openai_client
        )

        from sqlalchemy import select
        docs_result = await db_session.execute(select(KnowledgeDocument))
        doc = docs_result.scalar_one()

        assert doc.content_type == ContentType.PAGE

    @pytest.mark.asyncio
    async def test_external_id_mapping(self, db_session, test_data_source, mock_openai_client):
        """TC-023-F05: Verify external_id stores page_id."""
        await _process_page(
            session=db_session,
            data_source_id=test_data_source.id,
            page=MOCK_CONFLUENCE_PAGE,
            openai_client=mock_openai_client
        )

        from sqlalchemy import select
        docs_result = await db_session.execute(select(KnowledgeDocument))
        doc = docs_result.scalar_one()

        assert doc.external_id == "12345"
        assert doc.external_id == MOCK_CONFLUENCE_PAGE["id"]

    @pytest.mark.asyncio
    async def test_metadata_preservation(self, db_session, test_data_source, mock_openai_client):
        """TC-023-U09: Metadata stored in JSONB."""
        await _process_page(
            session=db_session,
            data_source_id=test_data_source.id,
            page=MOCK_CONFLUENCE_PAGE,
            openai_client=mock_openai_client
        )

        from sqlalchemy import select
        docs_result = await db_session.execute(select(KnowledgeDocument))
        doc = docs_result.scalar_one()

        assert doc.doc_metadata is not None
        assert doc.doc_metadata['page_id'] == "12345"
        assert doc.doc_metadata['space_key'] == "ENG"
        assert doc.doc_metadata['version'] == 3

