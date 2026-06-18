"""
Tasks module containing background tasks and scheduled jobs.

This module exports the Celery application instance configured with
Redis broker and result backend, task queues, routing, and scheduling.
"""

from tasks.celery import celery_app

__all__ = ["celery_app"]
