"""
Metrics Service for System Monitoring

This module provides services for collecting system metrics including:
- Document counts
- Chat session statistics
- Query statistics (today, week, month)
- Average response times
- Database size and embedding counts
- Ingestion job statistics
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge import KnowledgeDocument
from models.chat import ChatSession, ChatMessage, MessageRole
from models.data_source import IngestionJob, JobStatus

# Logger
logger = logging.getLogger(__name__)


class MetricsServiceError(Exception):
    """Base exception for metrics service errors."""
    pass


class MetricsService:
    """
    Service for collecting system metrics and statistics.
    
    Provides aggregated metrics for monitoring system health and usage.
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize metrics service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def get_document_metrics(self) -> Dict[str, int]:
        """
        Get document count metrics.
        
        Returns:
            dict: Document metrics with total_documents and active_documents
        """
        try:
            # Get total documents count
            total_result = await self.db.execute(
                select(func.count(KnowledgeDocument.id))
            )
            total_documents = total_result.scalar() or 0
            
            # Get active (non-deleted) documents count
            active_result = await self.db.execute(
                select(func.count(KnowledgeDocument.id))
                .where(KnowledgeDocument.is_deleted == False)
            )
            active_documents = active_result.scalar() or 0
            
            return {
                "total_documents": total_documents,
                "active_documents": active_documents
            }
        except Exception as e:
            logger.error(f"Failed to get document metrics: {str(e)}")
            raise MetricsServiceError(f"Failed to get document metrics: {str(e)}")
    
    async def get_session_metrics(self) -> Dict[str, int]:
        """
        Get chat session metrics.
        
        Returns:
            dict: Session metrics with total_all_time and active_sessions
        """
        try:
            # Get total sessions count
            total_result = await self.db.execute(
                select(func.count(ChatSession.id))
            )
            total_all_time = total_result.scalar() or 0
            
            # Get active sessions count (sessions with no ended_at)
            active_result = await self.db.execute(
                select(func.count(ChatSession.id))
                .where(ChatSession.ended_at.is_(None))
            )
            active_sessions = active_result.scalar() or 0
            
            return {
                "total_all_time": total_all_time,
                "active_sessions": active_sessions
            }
        except Exception as e:
            logger.error(f"Failed to get session metrics: {str(e)}")
            raise MetricsServiceError(f"Failed to get session metrics: {str(e)}")
    
    async def get_query_metrics(self) -> Dict[str, int]:
        """
        Get query count metrics for different time periods.
        
        Counts user messages only (role='user') from chat_messages table.
        
        Returns:
            dict: Query metrics with counts for today, week, month, and all-time
        """
        try:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=today_start.weekday())
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get total all-time queries
            total_result = await self.db.execute(
                select(func.count(ChatMessage.id))
                .where(ChatMessage.role == MessageRole.USER)
            )
            total_all_time = total_result.scalar() or 0
            
            # Get today's queries
            today_result = await self.db.execute(
                select(func.count(ChatMessage.id))
                .where(ChatMessage.role == MessageRole.USER)
                .where(ChatMessage.created_at >= today_start)
            )
            total_today = today_result.scalar() or 0
            
            # Get this week's queries
            week_result = await self.db.execute(
                select(func.count(ChatMessage.id))
                .where(ChatMessage.role == MessageRole.USER)
                .where(ChatMessage.created_at >= week_start)
            )
            total_this_week = week_result.scalar() or 0

            # Get this month's queries
            month_result = await self.db.execute(
                select(func.count(ChatMessage.id))
                .where(ChatMessage.role == MessageRole.USER)
                .where(ChatMessage.created_at >= month_start)
            )
            total_this_month = month_result.scalar() or 0

            return {
                "total_today": total_today,
                "total_this_week": total_this_week,
                "total_this_month": total_this_month,
                "total_all_time": total_all_time
            }
        except Exception as e:
            logger.error(f"Failed to get query metrics: {str(e)}")
            raise MetricsServiceError(f"Failed to get query metrics: {str(e)}")

    async def get_average_response_time(self) -> Optional[float]:
        """
        Calculate average response time from assistant messages metadata.

        Extracts 'duration_ms' from chat_messages.metadata where role='assistant'
        and calculates the average.

        Returns:
            float: Average response time in milliseconds, or None if no data
        """
        try:
            # Query assistant messages that have duration_ms in metadata
            result = await self.db.execute(
                select(ChatMessage.message_metadata)
                .where(ChatMessage.role == MessageRole.ASSISTANT)
                .where(ChatMessage.message_metadata.isnot(None))
            )

            messages = result.scalars().all()

            # Extract duration_ms values
            durations = []
            for metadata in messages:
                if metadata and isinstance(metadata, dict):
                    duration = metadata.get('duration_ms')
                    if duration is not None and isinstance(duration, (int, float)) and duration > 0:
                        durations.append(float(duration))

            # Calculate average
            if durations:
                return sum(durations) / len(durations)
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to get average response time: {str(e)}")
            raise MetricsServiceError(f"Failed to get average response time: {str(e)}")

    async def get_database_metrics(self) -> Dict[str, Any]:
        """
        Get database size and embedding count metrics.

        Returns:
            dict: Database metrics with size and embedding count
        """
        try:
            # Get database size - use database-agnostic approach
            # Check database dialect to use appropriate query
            database_size_bytes = 0
            database_size_mb = 0.0

            # Get database dialect name
            dialect_name = self.db.bind.dialect.name if self.db.bind else "unknown"

            if dialect_name == "postgresql":
                # PostgreSQL-specific query
                size_result = await self.db.execute(
                    text("SELECT pg_database_size(current_database())")
                )
                database_size_bytes = size_result.scalar() or 0
                database_size_mb = round(database_size_bytes / (1024 * 1024), 2)
            elif dialect_name == "sqlite":
                # SQLite: Return 0 for test environments (in-memory databases have no size)
                # In production with file-based SQLite, would use os.path.getsize()
                database_size_bytes = 0
                database_size_mb = 0.0
            else:
                # For other databases, return 0
                logger.warning(f"Database size calculation not supported for dialect: {dialect_name}")
                database_size_bytes = 0
                database_size_mb = 0.0

            # Get total embeddings count from document_embeddings table
            # Import here to avoid circular imports
            from models.knowledge import DocumentEmbedding

            embeddings_result = await self.db.execute(
                select(func.count(DocumentEmbedding.id))
            )
            total_embeddings = embeddings_result.scalar() or 0

            return {
                "database_size_bytes": database_size_bytes,
                "database_size_mb": database_size_mb,
                "total_embeddings": total_embeddings
            }
        except Exception as e:
            logger.error(f"Failed to get database metrics: {str(e)}")
            raise MetricsServiceError(f"Failed to get database metrics: {str(e)}")

    async def get_ingestion_metrics(self) -> Dict[str, Any]:
        """
        Get ingestion job statistics.

        Returns:
            dict: Ingestion metrics including success rate and last run times
        """
        try:
            # Get total jobs count
            total_result = await self.db.execute(
                select(func.count(IngestionJob.id))
            )
            total_jobs = total_result.scalar() or 0

            # Get successful jobs count
            success_result = await self.db.execute(
                select(func.count(IngestionJob.id))
                .where(IngestionJob.status == JobStatus.SUCCESS)
            )
            successful_jobs = success_result.scalar() or 0

            # Get failed jobs count
            failed_result = await self.db.execute(
                select(func.count(IngestionJob.id))
                .where(IngestionJob.status == JobStatus.FAILED)
            )
            failed_jobs = failed_result.scalar() or 0

            # Calculate success rate
            success_rate = 0.0
            if total_jobs > 0:
                success_rate = round((successful_jobs / total_jobs) * 100, 2)

            # Get last successful run
            last_success_result = await self.db.execute(
                select(IngestionJob.completed_at)
                .where(IngestionJob.status == JobStatus.SUCCESS)
                .where(IngestionJob.completed_at.isnot(None))
                .order_by(IngestionJob.completed_at.desc())
                .limit(1)
            )
            last_successful_run = last_success_result.scalar_one_or_none()

            # Get last failed run
            last_failed_result = await self.db.execute(
                select(IngestionJob.completed_at)
                .where(IngestionJob.status == JobStatus.FAILED)
                .where(IngestionJob.completed_at.isnot(None))
                .order_by(IngestionJob.completed_at.desc())
                .limit(1)
            )
            last_failed_run = last_failed_result.scalar_one_or_none()

            return {
                "total_jobs": total_jobs,
                "successful_jobs": successful_jobs,
                "failed_jobs": failed_jobs,
                "success_rate": success_rate,
                "last_successful_run": last_successful_run,
                "last_failed_run": last_failed_run
            }
        except Exception as e:
            logger.error(f"Failed to get ingestion metrics: {str(e)}")
            raise MetricsServiceError(f"Failed to get ingestion metrics: {str(e)}")

    async def get_all_metrics(self) -> Dict[str, Any]:
        """
        Collect all system metrics in a single call.

        Returns:
            dict: Complete system metrics
        """
        try:
            # Collect all metrics
            document_metrics = await self.get_document_metrics()
            session_metrics = await self.get_session_metrics()
            query_metrics = await self.get_query_metrics()
            avg_response_time = await self.get_average_response_time()
            database_metrics = await self.get_database_metrics()
            ingestion_metrics = await self.get_ingestion_metrics()

            return {
                "total_documents": document_metrics["total_documents"],
                "active_documents": document_metrics["active_documents"],
                "sessions": session_metrics,
                "queries": query_metrics,
                "average_response_time_ms": avg_response_time,
                "database": database_metrics,
                "ingestion": ingestion_metrics,
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Failed to get all metrics: {str(e)}")
            raise MetricsServiceError(f"Failed to get all metrics: {str(e)}")
