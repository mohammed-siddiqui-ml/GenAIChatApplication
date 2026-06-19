"""
Data ingestion tasks module.

This module contains Celery tasks for ingesting data from various sources:
- Confluence pages and documentation
- Jira issues and tickets
- Onboarding materials (PDFs, documents, etc.)

Tasks in this module are typically long-running and process data in batches.
"""

# Import tasks here as they are implemented
from tasks.ingestion.confluence import ingest_confluence_docs, refresh_confluence_data
# from tasks.ingestion.jira import refresh_jira_data, ingest_jira_issue
# from tasks.ingestion.onboarding import process_onboarding_material

__all__ = [
    'ingest_confluence_docs',
    'refresh_confluence_data',
]
