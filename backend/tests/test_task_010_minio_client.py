"""
Test suite for MinIO Client (Task 010)

Tests MinIO client initialization, bucket management, file operations,
and health checks using mocked MinIO client.
"""

import io
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from minio.error import S3Error
from urllib3.exceptions import MaxRetryError

from core.minio_client import (
    get_minio_client,
    init_minio,
    check_minio_health,
    upload_file,
    download_file,
    delete_file,
    get_file_info,
    list_files,
    detect_content_type,
    BUCKET_KNOWLEDGE_FILES,
    BUCKET_EMBEDDINGS_BACKUP,
    BUCKET_AUDIT_LOGS,
    REQUIRED_BUCKETS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_minio_client():
    """Reset the global MinIO client before each test."""
    import core.minio_client
    core.minio_client._minio_client = None
    yield
    core.minio_client._minio_client = None


@pytest.fixture
def mock_minio():
    """Mock MinIO client with common responses."""
    with patch('core.minio_client.Minio') as mock_minio_class:
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        
        # Setup default behaviors
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = False
        mock_client.make_bucket.return_value = None
        
        yield mock_client


# ============================================================================
# Test Case TC-A1: Client Initialization & Singleton Pattern
# ============================================================================

def test_singleton_pattern(mock_minio):
    """TC-A1: MinIO client singleton pattern - same instance returned."""
    client1 = get_minio_client()
    client2 = get_minio_client()
    
    assert client1 is client2, "Should return the same instance"
    assert mock_minio == client1, "Should return mocked client"


def test_client_configuration(mock_minio):
    """TC-A2: Client configuration from environment variables."""
    with patch('core.minio_client.Minio') as mock_minio_class:
        get_minio_client()
        
        # Verify Minio was called with correct settings
        mock_minio_class.assert_called_once()
        call_kwargs = mock_minio_class.call_args[1]
        
        # Check that settings are used (actual values depend on environment)
        assert 'endpoint' in call_kwargs
        assert 'access_key' in call_kwargs
        assert 'secret_key' in call_kwargs
        assert 'secure' in call_kwargs


# ============================================================================
# Test Case TC-B1: Bucket Management
# ============================================================================

def test_init_minio_creates_buckets(mock_minio):
    """TC-B1: Initialize MinIO and create all required buckets."""
    # Setup: No buckets exist initially
    mock_minio.bucket_exists.return_value = False
    mock_minio.list_buckets.return_value = []
    
    # Execute
    init_minio()
    
    # Verify all buckets were created
    assert mock_minio.make_bucket.call_count == 3
    created_buckets = [call[0][0] for call in mock_minio.make_bucket.call_args_list]
    assert BUCKET_KNOWLEDGE_FILES in created_buckets
    assert BUCKET_EMBEDDINGS_BACKUP in created_buckets
    assert BUCKET_AUDIT_LOGS in created_buckets


def test_init_minio_idempotent(mock_minio):
    """TC-B3: Handle bucket creation when buckets already exist (idempotent)."""
    # Setup: All buckets already exist
    mock_minio.bucket_exists.return_value = True
    mock_minio.list_buckets.return_value = [
        MagicMock(name=BUCKET_KNOWLEDGE_FILES),
        MagicMock(name=BUCKET_EMBEDDINGS_BACKUP),
        MagicMock(name=BUCKET_AUDIT_LOGS),
    ]
    
    # Execute
    init_minio()
    
    # Verify no buckets were created
    mock_minio.make_bucket.assert_not_called()


# ============================================================================
# Test Case TC-C: File Upload Operations
# ============================================================================

def test_upload_file_with_auto_content_type(mock_minio):
    """TC-C1: Upload file with auto-detected content type (PDF)."""
    file_data = io.BytesIO(b"%PDF-1.4 test content")
    file_size = len(file_data.getvalue())
    
    result = upload_file(
        bucket_name=BUCKET_KNOWLEDGE_FILES,
        object_name="test.pdf",
        file_data=file_data,
        file_size=file_size
    )
    
    assert result is True
    mock_minio.put_object.assert_called_once()
    call_kwargs = mock_minio.put_object.call_args[1]
    assert call_kwargs['content_type'] == "application/pdf"


def test_upload_file_with_manual_content_type(mock_minio):
    """TC-C2: Upload file with manually specified content type."""
    file_data = io.BytesIO(b"test content")
    file_size = len(file_data.getvalue())
    
    result = upload_file(
        bucket_name=BUCKET_KNOWLEDGE_FILES,
        object_name="test.bin",
        file_data=file_data,
        file_size=file_size,
        content_type="application/custom"
    )
    
    assert result is True
    call_kwargs = mock_minio.put_object.call_args[1]
    assert call_kwargs['content_type'] == "application/custom"


def test_upload_file_unknown_extension(mock_minio):
    """TC-C3: Upload file with unknown extension (default content type)."""
    file_data = io.BytesIO(b"unknown content")
    file_size = len(file_data.getvalue())

    # Use a truly unknown extension that's not in mimetypes database
    result = upload_file(
        bucket_name=BUCKET_KNOWLEDGE_FILES,
        object_name="unknown.unknownext123",
        file_data=file_data,
        file_size=file_size
    )

    assert result is True
    call_kwargs = mock_minio.put_object.call_args[1]
    assert call_kwargs['content_type'] == "application/octet-stream"


# ============================================================================
# Test Case TC-D: File Download Operations
# ============================================================================

def test_download_file_success(mock_minio):
    """TC-D1: Download existing file successfully."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.read.return_value = b"Test PDF content"
    mock_minio.get_object.return_value = mock_response

    # Execute
    response = download_file(BUCKET_KNOWLEDGE_FILES, "document.pdf")

    # Verify
    assert response is not None
    assert response.read() == b"Test PDF content"
    mock_minio.get_object.assert_called_once_with(BUCKET_KNOWLEDGE_FILES, "document.pdf")


def test_download_file_not_found(mock_minio):
    """TC-D2: Download non-existent file returns None."""
    # Setup: Simulate NoSuchKey error
    s3_error = S3Error(
        code="NoSuchKey",
        message="The specified key does not exist.",
        resource="/knowledge-files/missing.pdf",
        request_id="test-request-id",
        host_id="test-host-id",
        response=MagicMock()
    )
    mock_minio.get_object.side_effect = s3_error

    # Execute
    result = download_file(BUCKET_KNOWLEDGE_FILES, "missing.pdf")

    # Verify
    assert result is None


# ============================================================================
# Test Case TC-E: File Deletion Operations
# ============================================================================

def test_delete_file_success(mock_minio):
    """TC-E1: Delete existing file successfully."""
    mock_minio.remove_object.return_value = None

    result = delete_file(BUCKET_KNOWLEDGE_FILES, "test.txt")

    assert result is True
    mock_minio.remove_object.assert_called_once_with(BUCKET_KNOWLEDGE_FILES, "test.txt")


def test_delete_file_idempotent(mock_minio):
    """TC-E2: Delete non-existent file (idempotent - returns True)."""
    # Setup: Simulate NoSuchKey error
    s3_error = S3Error(
        code="NoSuchKey",
        message="The specified key does not exist.",
        resource="/knowledge-files/nonexistent.pdf",
        request_id="test-request-id",
        host_id="test-host-id",
        response=MagicMock()
    )
    mock_minio.remove_object.side_effect = s3_error

    result = delete_file(BUCKET_KNOWLEDGE_FILES, "nonexistent.pdf")

    # Returns True even if file doesn't exist (idempotent)
    assert result is True


# ============================================================================
# Test Case TC-F: Health Check
# ============================================================================

def test_health_check_success(mock_minio):
    """TC-F1: Health check passes when MinIO is available and buckets exist."""
    # Setup: All buckets exist - need to set .name attribute properly
    mock_bucket1 = MagicMock()
    mock_bucket1.name = BUCKET_KNOWLEDGE_FILES
    mock_bucket2 = MagicMock()
    mock_bucket2.name = BUCKET_EMBEDDINGS_BACKUP
    mock_bucket3 = MagicMock()
    mock_bucket3.name = BUCKET_AUDIT_LOGS

    mock_minio.list_buckets.return_value = [mock_bucket1, mock_bucket2, mock_bucket3]

    result = check_minio_health()

    assert result is True


def test_health_check_missing_buckets(mock_minio):
    """TC-F3: Health check fails when required buckets are missing."""
    # Setup: Only some buckets exist
    mock_buckets = [
        MagicMock(name=BUCKET_KNOWLEDGE_FILES),
    ]
    mock_minio.list_buckets.return_value = mock_buckets

    result = check_minio_health()

    assert result is False


def test_health_check_connection_failure(mock_minio):
    """TC-F2: Health check fails when MinIO is unavailable."""
    # Setup: Connection error
    mock_minio.list_buckets.side_effect = Exception("Connection refused")

    result = check_minio_health()

    assert result is False


# ============================================================================
# Test Case TC-G: File Metadata & Listing
# ============================================================================

def test_get_file_info_success(mock_minio):
    """TC-G1: Get file metadata (size, content_type, last_modified)."""
    # Setup mock stat object
    mock_stat = MagicMock()
    mock_stat.size = 1024
    mock_stat.etag = "abc123"
    mock_stat.content_type = "application/pdf"
    mock_stat.last_modified = datetime(2024, 1, 1, 12, 0, 0)
    mock_stat.metadata = {}
    mock_minio.stat_object.return_value = mock_stat

    # Execute
    info = get_file_info(BUCKET_KNOWLEDGE_FILES, "metadata_test.pdf")

    # Verify
    assert info is not None
    assert info['size'] == 1024
    assert info['content_type'] == "application/pdf"
    assert info['bucket'] == BUCKET_KNOWLEDGE_FILES
    assert info['object_name'] == "metadata_test.pdf"


def test_get_file_info_not_found(mock_minio):
    """TC-G2: Get metadata for non-existent file returns None."""
    s3_error = S3Error(
        code="NoSuchKey",
        message="The specified key does not exist.",
        resource="/knowledge-files/missing.pdf",
        request_id="test-request-id",
        host_id="test-host-id",
        response=MagicMock()
    )
    mock_minio.stat_object.side_effect = s3_error

    result = get_file_info(BUCKET_KNOWLEDGE_FILES, "missing.pdf")

    assert result is None


def test_list_files_with_prefix(mock_minio):
    """TC-G4: List files with prefix filter."""
    # Setup mock objects
    mock_obj1 = MagicMock()
    mock_obj1.object_name = "docs/file1.pdf"
    mock_obj2 = MagicMock()
    mock_obj2.object_name = "docs/file2.pdf"

    mock_minio.list_objects.return_value = [mock_obj1, mock_obj2]

    # Execute
    files = list_files(BUCKET_KNOWLEDGE_FILES, prefix="docs/")

    # Verify
    assert len(files) == 2
    assert "docs/file1.pdf" in files
    assert "docs/file2.pdf" in files


def test_list_files_empty_bucket(mock_minio):
    """TC-G5: List files in empty bucket."""
    mock_minio.list_objects.return_value = []

    files = list_files(BUCKET_KNOWLEDGE_FILES, prefix="")

    assert files == []


# ============================================================================
# Test Case TC-H: Content Type Detection
# ============================================================================

def test_detect_content_type_pdf():
    """TC-H1: Detect PDF content type."""
    content_type = detect_content_type("document.pdf")
    assert content_type == "application/pdf"


def test_detect_content_type_images():
    """TC-H2: Detect image content types (PNG, JPEG, GIF)."""
    assert detect_content_type("image.png") == "image/png"
    assert detect_content_type("photo.jpeg") == "image/jpeg"
    assert detect_content_type("photo.jpg") == "image/jpeg"
    assert detect_content_type("animation.gif") == "image/gif"


def test_detect_content_type_documents():
    """TC-H3: Detect document types (DOCX, TXT)."""
    assert detect_content_type("document.txt") == "text/plain"
    # DOCX detection depends on mimetypes database
    docx_type = detect_content_type("document.docx")
    assert docx_type in [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream"
    ]


def test_detect_content_type_unknown():
    """TC-H4: Default to 'application/octet-stream' for unknown types."""
    # Use a truly unknown extension that's not in mimetypes database
    content_type = detect_content_type("unknown.unknownext123")
    assert content_type == "application/octet-stream"


# ============================================================================
# Test Case TC-I: Error Handling
# ============================================================================

def test_init_minio_connection_error(mock_minio):
    """TC-I4: Handle MaxRetryError during initialization."""
    mock_minio.list_buckets.side_effect = MaxRetryError(
        pool=None,
        url="http://minio:9000"
    )

    with pytest.raises(MaxRetryError):
        init_minio()


def test_upload_file_s3_error(mock_minio):
    """TC-I3: Handle S3Error during upload operations."""
    s3_error = S3Error(
        code="AccessDenied",
        message="Access Denied",
        resource="/knowledge-files/test.pdf",
        request_id="test-request-id",
        host_id="test-host-id",
        response=MagicMock()
    )
    mock_minio.put_object.side_effect = s3_error

    file_data = io.BytesIO(b"test")

    with pytest.raises(S3Error):
        upload_file(BUCKET_KNOWLEDGE_FILES, "test.pdf", file_data, 4)
