"""
Data ingestion tasks module.

This module contains Celery tasks for ingesting data from various sources:
- Confluence pages and documentation
- Jira issues and tickets
- Onboarding materials (PDFs, documents, etc.)
- Folder watch (PDFs and videos dropped into watch folder)

Tasks in this module are typically long-running and process data in batches.
"""

# Import tasks here as they are implemented
from tasks.ingestion.confluence import ingest_confluence_docs, refresh_confluence_data
from tasks.ingestion.jira import ingest_jira_issues, refresh_jira_data
from tasks.ingestion.onboarding import ingest_onboarding_materials
from tasks.ingestion.folder_watch import process_file_from_folder

__all__ = [
    'ingest_confluence_docs',
    'refresh_confluence_data',
    'ingest_jira_issues',
    'refresh_jira_data',
    'ingest_onboarding_materials',
    'process_file_from_folder',
]
