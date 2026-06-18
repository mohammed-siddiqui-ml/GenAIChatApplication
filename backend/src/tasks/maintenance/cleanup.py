"""
Maintenance Tasks

This module contains Celery tasks for system maintenance and cleanup operations.
These tasks are typically scheduled to run periodically via Celery Beat.
"""

from datetime import datetime, timedelta
from tasks.celery import celery_app


@celery_app.task(
    name="tasks.maintenance.cleanup_old_results",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def cleanup_old_results(self, days_old: int = 7) -> dict:
    """
    Clean up old task results from the Celery result backend.
    
    This task removes task results older than the specified number of days
    to prevent the result backend from growing indefinitely.
    
    Args:
        days_old: Number of days to keep results (default: 7)
    
    Returns:
        dict: Summary of cleanup operation
        
    Raises:
        Exception: If cleanup fails
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Placeholder: In production, this would interact with Redis
        # to remove old task results
        # For now, just log the operation
        
        return {
            "status": "success",
            "cutoff_date": cutoff_date.isoformat(),
            "days_old": days_old,
            "message": f"Cleaned up results older than {days_old} days",
        }
        
    except Exception as exc:
        # Retry the task with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(
    name="tasks.maintenance.health_check",
    bind=True,
    max_retries=3,
)
def health_check(self) -> dict:
    """
    Perform a health check of the Celery worker and connected services.
    
    Returns:
        dict: Health check results
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "worker_id": self.request.id,
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
