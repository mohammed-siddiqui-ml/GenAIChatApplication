"""
Celery Application Bridge Module

This module provides backward compatibility for docker-compose.yml which references
'app.celery_app'. It imports and re-exports the Celery application from the main
tasks module located at src/tasks/celery.py.

For direct usage, prefer importing from: tasks.celery
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import the Celery app from the tasks module
from tasks.celery import celery_app

# Re-export for compatibility
__all__ = ["celery_app"]
