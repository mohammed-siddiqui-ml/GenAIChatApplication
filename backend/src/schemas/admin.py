"""
Admin Request/Response Schemas

This module defines Pydantic schemas for admin API endpoints
including data source CRUD operations and configuration management.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from models.data_source import DataSourceType


class DataSourceCreate(BaseModel):
    """
    Request schema for creating a new data source.

    Validates:
    - Data source name (1-100 characters)
    - Data source type (confluence, jira, onboarding, custom)
    - Configuration dictionary with required fields based on type
    - Optional sync schedule (cron expression)
    - Optional active status (defaults to True)
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name of the data source",
        examples=["Company Wiki"]
    )
    type: DataSourceType = Field(
        ...,
        description="Type of data source (confluence, jira, onboarding, custom)",
        examples=["confluence"]
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Configuration settings (URLs, credentials, filters). Required fields vary by type.",
        examples=[{
            "url": "https://wiki.example.com",
            "username": "admin",
            "api_token": "token123",
            "space_key": "DOCS"
        }]
    )
    sync_schedule: Optional[str] = Field(
        default=None,
        description="Cron expression for sync scheduling (e.g., '0 2 * * *' for 2 AM daily)",
        examples=["0 2 * * *", "*/30 * * * *"]
    )
    is_active: bool = Field(
        default=True,
        description="Whether the data source is active",
        examples=[True]
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Company Wiki",
                    "type": "confluence",
                    "config": {
                        "url": "https://wiki.example.com",
                        "username": "admin",
                        "api_token": "token123",
                        "space_key": "DOCS"
                    },
                    "sync_schedule": "0 2 * * *",
                    "is_active": True
                },
                {
                    "name": "Support Tickets",
                    "type": "jira",
                    "config": {
                        "url": "https://jira.example.com",
                        "username": "admin",
                        "api_token": "token456",
                        "project_key": "SUP"
                    },
                    "sync_schedule": "*/30 * * * *",
                    "is_active": True
                }
            ]
        }
    }


