"""
Ingestion Job Service

This module provides service layer for managing data ingestion jobs,
including triggering manual ingestion and querying job status.
"""

import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.data_source import DataSource, IngestionJob, JobStatus, DataSourceType
from tasks.ingestion import (
    ingest_confluence_docs,
    ingest_jira_issues,
    ingest_onboarding_materials
)

# Logger
logger = logging.getLogger(__name__)


class IngestionJobError(Exception):
    """Custom exception for ingestion job operations."""
    pass


class IngestionJobService:
    """
    Service for managing ingestion jobs.
    
    Provides methods for:
    - Triggering manual ingestion
    - Querying job status
    - Listing jobs with filtering
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize service with database session.
        
        Args:
            db: Async database session
        """
        self.db = db
    
    async def trigger_ingestion(
        self,
        data_source_id: int,
        sync_type: str = "incremental"
    ) -> Tuple[IngestionJob, Optional[str]]:
        """
        Trigger manual ingestion for a data source.
        
        Creates an ingestion job record with status 'pending' and dispatches
        the appropriate Celery task based on data source type.
        
        Args:
            data_source_id: ID of the data source to ingest
            sync_type: Type of sync - 'full_sync' or 'incremental'
            
        Returns:
            Tuple of (IngestionJob, task_id) where task_id is the Celery task ID
            
        Raises:
            IngestionJobError: If data source not found or invalid
        """
        try:
            # Fetch data source
            result = await self.db.execute(
                select(DataSource).where(DataSource.id == data_source_id)
            )
            data_source = result.scalar_one_or_none()
            
            if not data_source:
                raise IngestionJobError(f"Data source {data_source_id} not found")
            
            if not data_source.is_active:
                raise IngestionJobError(
                    f"Data source {data_source_id} is not active"
                )
            
            # Create ingestion job record
            job = IngestionJob(
                data_source_id=data_source_id,
                status=JobStatus.PENDING,
                started_at=None,
                completed_at=None,
                documents_processed=0,
                documents_failed=0,
                error_message=None,
                job_metadata={
                    "sync_type": sync_type,
                    "triggered_manually": True,
                    "triggered_at": datetime.utcnow().isoformat()
                }
            )
            
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)
            
            logger.info(
                f"Created ingestion job {job.id} for data source {data_source_id} "
                f"(type: {data_source.type.value}, sync_type: {sync_type})"
            )
            
            # Dispatch Celery task based on data source type
            task_id = None
            try:
                task_id = self._dispatch_task(data_source.type, data_source_id, job.id)
                
                # Update job metadata with task ID
                job.job_metadata["task_id"] = task_id
                await self.db.commit()
                
                logger.info(
                    f"Dispatched task {task_id} for job {job.id} "
                    f"(data_source: {data_source_id}, type: {data_source.type.value})"
                )
            except Exception as e:
                logger.error(f"Failed to dispatch task for job {job.id}: {e}")
                # Update job status to failed
                job.status = JobStatus.FAILED
                job.error_message = f"Failed to dispatch task: {str(e)}"
                await self.db.commit()
                raise IngestionJobError(f"Failed to dispatch task: {str(e)}")
            
            return job, task_id
            
        except IngestionJobError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to trigger ingestion: {e}", exc_info=True)
            raise IngestionJobError(f"Failed to trigger ingestion: {str(e)}")
    
    def _dispatch_task(
        self,
        source_type: DataSourceType,
        data_source_id: int,
        job_id: int
    ) -> str:
        """
        Dispatch Celery task based on data source type.

        Args:
            source_type: Type of data source
            data_source_id: ID of data source
            job_id: ID of ingestion job (for tracking)

        Returns:
            str: Celery task ID

        Raises:
            ValueError: If data source type is not supported
        """
        if source_type == DataSourceType.CONFLUENCE:
            result = ingest_confluence_docs.delay(data_source_id)
            return result.id
        elif source_type == DataSourceType.JIRA:
            result = ingest_jira_issues.delay(data_source_id)
            return result.id
        elif source_type == DataSourceType.ONBOARDING:
            # Note: Onboarding requires file_path parameter
            # For manual trigger, we'll need to handle this differently
            # For now, raise an error
            raise ValueError(
                "Onboarding data sources require file_path parameter. "
                "Use file upload endpoint instead."
            )
        elif source_type == DataSourceType.CUSTOM:
            raise ValueError("Custom data sources are not yet supported")
        else:
            raise ValueError(f"Unsupported data source type: {source_type.value}")

    async def get_job(
        self,
        job_id: int,
        include_data_source: bool = True
    ) -> Optional[IngestionJob]:
        """
        Get an ingestion job by ID.

        Args:
            job_id: ID of the job to retrieve
            include_data_source: Whether to include data source details

        Returns:
            IngestionJob or None if not found
        """
        try:
            query = select(IngestionJob).where(IngestionJob.id == job_id)
            result = await self.db.execute(query)
            job = result.scalar_one_or_none()

            return job

        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}", exc_info=True)
            raise IngestionJobError(f"Failed to get job: {str(e)}")

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        data_source_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[IngestionJob], int]:
        """
        List ingestion jobs with filtering and pagination.

        Args:
            status: Optional filter by job status
            data_source_id: Optional filter by data source ID
            limit: Number of items per page (max 100)
            offset: Number of items to skip

        Returns:
            Tuple of (list of jobs, total count)
        """
        try:
            # Enforce maximum limit
            limit = min(limit, 100)

            # Build base query
            query = select(IngestionJob)
            count_query = select(func.count(IngestionJob.id))

            # Apply filters
            if status is not None:
                query = query.where(IngestionJob.status == status)
                count_query = count_query.where(IngestionJob.status == status)

            if data_source_id is not None:
                query = query.where(IngestionJob.data_source_id == data_source_id)
                count_query = count_query.where(
                    IngestionJob.data_source_id == data_source_id
                )

            # Order by started_at descending (most recent first)
            query = query.order_by(IngestionJob.started_at.desc())

            # Apply pagination
            query = query.limit(limit).offset(offset)

            # Execute queries
            result = await self.db.execute(query)
            jobs = list(result.scalars().all())

            count_result = await self.db.execute(count_query)
            total = count_result.scalar_one()

            return jobs, total

        except Exception as e:
            logger.error(f"Failed to list jobs: {e}", exc_info=True)
            raise IngestionJobError(f"Failed to list jobs: {str(e)}")
