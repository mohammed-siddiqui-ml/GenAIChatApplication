"""
Core module containing application configuration, logging, database, and base utilities.
"""

from core.config import settings
from core.logging import setup_logging
from core.database import (
    get_db,
    get_engine,
    get_session_factory,
    init_db,
    close_db,
    check_db_health,
)
from core.minio_client import (
    get_minio_client,
    init_minio,
    check_minio_health,
    upload_file,
    download_file,
    delete_file,
    get_file_info,
    list_files,
    BUCKET_KNOWLEDGE_FILES,
    BUCKET_EMBEDDINGS_BACKUP,
    BUCKET_AUDIT_LOGS,
)

__all__ = [
    "settings",
    "setup_logging",
    "get_db",
    "get_engine",
    "get_session_factory",
    "init_db",
    "close_db",
    "check_db_health",
    "get_minio_client",
    "init_minio",
    "check_minio_health",
    "upload_file",
    "download_file",
    "delete_file",
    "get_file_info",
    "list_files",
    "BUCKET_KNOWLEDGE_FILES",
    "BUCKET_EMBEDDINGS_BACKUP",
    "BUCKET_AUDIT_LOGS",
]
