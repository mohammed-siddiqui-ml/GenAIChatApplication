"""
MinIO Client for S3-Compatible Object Storage

This module provides MinIO client configuration for object storage operations.
Supports bucket management, file upload/download, and health checks.
"""

import io
import logging
import mimetypes
from typing import Optional, BinaryIO

from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import MaxRetryError

from core.config import settings

# Logger
logger = logging.getLogger(__name__)

# Global MinIO client
_minio_client: Optional[Minio] = None

# Bucket names
BUCKET_KNOWLEDGE_FILES = settings.MINIO_BUCKET_KNOWLEDGE_FILES
BUCKET_EMBEDDINGS_BACKUP = settings.MINIO_BUCKET_EMBEDDINGS_BACKUP
BUCKET_AUDIT_LOGS = settings.MINIO_BUCKET_AUDIT_LOGS

# List of all buckets to create on startup
REQUIRED_BUCKETS = [
    BUCKET_KNOWLEDGE_FILES,
    BUCKET_EMBEDDINGS_BACKUP,
    BUCKET_AUDIT_LOGS,
]


def get_minio_client() -> Minio:
    """
    Get or create the MinIO client.
    
    The MinIO client is configured with:
    - endpoint: MinIO server address (host:port)
    - access_key: MinIO access key for authentication
    - secret_key: MinIO secret key for authentication
    - secure: Whether to use HTTPS (True) or HTTP (False)
    
    Returns:
        Minio: Configured MinIO client instance
    """
    global _minio_client
    
    if _minio_client is None:
        logger.info("Creating MinIO client...")
        logger.info(f"MinIO endpoint: {settings.MINIO_ENDPOINT}")
        logger.info(f"MinIO SSL enabled: {settings.MINIO_USE_SSL}")
        
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
        
        logger.info("MinIO client created successfully")
    
    return _minio_client


def init_minio() -> None:
    """
    Initialize MinIO on application startup.
    
    This function should be called during application startup to:
    - Verify MinIO connectivity
    - Create required buckets if they don't exist
    - Log bucket status
    
    Raises:
        Exception: If MinIO initialization fails
    """
    try:
        client = get_minio_client()
        
        # Test MinIO connectivity by listing buckets
        logger.info("Testing MinIO connectivity...")
        buckets = client.list_buckets()
        logger.info(f"MinIO connectivity verified. Existing buckets: {len(buckets)}")
        
        # Create required buckets if they don't exist
        for bucket_name in REQUIRED_BUCKETS:
            if not client.bucket_exists(bucket_name):
                logger.info(f"Creating bucket: {bucket_name}")
                client.make_bucket(bucket_name)
                logger.info(f"Bucket created: {bucket_name}")
            else:
                logger.info(f"Bucket already exists: {bucket_name}")
        
        logger.info("MinIO initialized successfully")
        logger.info(f"Required buckets configured: {', '.join(REQUIRED_BUCKETS)}")
        
    except MaxRetryError as e:
        logger.error(f"Failed to connect to MinIO: {str(e)}")
        logger.error("Ensure MinIO service is running and endpoint is correct")
        raise
    except S3Error as e:
        logger.error(f"MinIO S3 error during initialization: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize MinIO: {str(e)}")
        raise


def check_minio_health() -> bool:
    """
    Check MinIO health for readiness probes.
    
    This function verifies that:
    - MinIO is reachable
    - Authentication is working
    - Required buckets exist
    
    Used by the /ready endpoint for Kubernetes/Docker health checks.
    
    Returns:
        bool: True if MinIO is healthy, False otherwise
    """
    try:
        client = get_minio_client()
        
        # Test connectivity by listing buckets
        buckets = client.list_buckets()
        
        # Verify all required buckets exist
        existing_buckets = {bucket.name for bucket in buckets}
        all_buckets_exist = all(
            bucket in existing_buckets for bucket in REQUIRED_BUCKETS
        )
        
        if not all_buckets_exist:
            missing = set(REQUIRED_BUCKETS) - existing_buckets
            logger.warning(f"MinIO health check: missing buckets: {missing}")
            return False
        
        logger.debug("MinIO health check passed")
        return True
        
    except Exception as e:
        logger.error(f"MinIO health check failed: {str(e)}")
        return False


# ============================================================================
# File Upload/Download/Delete Functions
# ============================================================================

def detect_content_type(file_name: str, default: str = "application/octet-stream") -> str:
    """
    Detect content type from file name using mimetypes module.

    Args:
        file_name: Name of the file (with extension)
        default: Default content type if detection fails

    Returns:
        str: MIME type (e.g., 'image/png', 'application/pdf')
    """
    content_type, _ = mimetypes.guess_type(file_name)
    if content_type is None:
        logger.debug(f"Could not detect content type for '{file_name}', using default: {default}")
        return default

    logger.debug(f"Detected content type for '{file_name}': {content_type}")
    return content_type


