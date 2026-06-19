"""
Admin API Endpoints

This module provides REST API endpoints for administrative operations
including data source management (CRUD operations).
"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from middleware.auth import require_admin
from models.user import User
from models.data_source import DataSourceType, JobStatus
from schemas.admin import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    DataSourceListResponse,
    IngestionTriggerRequest,
    IngestionTriggerResponse,
    IngestionJobResponse,
    IngestionJobListResponse,
    SystemMetricsResponse
)
from services.admin_service import DataSourceService, DataSourceError
from services.ingestion_service import IngestionJobService, IngestionJobError
from services.metrics_service import MetricsService, MetricsServiceError

# Logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get(
    "/data-sources",
    response_model=DataSourceListResponse,
    summary="List all data sources",
    description="""
    List all data sources with optional filtering and pagination.

    Supports filtering by:
    - Data source type (confluence, jira, onboarding, custom)
    - Active status (true/false)

    Returns paginated results with total count.

    **Requires**: Admin role
    """,
    responses={
        200: {
            "description": "List of data sources retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": 1,
                                "name": "Company Wiki",
                                "type": "confluence",
                                "config": {"url": "https://wiki.example.com", "space_key": "DOCS"},
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
                }
            }
        },
        403: {"description": "Admin access required"},
        500: {"description": "Internal server error"}
    }
)
async def list_data_sources(
    source_type: Optional[DataSourceType] = Query(
        None,
        description="Filter by data source type"
    ),
    is_active: Optional[bool] = Query(
        None,
        description="Filter by active status"
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of items per page (max 100)"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of items to skip"
    ),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    List data sources with filtering and pagination.

    Args:
        source_type: Optional filter by data source type
        is_active: Optional filter by active status
        limit: Number of items per page (1-100)
        offset: Number of items to skip
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Dictionary with items, total, limit, offset

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 500: If listing fails
    """
    logger.info(
        f"Admin {admin.email} listing data sources "
        f"(type={source_type}, is_active={is_active}, limit={limit}, offset={offset})"
    )

    try:
        service = DataSourceService(db)
        sources, total = await service.list_data_sources(
            source_type=source_type,
            is_active=is_active,
            limit=limit,
            offset=offset,
            decrypt_config=False  # Keep sensitive fields encrypted in response
        )

        logger.info(f"Retrieved {len(sources)} data sources (total: {total})")

        return {
            "items": sources,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except DataSourceError as e:
        logger.error(f"Failed to list data sources: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list data sources: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing data sources: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.post(
    "/data-sources",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new data source",
    description="""
    Create a new data source with validated configuration.

    Configuration validation is performed based on data source type:
    - **Confluence**: Requires url, username, api_token, space_key
    - **JIRA**: Requires url, username, api_token, project_key
    - **Onboarding**: Requires storage_path
    - **Custom**: Requires url

    Sensitive fields (api_token, password, credentials) are automatically encrypted.

    **Requires**: Admin role
    """,
    responses={
        201: {
            "description": "Data source created successfully",
            "content": {
                "application/json": {
                    "example": {
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
                        "last_sync_at": None,
                        "created_by": 1,
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    }
                }
            }
        },
        400: {"description": "Invalid configuration or validation error"},
        403: {"description": "Admin access required"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"}
    }
)
async def create_data_source(
    request: DataSourceCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> DataSourceResponse:
    """
    Create a new data source.

    Args:
        request: Data source creation request with name, type, config, etc.
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Created data source object

    Raises:
        HTTPException 400: If configuration is invalid
        HTTPException 403: If user is not admin
        HTTPException 422: If request validation fails
        HTTPException 500: If creation fails
    """
    logger.info(f"Admin {admin.email} creating data source: {request.name} (type: {request.type})")

    try:
        service = DataSourceService(db)

        # Create data source with admin as creator
        data_source = await service.create_data_source(
            name=request.name,
            source_type=request.type,
            config=request.config,
            sync_schedule=request.sync_schedule,
            is_active=request.is_active,
            created_by=admin.id
        )

        logger.info(f"Created data source: {data_source.name} (ID: {data_source.id})")

        return data_source

    except DataSourceError as e:
        logger.error(f"Failed to create data source: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating data source: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/data-sources/{data_source_id}",
    response_model=DataSourceResponse,
    summary="Get a data source by ID",
    description="""
    Retrieve a single data source by its ID.

    Returns complete data source information including configuration.
    Sensitive fields in configuration are encrypted.

    **Requires**: Admin role
    """,
    responses={
        200: {
            "description": "Data source retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "Company Wiki",
                        "type": "confluence",
                        "config": {"url": "https://wiki.example.com", "space_key": "DOCS"},
                        "is_active": True,
                        "sync_schedule": "0 2 * * *",
                        "last_sync_at": "2024-01-15T02:00:00Z",
                        "created_by": 1,
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-15T14:30:00Z"
                    }
                }
            }
        },
        403: {"description": "Admin access required"},
        404: {"description": "Data source not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_data_source(
    data_source_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> DataSourceResponse:
    """
    Get a data source by ID.

    Args:
        data_source_id: ID of the data source to retrieve
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Data source object

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If data source not found
        HTTPException 500: If retrieval fails
    """
    logger.info(f"Admin {admin.email} retrieving data source ID: {data_source_id}")

    try:
        service = DataSourceService(db)
        data_source = await service.get_data_source(
            data_source_id=data_source_id,
            decrypt_config=False  # Keep sensitive fields encrypted
        )

        if not data_source:
            logger.warning(f"Data source not found: {data_source_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source not found: {data_source_id}"
            )

        logger.info(f"Retrieved data source: {data_source.name} (ID: {data_source_id})")

        return data_source

    except HTTPException:
        raise
    except DataSourceError as e:
        logger.error(f"Failed to get data source: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get data source: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting data source: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )



@router.put(
    "/data-sources/{data_source_id}",
    response_model=DataSourceResponse,
    summary="Update a data source",
    description="""
    Update an existing data source.

    All fields are optional - only provided fields will be updated.
    Configuration validation is performed if new config is provided.

    To clear sync_schedule, pass an empty string.

    **Requires**: Admin role
    """,
    responses={
        200: {
            "description": "Data source updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "Updated Company Wiki",
                        "type": "confluence",
                        "config": {
                            "url": "https://wiki.example.com",
                            "username": "admin",
                            "api_token": "[ENCRYPTED]",
                            "space_key": "DOCS"
                        },
                        "is_active": False,
                        "sync_schedule": "0 3 * * *",
                        "last_sync_at": "2024-01-15T02:00:00Z",
                        "created_by": 1,
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-16T11:30:00Z"
                    }
                }
            }
        },
        400: {"description": "Invalid configuration or validation error"},
        403: {"description": "Admin access required"},
        404: {"description": "Data source not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"}
    }
)
async def update_data_source(
    data_source_id: int,
    request: DataSourceUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> DataSourceResponse:
    """
    Update an existing data source.

    Args:
        data_source_id: ID of the data source to update
        request: Data source update request (all fields optional)
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Updated data source object

    Raises:
        HTTPException 400: If configuration is invalid
        HTTPException 403: If user is not admin
        HTTPException 404: If data source not found
        HTTPException 422: If request validation fails
        HTTPException 500: If update fails
    """
    logger.info(f"Admin {admin.email} updating data source ID: {data_source_id}")

    try:
        service = DataSourceService(db)

        # Update data source
        data_source = await service.update_data_source(
            data_source_id=data_source_id,
            name=request.name,
            config=request.config,
            sync_schedule=request.sync_schedule,
            is_active=request.is_active
        )

        logger.info(f"Updated data source: {data_source.name} (ID: {data_source_id})")

        return data_source

    except DataSourceError as e:
        error_msg = str(e)
        logger.error(f"Failed to update data source: {error_msg}")

        # Return 404 if data source not found
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

        # Return 400 for validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        logger.error(f"Unexpected error updating data source: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.delete(
    "/data-sources/{data_source_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a data source",
    description="""
    Delete a data source and all associated data.

    This operation will:
    - Delete the data source
    - Cascade delete all associated knowledge documents
    - Cascade delete all associated document embeddings

    **Warning**: This operation cannot be undone.

    **Requires**: Admin role
    """,
    responses={
        200: {
            "description": "Data source deleted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Data source deleted successfully",
                        "data_source_id": 1
                    }
                }
            }
        },
        403: {"description": "Admin access required"},
        404: {"description": "Data source not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_data_source(
    data_source_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete a data source and cascade delete all related documents.

    Args:
        data_source_id: ID of the data source to delete
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Success message with deleted data source ID

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If data source not found
        HTTPException 500: If deletion fails
    """
    logger.info(f"Admin {admin.email} deleting data source ID: {data_source_id}")

    try:
        service = DataSourceService(db)

        # Delete data source
        success = await service.delete_data_source(data_source_id)

        if success:
            logger.info(f"Successfully deleted data source ID: {data_source_id}")
            return {
                "message": "Data source deleted successfully",
                "data_source_id": data_source_id
            }

    except DataSourceError as e:
        error_msg = str(e)
        logger.error(f"Failed to delete data source: {error_msg}")

        # Return 404 if data source not found
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting data source: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


# ============================================================================
# Ingestion Job Management Endpoints
# ============================================================================


@router.post(
    "/ingestion/trigger",
    response_model=IngestionTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger manual data ingestion",
    description="""
    Trigger manual ingestion for a specific data source.

    Supports two sync types:
    - **full_sync**: Re-ingest all data (deletes existing and re-processes)
    - **incremental**: Only ingest new or updated data since last sync

    Creates an ingestion job record with status 'pending' and dispatches
    a Celery task based on data source type:
    - Confluence → ingest_confluence_docs task
    - JIRA → ingest_jira_issues task
    - Onboarding → Requires file upload endpoint (not supported here)

    **Requires**: Admin role
    """,
    responses={
        201: {
            "description": "Ingestion job created and task dispatched",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": 123,
                        "data_source_id": 1,
                        "status": "pending",
                        "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "sync_type": "full_sync",
                        "message": "Ingestion job created and task dispatched successfully"
                    }
                }
            }
        },
        400: {"description": "Invalid request or data source not active"},
        403: {"description": "Admin access required"},
        404: {"description": "Data source not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"}
    }
)
async def trigger_ingestion(
    request: IngestionTriggerRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> IngestionTriggerResponse:
    """
    Trigger manual ingestion for a data source.

    Args:
        request: Ingestion trigger request with data_source_id and sync_type
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Ingestion trigger response with job details

    Raises:
        HTTPException 400: If data source is invalid or not active
        HTTPException 403: If user is not admin
        HTTPException 404: If data source not found
        HTTPException 422: If request validation fails
        HTTPException 500: If triggering fails
    """
    logger.info(
        f"Admin {admin.email} triggering ingestion for data source "
        f"{request.data_source_id} (sync_type: {request.sync_type})"
    )

    try:
        service = IngestionJobService(db)

        # Trigger ingestion
        job, task_id = await service.trigger_ingestion(
            data_source_id=request.data_source_id,
            sync_type=request.sync_type
        )

        logger.info(
            f"Successfully triggered ingestion job {job.id} for data source "
            f"{request.data_source_id} (task_id: {task_id})"
        )

        return IngestionTriggerResponse(
            job_id=job.id,
            data_source_id=job.data_source_id,
            status=job.status.value,
            task_id=task_id,
            sync_type=request.sync_type,
            message="Ingestion job created and task dispatched successfully"
        )

    except IngestionJobError as e:
        error_msg = str(e)
        logger.error(f"Failed to trigger ingestion: {error_msg}")

        # Return 404 if data source not found
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

        # Return 400 for validation or activation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        logger.error(f"Unexpected error triggering ingestion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/ingestion/jobs",
    response_model=IngestionJobListResponse,
    summary="List ingestion jobs",
    description="""
    List ingestion jobs with optional filtering and pagination.

    Supports filtering by:
    - Job status (pending, running, success, failed)
    - Data source ID

    Returns paginated results with total count, ordered by started_at descending
    (most recent first).

    **Requires**: Admin role
    """,
    responses={
        200: {
            "description": "List of ingestion jobs retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
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
                }
            }
        },
        403: {"description": "Admin access required"},
        500: {"description": "Internal server error"}
    }
)
async def list_ingestion_jobs(
    job_status: Optional[JobStatus] = Query(
        None,
        description="Filter by job status"
    ),
    data_source_id: Optional[int] = Query(
        None,
        description="Filter by data source ID",
        gt=0
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of items per page (max 100)"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of items to skip"
    ),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    List ingestion jobs with filtering and pagination.

    Args:
        job_status: Optional filter by job status
        data_source_id: Optional filter by data source ID
        limit: Number of items per page (1-100)
        offset: Number of items to skip
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Dictionary with items, total, limit, offset

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 500: If listing fails
    """
    logger.info(
        f"Admin {admin.email} listing ingestion jobs "
        f"(status={job_status}, data_source_id={data_source_id}, "
        f"limit={limit}, offset={offset})"
    )

    try:
        service = IngestionJobService(db)
        jobs, total = await service.list_jobs(
            status=job_status,
            data_source_id=data_source_id,
            limit=limit,
            offset=offset
        )

        # Build response with data source details
        items = []
        for job in jobs:
            item = {
                "id": job.id,
                "data_source_id": job.data_source_id,
                "data_source_name": job.data_source.name if job.data_source else None,
                "data_source_type": job.data_source.type.value if job.data_source else None,
                "status": job.status.value,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "documents_processed": job.documents_processed,
                "documents_failed": job.documents_failed,
                "error_message": job.error_message,
                "metadata": job.job_metadata
            }
            items.append(item)

        logger.info(f"Retrieved {len(jobs)} ingestion jobs (total: {total})")

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except IngestionJobError as e:
        logger.error(f"Failed to list ingestion jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list ingestion jobs: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing ingestion jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/ingestion/jobs/{job_id}",
    response_model=IngestionJobResponse,
    summary="Get ingestion job details",
    description="""
    Retrieve detailed information about a specific ingestion job.

    Returns complete job information including:
    - Current status (pending, running, success, failed)
    - Progress tracking (documents processed/failed)
    - Start and completion timestamps
    - Error messages if failed
    - Job metadata (sync_type, task_id, etc.)

    **Requires**: Admin role
    """,
    responses={
        200: {
            "description": "Ingestion job retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
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
                }
            }
        },
        403: {"description": "Admin access required"},
        404: {"description": "Ingestion job not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_ingestion_job(
    job_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed information about an ingestion job.

    Args:
        job_id: ID of the job to retrieve
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        Ingestion job details

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If job not found
        HTTPException 500: If retrieval fails
    """
    logger.info(f"Admin {admin.email} retrieving ingestion job ID: {job_id}")

    try:
        service = IngestionJobService(db)
        job = await service.get_job(job_id, include_data_source=True)

        if not job:
            logger.warning(f"Ingestion job not found: {job_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingestion job not found: {job_id}"
            )

        logger.info(f"Retrieved ingestion job: {job_id} (status: {job.status.value})")

        return {
            "id": job.id,
            "data_source_id": job.data_source_id,
            "data_source_name": job.data_source.name if job.data_source else None,
            "data_source_type": job.data_source.type.value if job.data_source else None,
            "status": job.status.value,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "documents_processed": job.documents_processed,
            "documents_failed": job.documents_failed,
            "error_message": job.error_message,
            "metadata": job.job_metadata
        }

    except HTTPException:
        raise
    except IngestionJobError as e:
        logger.error(f"Failed to get ingestion job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ingestion job: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting ingestion job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/metrics",
    response_model=SystemMetricsResponse,
    summary="Get system metrics and monitoring statistics",
    description="""
    Retrieve aggregated system metrics for monitoring and analytics.

    Returns comprehensive statistics including:
    - **Documents**: Total and active document counts
    - **Chat Sessions**: All-time total and currently active sessions
    - **Queries**: Counts for today, this week, this month, and all-time
    - **Response Times**: Average response time from assistant messages
    - **Database**: Database size (bytes and MB) and total embeddings count
    - **Ingestion Jobs**: Success rate, counts, and last run timestamps

    **Requires**: Admin role

    **Performance Note**: This endpoint aggregates data from multiple tables.
    Response time may vary based on database size.
    """,
    responses={
        200: {
            "description": "System metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
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
                }
            }
        },
        403: {"description": "Admin access required"},
        500: {"description": "Internal server error"}
    }
)
async def get_system_metrics(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get system metrics and monitoring statistics.

    Args:
        admin: Authenticated admin user (from dependency)
        db: Database session

    Returns:
        dict: System metrics including documents, sessions, queries, database, and ingestion stats

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 500: If metrics collection fails
    """
    logger.info(f"Admin {admin.email} retrieving system metrics")

    try:
        service = MetricsService(db)
        metrics = await service.get_all_metrics()

        logger.info(
            f"System metrics retrieved: {metrics['total_documents']} docs, "
            f"{metrics['sessions']['active_sessions']} active sessions, "
            f"{metrics['queries']['total_today']} queries today"
        )

        return metrics

    except MetricsServiceError as e:
        logger.error(f"Failed to get system metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system metrics: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting system metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