class DataSourceUpdate(BaseModel):
    """
    Request schema for updating an existing data source.

    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated display name",
        examples=["Updated Wiki Name"]
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Updated configuration (replaces existing config)",
        examples=[{
            "url": "https://newwiki.example.com",
            "username": "admin",
            "api_token": "newtoken",
            "space_key": "DOCS"
        }]
    )
    sync_schedule: Optional[str] = Field(
        default=None,
        description="Updated cron expression (pass empty string to clear)",
        examples=["0 3 * * *", ""]
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Updated active status",
        examples=[False]
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate name is not empty or just whitespace if provided."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Name cannot be empty or whitespace')
            return v.strip()
        return v

    @field_validator('sync_schedule')
    @classmethod
    def validate_sync_schedule(cls, v: Optional[str]) -> Optional[str]:
        """Validate sync_schedule is not just whitespace if provided."""
        if v is not None and v != "" and not v.strip():
            raise ValueError('Sync schedule cannot be just whitespace')
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Updated Company Wiki",
                    "is_active": False
                },
                {
                    "sync_schedule": "0 3 * * *"
                }
            ]
        }
    }



class DataSourceResponse(BaseModel):
    """
    Response schema for data source information.

    Returns complete data source information including metadata
    and timestamps. Sensitive fields in config are encrypted.
    """
    id: int = Field(..., description="Data source ID", examples=[1])
    name: str = Field(..., description="Display name", examples=["Company Wiki"])
    type: str = Field(..., description="Data source type", examples=["confluence"])
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration settings (sensitive fields encrypted)",
        examples=[{
            "url": "https://wiki.example.com",
            "username": "admin",
            "api_token": "[ENCRYPTED]",
            "space_key": "DOCS"
        }]
    )
    is_active: bool = Field(..., description="Active status", examples=[True])
    sync_schedule: Optional[str] = Field(
        None,
        description="Cron expression for sync scheduling",
        examples=["0 2 * * *"]
    )
    last_sync_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last successful sync",
        examples=["2024-01-15T02:00:00Z"]
    )
    created_by: Optional[int] = Field(
        None,
        description="User ID who created this data source",
        examples=[1]
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
        examples=["2024-01-01T10:00:00Z"]
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
        examples=["2024-01-15T14:30:00Z"]
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Company Wiki",
                    "type": "confluence",
                    "config": {
                        "url": "https://wiki.example.com",
                        "username": "admin",
                        "api_token": "[ENCRYPTED]",
                        "space_key": "DOCS"
                    },
                    "is_active": True,
                    "sync_schedule": "0 2 * * *",
                    "last_sync_at": "2024-01-15T02:00:00Z",
                    "created_by": 1,
                    "created_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-15T14:30:00Z"
                }
            ]
        }
    }


class DataSourceListResponse(BaseModel):
    """
    Response schema for paginated data source list.

    Returns list of data sources with pagination metadata.
    """
    items: list[DataSourceResponse] = Field(
        ...,
        description="List of data sources",
        examples=[[]]
    )
    total: int = Field(
        ...,
        description="Total number of data sources matching filters",
        examples=[42]
    )
    limit: int = Field(
        ...,
        description="Number of items per page",
        examples=[20]
    )
    offset: int = Field(
        ...,
        description="Number of items skipped",
        examples=[0]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "name": "Company Wiki",
                            "type": "confluence",
                            "config": {
                                "url": "https://wiki.example.com",
                                "space_key": "DOCS"
                            },
                            "is_active": True,
                            "sync_schedule": "0 2 * * *",
                            "last_sync_at": "2024-01-15T02:00:00Z",
                            "created_by": 1,
                            "created_at": "2024-01-01T10:00:00Z",
                            "updated_at": "2024-01-15T14:30:00Z"
                        }
                    ],
                    "total": 42,
                    "limit": 20,
                    "offset": 0
                }
            ]
        }
    }


# ============================================================================
# Ingestion Job Schemas
# ============================================================================


class IngestionTriggerRequest(BaseModel):
    """
    Request schema for triggering manual ingestion.

    Supports both full_sync (re-ingest all) and incremental sync modes.
    """
    data_source_id: int = Field(
        ...,
        description="ID of the data source to ingest",
        examples=[1],
        gt=0
    )
    sync_type: str = Field(
        default="incremental",
        description="Type of sync: 'full_sync' (re-ingest all) or 'incremental' (new/updated only)",
        examples=["full_sync", "incremental"]
    )

    @field_validator('sync_type')
    @classmethod
    def validate_sync_type(cls, v: str) -> str:
        """Validate sync_type is either full_sync or incremental."""
        if v not in ['full_sync', 'incremental']:
            raise ValueError("sync_type must be 'full_sync' or 'incremental'")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "data_source_id": 1,
                    "sync_type": "full_sync"
                },
                {
                    "data_source_id": 2,
                    "sync_type": "incremental"
                }
            ]
        }
    }


class IngestionTriggerResponse(BaseModel):
    """
    Response schema for triggered ingestion job.

    Returns job details and task information.
    """
    job_id: int = Field(..., description="Ingestion job ID", examples=[123])
    data_source_id: int = Field(..., description="Data source ID", examples=[1])
    status: str = Field(..., description="Job status", examples=["pending"])
    task_id: Optional[str] = Field(
        None,
        description="Celery task ID for tracking",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
    )
    sync_type: str = Field(..., description="Sync type", examples=["full_sync"])
    message: str = Field(
        ...,
        description="Success message",
        examples=["Ingestion job created and task dispatched successfully"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job_id": 123,
                    "data_source_id": 1,
                    "status": "pending",
                    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "sync_type": "full_sync",
                    "message": "Ingestion job created and task dispatched successfully"
                }
            ]
        }
    }


class IngestionJobResponse(BaseModel):
    """
    Response schema for ingestion job details.

    Returns complete job information including progress tracking.
    """
    id: int = Field(..., description="Job ID", examples=[123])
    data_source_id: int = Field(..., description="Data source ID", examples=[1])
    data_source_name: Optional[str] = Field(
        None,
        description="Data source name",
        examples=["Company Wiki"]
    )
    data_source_type: Optional[str] = Field(
        None,
        description="Data source type",
        examples=["confluence"]
    )
    status: str = Field(..., description="Job status", examples=["running"])
    started_at: Optional[datetime] = Field(
        None,
        description="Job start timestamp",
        examples=["2024-01-15T10:00:00Z"]
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Job completion timestamp",
        examples=["2024-01-15T10:30:00Z"]
    )
    documents_processed: int = Field(
        ...,
        description="Number of documents successfully processed",
        examples=[42]
    )
    documents_failed: int = Field(
        ...,
        description="Number of documents that failed processing",
        examples=[2]
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if job failed",
        examples=["Connection timeout"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional job metadata",
        examples=[{"sync_type": "full_sync", "task_id": "abc-123"}]
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 123,
                    "data_source_id": 1,
                    "data_source_name": "Company Wiki",
                    "data_source_type": "confluence",
                    "status": "running",
                    "started_at": "2024-01-15T10:00:00Z",
                    "completed_at": None,
                    "documents_processed": 15,
                    "documents_failed": 0,
                    "error_message": None,
                    "metadata": {
                        "sync_type": "full_sync",
                        "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                    }
                }
            ]
        }
    }


class IngestionJobListResponse(BaseModel):
    """
    Response schema for paginated ingestion job list.

    Returns list of jobs with pagination metadata.
    """
    items: list[IngestionJobResponse] = Field(
        ...,
        description="List of ingestion jobs",
        examples=[[]]
    )
    total: int = Field(
        ...,
        description="Total number of jobs matching filters",
        examples=[10]
    )
    limit: int = Field(
        ...,
        description="Number of items per page",
        examples=[20]
    )
    offset: int = Field(
        ...,
        description="Number of items skipped",
        examples=[0]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": 123,
                            "data_source_id": 1,
                            "data_source_name": "Company Wiki",
                            "data_source_type": "confluence",
                            "status": "success",
                            "started_at": "2024-01-15T10:00:00Z",
                            "completed_at": "2024-01-15T10:30:00Z",
                            "documents_processed": 42,
                            "documents_failed": 0,
                            "error_message": None,
                            "metadata": {"sync_type": "full_sync"}
                        }
                    ],
                    "total": 10,
                    "limit": 20,
                    "offset": 0
                }
            ]
        }
    }


class QueryMetrics(BaseModel):
    """Query metrics statistics."""

    total_today: int = Field(
        ...,
        description="Total queries today",
        ge=0,
        examples=[127]
    )
    total_this_week: int = Field(
        ...,
        description="Total queries this week",
        ge=0,
        examples=[543]
    )
    total_this_month: int = Field(
        ...,
        description="Total queries this month",
        ge=0,
        examples=[2341]
    )
    total_all_time: int = Field(
        ...,
        description="Total queries all-time",
        ge=0,
        examples=[15432]
    )


class SessionMetrics(BaseModel):
    """Chat session statistics."""

    total_all_time: int = Field(
        ...,
        description="Total chat sessions all-time",
        ge=0,
        examples=[1234]
    )
    active_sessions: int = Field(
        ...,
        description="Currently active sessions (no end time)",
        ge=0,
        examples=[42]
    )


class IngestionMetrics(BaseModel):
    """Ingestion job statistics."""

    total_jobs: int = Field(
        ...,
        description="Total ingestion jobs",
        ge=0,
        examples=[156]
    )
    successful_jobs: int = Field(
        ...,
        description="Number of successful jobs",
        ge=0,
        examples=[142]
    )
    failed_jobs: int = Field(
        ...,
        description="Number of failed jobs",
        ge=0,
        examples=[8]
    )
    success_rate: float = Field(
        ...,
        description="Success rate percentage (0-100)",
        ge=0,
        le=100,
        examples=[91.03]
    )
    last_successful_run: Optional[datetime] = Field(
        None,
        description="Timestamp of last successful job completion",
        examples=["2024-01-15T14:30:00Z"]
    )
    last_failed_run: Optional[datetime] = Field(
        None,
        description="Timestamp of last failed job completion",
        examples=["2024-01-14T08:15:00Z"]
    )


class DatabaseMetrics(BaseModel):
    """Database statistics."""

    database_size_bytes: int = Field(
        ...,
        description="Total database size in bytes",
        ge=0,
        examples=[524288000]
    )
    database_size_mb: float = Field(
        ...,
        description="Total database size in megabytes",
        ge=0,
        examples=[500.0]
    )
    total_embeddings: int = Field(
        ...,
        description="Total number of embeddings",
        ge=0,
        examples=[5432]
    )


class SystemMetricsResponse(BaseModel):
    """
    System metrics and monitoring response.

    Provides aggregated statistics for system monitoring including:
    - Document count
    - Chat session statistics
    - Query statistics (today, week, month)
    - Average response times
    - Database size and embedding count
    - Ingestion job statistics
    """

    total_documents: int = Field(
        ...,
        description="Total number of knowledge documents",
        ge=0,
        examples=[1234]
    )
    active_documents: int = Field(
        ...,
        description="Number of active (non-deleted) documents",
        ge=0,
        examples=[1200]
    )
    sessions: SessionMetrics = Field(
        ...,
        description="Chat session statistics"
    )
    queries: QueryMetrics = Field(
        ...,
        description="Query statistics"
    )
    average_response_time_ms: Optional[float] = Field(
        None,
        description="Average response time in milliseconds (from chat_messages metadata)",
        ge=0,
        examples=[1250.5]
    )
    database: DatabaseMetrics = Field(
        ...,
        description="Database statistics"
    )
    ingestion: IngestionMetrics = Field(
        ...,
        description="Ingestion job statistics"
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp when metrics were collected",
        examples=["2024-01-15T14:30:00Z"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_documents": 1234,
                    "active_documents": 1200,
                    "sessions": {
                        "total_all_time": 1234,
                        "active_sessions": 42
                    },
                    "queries": {
                        "total_today": 127,
                        "total_this_week": 543,
                        "total_this_month": 2341,
                        "total_all_time": 15432
                    },
                    "average_response_time_ms": 1250.5,
                    "database": {
                        "database_size_bytes": 524288000,
                        "database_size_mb": 500.0,
                        "total_embeddings": 5432
                    },
                    "ingestion": {
                        "total_jobs": 156,
                        "successful_jobs": 142,
                        "failed_jobs": 8,
                        "success_rate": 91.03,
                        "last_successful_run": "2024-01-15T14:30:00Z",
                        "last_failed_run": "2024-01-14T08:15:00Z"
                    },
                    "timestamp": "2024-01-15T14:30:00Z"
                }
            ]
        }
    }
