"""
Celery Application Configuration

This module configures the Celery distributed task queue with Redis as broker
and result backend. It sets up task queues, routing, monitoring, and retry policies.

Task Queues:
- default: General purpose tasks
- confluence_queue: Confluence data ingestion tasks
- jira_queue: Jira data ingestion tasks
- embeddings_queue: Embedding generation tasks

Configuration:
- Broker: Redis database 1
- Result Backend: Redis database 2
- Task routing: Automatic routing based on task names
- Retry Policy: Max 3 retries with exponential backoff
- Result Expiration: 24 hours
"""

import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange

# Import Redis helper functions for broker/backend URLs
from core.redis import get_celery_broker_url, get_celery_result_backend_url
from core.config import settings


# ============================================================================
# Celery Application Initialization
# ============================================================================

# Initialize Celery app
celery_app = Celery("knowledge_retrieval_tasks")

# Prefer environment variables for broker/backend if set, otherwise use helper functions
broker_url = os.getenv("CELERY_BROKER_URL") or get_celery_broker_url()
result_backend_url = os.getenv("CELERY_RESULT_BACKEND") or get_celery_result_backend_url()


# ============================================================================
# Celery Configuration
# ============================================================================

celery_app.conf.update(
    # Broker and Result Backend
    broker_url=broker_url,
    result_backend=result_backend_url,
    
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Timezone and Task Scheduling
    timezone="UTC",
    enable_utc=True,
    
    # Task Result Settings
    result_expires=86400,  # 24 hours in seconds
    result_persistent=True,  # Persist results to backend
    task_track_started=True,  # Track when tasks start
    task_ignore_result=False,  # Store task results
    
    # Task Retry Configuration
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    task_default_retry_delay=60,  # 1 minute delay between retries
    task_max_retries=3,  # Maximum 3 retries
    
    # Worker Settings
    worker_prefetch_multiplier=4,  # Number of tasks to prefetch per worker
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)
    
    # Task Routing - Define queues
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("confluence_queue", Exchange("confluence"), routing_key="confluence.*"),
        Queue("jira_queue", Exchange("jira"), routing_key="jira.*"),
        Queue("embeddings_queue", Exchange("embeddings"), routing_key="embeddings.*"),
    ),
    
    # Default queue for tasks without explicit routing
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    
    # Task Routing Rules - Map task names to queues
    task_routes={
        # Confluence tasks
        "tasks.ingestion.confluence.*": {
            "queue": "confluence_queue",
            "routing_key": "confluence.ingestion",
        },
        # Jira tasks
        "tasks.ingestion.jira.*": {
            "queue": "jira_queue",
            "routing_key": "jira.ingestion",
        },
        # Embedding tasks
        "tasks.embeddings.*": {
            "queue": "embeddings_queue",
            "routing_key": "embeddings.generate",
        },
        # Onboarding materials tasks (use default queue)
        "tasks.ingestion.onboarding.*": {
            "queue": "default",
            "routing_key": "default",
        },
    },
    
    # Beat Scheduler Configuration for Periodic Tasks
    beat_schedule={
        # Example: Daily data refresh at 2 AM UTC
        "refresh-confluence-data": {
            "task": "tasks.ingestion.confluence.refresh_confluence_data",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
            "options": {"queue": "confluence_queue"},
        },
        "refresh-jira-data": {
            "task": "tasks.ingestion.jira.refresh_jira_data",
            "schedule": crontab(hour=2, minute=30),  # Daily at 2:30 AM
            "options": {"queue": "jira_queue"},
        },
        # Example: Clean up old results every 6 hours
        "cleanup-task-results": {
            "task": "tasks.maintenance.cleanup_old_results",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
            "options": {"queue": "default"},
        },
    },
    
    # Monitoring and Logging
    task_send_sent_event=True,  # Send task-sent events
    worker_send_task_events=True,  # Enable task events for monitoring
    task_time_limit=3600,  # Hard time limit: 1 hour
    task_soft_time_limit=3000,  # Soft time limit: 50 minutes
)


# ============================================================================
# Task Auto-Discovery
# ============================================================================

# Auto-discover tasks from tasks module
# This will automatically load all tasks from tasks.ingestion, tasks.embeddings, etc.
celery_app.autodiscover_tasks(["tasks.ingestion", "tasks.embeddings", "tasks.maintenance"])


# ============================================================================
# Structured Logging Configuration for Celery
# ============================================================================

# Configure structured JSON logging for Celery workers
import logging
from middleware.logging_middleware import CeleryLoggingContextFilter

# Get celery logger and add context filter
celery_logger = logging.getLogger("celery")
celery_logger.addFilter(CeleryLoggingContextFilter())

# Add filter to task logger as well
task_logger = logging.getLogger("celery.task")
task_logger.addFilter(CeleryLoggingContextFilter())


# ============================================================================
# Celery Application Instance Export
# ============================================================================

__all__ = ["celery_app"]
