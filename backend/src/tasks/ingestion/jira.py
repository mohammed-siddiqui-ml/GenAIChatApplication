"""
JIRA Ingestion Celery Tasks

This module implements Celery tasks for ingesting JIRA issues into the knowledge base.
Handles fetching issues using JQL queries, extracting text from descriptions and comments,
chunking content, generating embeddings, and database storage with deduplication.
"""

import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tasks.celery import celery_app
from core.database import get_session_factory
from core.config import settings
from models.data_source import DataSource, IngestionJob, JobStatus, DataSourceType
from models.knowledge import KnowledgeDocument, DocumentEmbedding, ContentType
from integrations.jira_client import JiraClient, JiraAPIError
from integrations.openai_client import OpenAIClient, OpenAIError
from utils.text_processing import chunk_text, count_tokens

# Logger
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 500  # tokens
CHUNK_OVERLAP = 50  # tokens
EMBEDDING_BATCH_SIZE = 100  # Process embeddings in batches
DEFAULT_JQL = "ORDER BY updated DESC"  # Default JQL query


# ============================================================================
# Celery Tasks
# ============================================================================

@celery_app.task(
    bind=True,
    name="tasks.ingestion.jira.ingest_jira_issues",
    max_retries=3,
    default_retry_delay=60,
)
def ingest_jira_issues(self, data_source_id: int) -> Dict[str, Any]:
    """
    Ingest JIRA issues for a given data source.
    
    This task:
    1. Fetches issues from JIRA API using configured JQL query
    2. Extracts text from issue summary, description, and comments
    3. Combines issue data into single document per issue
    4. Chunks documents into 500-token chunks with 50-token overlap
    5. Generates embeddings for each chunk (batch processing)
    6. Stores documents in knowledge_documents table with metadata
    7. Stores embeddings in document_embeddings table
    8. Updates ingestion_jobs table with progress and status
    9. Performs deduplication using external_id (JIRA issue key)
    
    Args:
        data_source_id: ID of the JIRA data source to ingest
        
    Returns:
        dict: Summary with status, documents processed, documents failed
        
    Raises:
        Exception: Retries on failure with exponential backoff
    """
    try:
        # Run async ingestion in event loop
        # Use asyncio.run() instead of get_event_loop() to avoid event loop conflicts in Celery
        result = asyncio.run(_ingest_jira_issues_async(data_source_id, self))
        return result
    except Exception as exc:
        logger.error(f"JIRA ingestion failed: {exc}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


async def _ingest_jira_issues_async(data_source_id: int, task_context) -> Dict[str, Any]:
    """
    Async implementation of JIRA issue ingestion.
    
    Args:
        data_source_id: ID of the JIRA data source
        task_context: Celery task context for updates
        
    Returns:
        dict: Summary with status, job_id, documents_processed, documents_failed
    """
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            # Fetch data source
            data_source = await _get_data_source(session, data_source_id)
            
            if not data_source:
                raise ValueError(f"Data source {data_source_id} not found")
                
            if data_source.type != DataSourceType.JIRA:
                raise ValueError(f"Data source {data_source_id} is not a JIRA source")
                
            if not data_source.is_active:
                logger.warning(f"Data source {data_source_id} is not active, skipping")
                return {"status": "skipped", "documents_processed": 0, "documents_failed": 0}

            # Create ingestion job
            job = await _create_ingestion_job(session, data_source_id)
            logger.info(f"Started ingestion job {job.id} for data source {data_source_id}")
            
            # Extract configuration
            config = data_source.source_config or {}
            jql_query = config.get('jql_query', DEFAULT_JQL)
            
            logger.info(f"Using JQL query: {jql_query}")
            
            # Initialize clients
            jira_client = JiraClient()
            openai_client = OpenAIClient()
            
            # Fetch all issues using pagination
            total_processed = 0
            total_failed = 0
            start_at = 0
            max_results = 50
            
            while True:
                try:
                    logger.info(f"Fetching issues (start_at={start_at}, max_results={max_results})")
                    
                    # Fetch issues with JQL
                    result = await jira_client.fetch_issues(
                        jql=jql_query,
                        start_at=start_at,
                        max_results=max_results
                    )
                    
                    issues = result.get('issues', [])
                    total = result.get('total', 0)

                    logger.info(f"Fetched {len(issues)} issues (total: {total})")

                    if not issues:
                        break

                    # Process each issue
                    for issue in issues:
                        try:
                            processed = await _process_issue(
                                session=session,
                                data_source_id=data_source_id,
                                issue=issue,
                                jira_client=jira_client,
                                openai_client=openai_client
                            )

                            if processed:
                                total_processed += 1
                            else:
                                total_failed += 1

                            # Update job progress periodically
                            if (total_processed + total_failed) % 10 == 0:
                                await _update_job_progress(
                                    session, job, total_processed, total_failed
                                )

                        except Exception as e:
                            logger.error(f"Failed to process issue {issue.get('key')}: {e}")
                            total_failed += 1

                    # Check if we've processed all issues
                    if start_at + len(issues) >= total:
                        break

                    # Move to next page
                    start_at += max_results

                except Exception as e:
                    logger.error(f"Failed to fetch issues: {e}")
                    raise

            # Complete the job
            await _complete_job(session, job, JobStatus.SUCCESS, total_processed, total_failed)

            logger.info(
                f"JIRA ingestion completed for data source {data_source_id}: "
                f"{total_processed} processed, {total_failed} failed"
            )

            return {
                "status": "success",
                "job_id": job.id,
                "documents_processed": total_processed,
                "documents_failed": total_failed,
            }

        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            if 'job' in locals():
                await _complete_job(
                    session, job, JobStatus.FAILED,
                    total_processed if 'total_processed' in locals() else 0,
                    total_failed if 'total_failed' in locals() else 0,
                    error_message=str(e)
                )
            raise


# ============================================================================
# Helper Functions
# ============================================================================

async def _get_data_source(session: AsyncSession, data_source_id: int) -> Optional[DataSource]:
    """Fetch data source by ID."""
    result = await session.execute(
        select(DataSource).where(DataSource.id == data_source_id)
    )
    return result.scalar_one_or_none()


async def _create_ingestion_job(session: AsyncSession, data_source_id: int) -> IngestionJob:
    """Create and persist a new ingestion job."""
    job = IngestionJob(
        data_source_id=data_source_id,
        status=JobStatus.RUNNING,
        started_at=datetime.utcnow(),
        documents_processed=0,
        documents_failed=0,
    )
    session.add(job)
    await session.flush()  # Flush to generate ID immediately (SQLite compatibility)
    await session.refresh(job)
    return job


async def _update_job_progress(
    session: AsyncSession,
    job: IngestionJob,
    processed: int,
    failed: int
) -> None:
    """Update job progress."""
    job.documents_processed = processed
    job.documents_failed = failed
    await session.commit()


async def _complete_job(
    session: AsyncSession,
    job: IngestionJob,
    status: JobStatus,
    processed: int,
    failed: int,
    error_message: Optional[str] = None
) -> None:
    """Mark job as complete."""
    job.status = status
    job.documents_processed = processed
    job.documents_failed = failed
    job.completed_at = datetime.utcnow()
    if error_message:
        job.error_message = error_message
    await session.commit()


async def _process_issue(
    session: AsyncSession,
    data_source_id: int,
    issue: Dict[str, Any],
    jira_client: JiraClient,
    openai_client: OpenAIClient
) -> bool:
    """
    Process a single JIRA issue.

    Extracts text from summary, description, and comments, combines into single document,
    chunks it, generates embeddings, and stores in database.
    Performs deduplication using external_id (JIRA issue key).

    Args:
        session: Database session
        data_source_id: Data source ID
        issue: JIRA issue data
        jira_client: JIRA client for fetching comments
        openai_client: OpenAI client for embeddings

    Returns:
        bool: True if processed successfully, False otherwise
    """
    try:
        # Extract issue data
        issue_key = issue.get('key')
        fields = issue.get('fields', {})

        summary = fields.get('summary', '')
        description = fields.get('description', '') or ''
        status = fields.get('status', {}).get('name', 'Unknown')
        resolution = fields.get('resolution', {}).get('name') if fields.get('resolution') else None
        created = fields.get('created')
        updated = fields.get('updated')
        labels = fields.get('labels', [])

        logger.info(f"Processing JIRA issue: {issue_key}")

        # Check for deduplication using external_id
        existing_doc = await session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.data_source_id == data_source_id,
                KnowledgeDocument.external_id == issue_key
            )
        )
        existing = existing_doc.scalar_one_or_none()

        # Fetch comments for the issue
        comments = []
        try:
            comments = await jira_client.fetch_comments(issue_key)
        except Exception as e:
            logger.warning(f"Failed to fetch comments for {issue_key}: {e}")

        # Combine issue content: summary + description + comments
        content_parts = []

        # Add summary
        if summary:
            content_parts.append(f"Summary: {summary}")

        # Add description
        if description:
            content_parts.append(f"\nDescription:\n{description}")

        # Add comments
        if comments:
            content_parts.append("\n\nComments:")
            for comment in comments:
                comment_body = comment.get('body', '')
                comment_author = comment.get('author', {}).get('displayName', 'Unknown')
                comment_created = comment.get('created', '')

                if comment_body:
                    content_parts.append(
                        f"\n[{comment_author} - {comment_created}]: {comment_body}"
                    )

        # Combine all content
        combined_content = '\n'.join(content_parts)

        if not combined_content or len(combined_content.strip()) < 10:
            logger.warning(f"Issue {issue_key} has insufficient content, skipping")
            return False

        # Create document hash for deduplication
        doc_hash = hashlib.sha256(combined_content.encode('utf-8')).hexdigest()

        # Check if content has changed (if document exists)
        if existing:
            if existing.document_hash == doc_hash:
                logger.info(f"Issue {issue_key} already exists with same content, skipping")
                return True  # Not a failure, just already processed
            else:
                logger.info(f"Issue {issue_key} content changed, updating")
                # Mark old document as deleted
                existing.is_deleted = True
                await session.commit()

        # Build issue URL
        issue_url = f"{jira_client.url}/browse/{issue_key}"

        # Extract metadata
        metadata = {
            'issue_key': issue_key,
            'status': status,
            'resolution': resolution,
            'created_date': created,
            'updated_date': updated,
            'labels': labels,
            'priority': fields.get('priority', {}).get('name'),
            'issue_type': fields.get('issuetype', {}).get('name'),
            'project': fields.get('project', {}).get('key'),
            'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
            'reporter': fields.get('reporter', {}).get('displayName') if fields.get('reporter') else None,
            'comment_count': len(comments)
        }

        # Create knowledge document
        document = KnowledgeDocument(
            data_source_id=data_source_id,
            external_id=issue_key,
            title=f"{issue_key}: {summary}",
            content=combined_content,
            content_type=ContentType.ISSUE,
            url=issue_url,
            doc_metadata=metadata,
            document_hash=doc_hash,
            indexed_at=datetime.utcnow(),
            is_deleted=False
        )

        session.add(document)
        await session.flush()  # Get document ID

        # Chunk the document
        chunks = chunk_text(combined_content, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        logger.info(f"Issue {issue_key} chunked into {len(chunks)} chunks")

        # Generate embeddings for chunks (batch processing)
        chunk_embeddings = await openai_client.generate_embeddings_batch(
            chunks, batch_size=EMBEDDING_BATCH_SIZE
        )

        # Store embeddings
        for idx, (chunk_text_content, embedding) in enumerate(zip(chunks, chunk_embeddings)):
            token_count = count_tokens(chunk_text_content)

            doc_embedding = DocumentEmbedding(
                document_id=document.id,
                chunk_index=idx,
                chunk_text=chunk_text_content,
                embedding=embedding,
                token_count=token_count
            )
            session.add(doc_embedding)

        await session.commit()

        logger.info(
            f"Successfully processed issue {issue_key}: "
            f"{len(chunks)} chunks, {len(chunk_embeddings)} embeddings"
        )

        return True

    except Exception as e:
        logger.error(f"Failed to process issue: {e}", exc_info=True)
        await session.rollback()
        return False


@celery_app.task(
    bind=True,
    name="tasks.ingestion.jira.refresh_jira_data",
    max_retries=3,
    default_retry_delay=600,
)
def refresh_jira_data(self) -> Dict[str, Any]:
    """
    Scheduled task to refresh all active JIRA data sources.

    This task is triggered by Celery Beat scheduler to keep data up-to-date.
    Iterates through all active JIRA data sources and triggers ingestion.

    Returns:
        dict: Summary of refresh operation
    """
    try:
        # Use asyncio.run() instead of get_event_loop() to avoid event loop conflicts in Celery
        result = asyncio.run(_refresh_jira_data_async())
        return result
    except Exception as exc:
        logger.error(f"JIRA refresh failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=600)  # Retry after 10 minutes


async def _refresh_jira_data_async() -> Dict[str, Any]:
    """
    Async implementation of JIRA data refresh.

    Returns:
        dict: Summary with total sources, successful, and failed counts
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            # Fetch all active JIRA data sources
            result = await session.execute(
                select(DataSource).where(
                    DataSource.type == DataSourceType.JIRA,
                    DataSource.is_active == True
                )
            )
            data_sources = result.scalars().all()

            logger.info(f"Found {len(data_sources)} active JIRA data sources to refresh")

            total_sources = len(data_sources)
            successful = 0
            failed = 0

            # Trigger ingestion for each data source
            for data_source in data_sources:
                try:
                    logger.info(f"Refreshing JIRA data source: {data_source.name} (ID: {data_source.id})")

                    # Trigger ingestion task asynchronously
                    ingest_jira_issues.delay(data_source.id)

                    successful += 1

                except Exception as e:
                    logger.error(f"Failed to trigger refresh for {data_source.name}: {e}")
                    failed += 1

            logger.info(
                f"JIRA refresh completed: {total_sources} sources, "
                f"{successful} successful, {failed} failed"
            )

            return {
                "status": "success",
                "total_sources": total_sources,
                "successful": successful,
                "failed": failed
            }

        except Exception as e:
            logger.error(f"JIRA refresh failed: {e}", exc_info=True)
            raise


# ============================================================================
# Utility Functions
# ============================================================================

def format_issue_content(issue: dict, include_comments: bool = True) -> str:
    """
    Format JIRA issue into readable text content.

    Extracts and formats key fields from a JIRA issue including summary,
    description, status, and optionally comments.

    Args:
        issue: JIRA issue dictionary from API
        include_comments: Whether to include comments in content

    Returns:
        str: Formatted issue content as plain text
    """
    fields = issue.get("fields", {})

    # Build content parts
    content_parts = []

    # Add summary
    summary = fields.get("summary", "No summary")
    content_parts.append(f"Summary: {summary}")

    # Add description
    description = fields.get("description", "No description")
    content_parts.append(f"\nDescription:\n{description}")

    # Add status
    status = fields.get("status", {})
    status_name = status.get("name", "Unknown") if isinstance(status, dict) else "Unknown"
    content_parts.append(f"\nStatus: {status_name}")

    # Add priority
    priority = fields.get("priority", {})
    priority_name = priority.get("name", "Unknown") if isinstance(priority, dict) else "Unknown"
    content_parts.append(f"Priority: {priority_name}")

    # Add assignee
    assignee = fields.get("assignee", {})
    assignee_name = assignee.get("displayName", "Unassigned") if isinstance(assignee, dict) else "Unassigned"
    content_parts.append(f"Assignee: {assignee_name}")

    # Add labels
    labels = fields.get("labels", [])
    if labels:
        content_parts.append(f"Labels: {', '.join(labels)}")

    # Add comments if requested
    if include_comments:
        comment_data = fields.get("comment", {})
        if isinstance(comment_data, dict):
            comments = comment_data.get("comments", [])
            if comments:
                content_parts.append("\nComments:")
                for idx, comment in enumerate(comments, 1):
                    author = comment.get("author", {})
                    author_name = author.get("displayName", "Unknown") if isinstance(author, dict) else "Unknown"
                    body = comment.get("body", "")
                    content_parts.append(f"\nComment {idx} by {author_name}:")
                    content_parts.append(body)

    return "\n".join(content_parts)