def upload_file(
    bucket_name: str,
    object_name: str,
    file_data: BinaryIO,
    file_size: int,
    content_type: Optional[str] = None,
) -> bool:
    """
    Upload a file to MinIO bucket.

    Args:
        bucket_name: Name of the bucket to upload to
        object_name: Object name (path) in the bucket
        file_data: Binary file data (file-like object)
        file_size: Size of the file in bytes
        content_type: Optional MIME type (auto-detected if not provided)

    Returns:
        bool: True if upload successful, False otherwise

    Raises:
        S3Error: If MinIO operation fails
    """
    try:
        client = get_minio_client()

        # Auto-detect content type if not provided
        if content_type is None:
            content_type = detect_content_type(object_name)

        # Upload file
        logger.info(f"Uploading file to bucket '{bucket_name}': {object_name} ({file_size} bytes)")

        client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=file_data,
            length=file_size,
            content_type=content_type,
        )

        logger.info(f"File uploaded successfully: {bucket_name}/{object_name}")
        return True

    except S3Error as e:
        logger.error(f"Failed to upload file '{object_name}' to bucket '{bucket_name}': {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading file '{object_name}': {str(e)}")
        raise


def download_file(bucket_name: str, object_name: str) -> Optional[BinaryIO]:
    """
    Download a file from MinIO bucket with streaming support.

    This function returns a streaming response object that can be read incrementally,
    which is memory-efficient for large files.

    Args:
        bucket_name: Name of the bucket to download from
        object_name: Object name (path) in the bucket

    Returns:
        Optional[BinaryIO]: File stream object, or None if file doesn't exist

    Raises:
        S3Error: If MinIO operation fails
    """
    try:
        client = get_minio_client()

        logger.info(f"Downloading file from bucket '{bucket_name}': {object_name}")

        # Get object (returns a streaming HTTPResponse object)
        response = client.get_object(bucket_name, object_name)

        logger.info(f"File download initiated: {bucket_name}/{object_name}")
        return response

    except S3Error as e:
        if e.code == "NoSuchKey":
            logger.warning(f"File not found: {bucket_name}/{object_name}")
            return None
        else:
            logger.error(f"Failed to download file '{object_name}' from bucket '{bucket_name}': {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error downloading file '{object_name}': {str(e)}")
        raise


def delete_file(bucket_name: str, object_name: str) -> bool:
    """
    Delete a file from MinIO bucket.

    Args:
        bucket_name: Name of the bucket to delete from
        object_name: Object name (path) in the bucket

    Returns:
        bool: True if deletion successful, False otherwise

    Raises:
        S3Error: If MinIO operation fails
    """
    try:
        client = get_minio_client()

        logger.info(f"Deleting file from bucket '{bucket_name}': {object_name}")

        # Delete object
        client.remove_object(bucket_name, object_name)

        logger.info(f"File deleted successfully: {bucket_name}/{object_name}")
        return True

    except S3Error as e:
        if e.code == "NoSuchKey":
            logger.warning(f"File not found (already deleted?): {bucket_name}/{object_name}")
            return True  # Consider it success if file doesn't exist
        else:
            logger.error(f"Failed to delete file '{object_name}' from bucket '{bucket_name}': {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error deleting file '{object_name}': {str(e)}")
        raise


def get_file_info(bucket_name: str, object_name: str) -> Optional[dict]:
    """
    Get file metadata from MinIO bucket.

    Args:
        bucket_name: Name of the bucket
        object_name: Object name (path) in the bucket

    Returns:
        Optional[dict]: File metadata (size, etag, content_type, last_modified), or None if not found

    Raises:
        S3Error: If MinIO operation fails
    """
    try:
        client = get_minio_client()

        # Get object metadata
        stat = client.stat_object(bucket_name, object_name)

        metadata = {
            "bucket": bucket_name,
            "object_name": object_name,
            "size": stat.size,
            "etag": stat.etag,
            "content_type": stat.content_type,
            "last_modified": stat.last_modified,
            "metadata": stat.metadata,
        }

        logger.debug(f"Retrieved file info: {bucket_name}/{object_name} ({stat.size} bytes)")
        return metadata

    except S3Error as e:
        if e.code == "NoSuchKey":
            logger.debug(f"File not found: {bucket_name}/{object_name}")
            return None
        else:
            logger.error(f"Failed to get file info for '{object_name}': {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error getting file info for '{object_name}': {str(e)}")
        raise


def list_files(bucket_name: str, prefix: str = "") -> list:
    """
    List files in a MinIO bucket with optional prefix filter.

    Args:
        bucket_name: Name of the bucket
        prefix: Optional prefix to filter objects (e.g., 'folder/')

    Returns:
        list: List of object names matching the prefix

    Raises:
        S3Error: If MinIO operation fails
    """
    try:
        client = get_minio_client()

        logger.debug(f"Listing files in bucket '{bucket_name}' with prefix '{prefix}'")

        objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)

        file_list = [obj.object_name for obj in objects]

        logger.debug(f"Found {len(file_list)} files in {bucket_name}/{prefix}")
        return file_list

    except S3Error as e:
        logger.error(f"Failed to list files in bucket '{bucket_name}': {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing files in bucket '{bucket_name}': {str(e)}")
        raise

