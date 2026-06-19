"""
Confluence Ingestion Celery Tasks

This module implements Celery tasks for ingesting Confluence pages into the knowledge base.
Handles fetching pages from Confluence API, extracting text, chunking, embedding generation,
and database storage with deduplication.
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
from integrations.confluence_client import ConfluenceClient, ConfluenceAPIError
from integrations.openai_client import OpenAIClient, OpenAIError
from utils.text_processing import clean_html, chunk_text, count_tokens

# Logger
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 500  # tokens
CHUNK_OVERLAP = 50  # tokens
EMBEDDING_BATCH_SIZE = 100  # Process embeddings in batches


def compute_document_hash(content: str) -> str:
    """
    Compute SHA-256 hash of document content for deduplication.
    
    Args:
        content: Document text content
        
    Returns:
        str: Hex digest of SHA-256 hash
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


@celery_app.task(
    name="tasks.ingestion.confluence.ingest_confluence_docs",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    time_limit=3600,  # 1 hour hard limit
    soft_time_limit=3300,  # 55 minutes soft limit
)
def ingest_confluence_docs(self, data_source_id: int) -> Dict[str, Any]:
    """
    Ingest Confluence pages for a given data source.
    
    This task:
    1. Fetches pages from Confluence API using configured space keys
    2. Extracts clean text from HTML content
    3. Chunks documents into 500-token chunks with 50-token overlap
    4. Generates embeddings for each chunk (batch processing)
    5. Stores documents in knowledge_documents table with metadata
    6. Stores embeddings in document_embeddings table
    7. Updates ingestion_jobs table with progress and status
    8. Performs deduplication using document_hash (SHA256)
    
    Args:
        data_source_id: ID of the Confluence data source to ingest
        
    Returns:
        dict: Summary with status, documents processed, documents failed
        
    Raises:
        Exception: Retries on failure with exponential backoff
    """
    try:
        # Run async ingestion in event loop
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(_ingest_confluence_docs_async(data_source_id, self))
        return result
    except Exception as exc:
        logger.error(f"Confluence ingestion failed: {exc}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


async def _ingest_confluence_docs_async(data_source_id: int, task_context) -> Dict[str, Any]:
    """
    Async implementation of Confluence document ingestion.
    
    Args:
        data_source_id: ID of the Confluence data source
        task_context: Celery task context for updates
        
    Returns:
        dict: Ingestion summary
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            # Fetch data source configuration FIRST (before creating job)
            data_source = await _get_data_source(session, data_source_id)
            if not data_source:
                raise ValueError(f"Data source {data_source_id} not found")

            if not data_source.is_active:
                raise ValueError(f"Data source {data_source_id} is not active")

            # Create ingestion job
            job = await _create_ingestion_job(session, data_source_id)
            logger.info(f"Started ingestion job {job.id} for data source {data_source_id}")
            
            # Extract configuration
            config = data_source.source_config or {}
            space_keys = config.get('space_keys', [])
            
            if not space_keys:
                logger.warning(f"No space keys configured for data source {data_source_id}")
                await _complete_job(session, job, JobStatus.SUCCESS, 0, 0)
                return {"status": "success", "documents_processed": 0, "documents_failed": 0}
            
            # Initialize clients
            confluence_client = ConfluenceClient()
            openai_client = OpenAIClient()
            
            # Process each space
            total_processed = 0
            total_failed = 0

            for space_key in space_keys:
                try:
                    logger.info(f"Processing Confluence space: {space_key}")

                    # Fetch all pages from the space
                    pages = await confluence_client.fetch_all_pages(space_key)
                    logger.info(f"Fetched {len(pages)} pages from space {space_key}")

                    # Process each page
                    for page in pages:
                        try:
                            processed = await _process_page(
                                session=session,
                                data_source_id=data_source_id,
                                page=page,
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
                            logger.error(f"Failed to process page {page.get('id')}: {e}")
                            total_failed += 1

                except Exception as e:
                    logger.error(f"Failed to process space {space_key}: {e}")
                    continue

            # Complete the job
            await _complete_job(session, job, JobStatus.SUCCESS, total_processed, total_failed)

            # Update data source last_sync_at
            data_source.last_sync_at = datetime.utcnow()
            await session.commit()

            logger.info(
                f"Ingestion job {job.id} completed: "
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


async def _process_page(
    session: AsyncSession,
    data_source_id: int,
    page: Dict[str, Any],
    openai_client: OpenAIClient
) -> bool:
    """
    Process a single Confluence page.

    Extracts text, chunks it, generates embeddings, and stores in database.
    Performs deduplication using document hash.

    Args:
        session: Database session
        data_source_id: Data source ID
        page: Confluence page data
        openai_client: OpenAI client for embeddings

    Returns:
        bool: True if processed successfully, False otherwise
    """
    try:
        # Extract page data
        page_id = page.get('id')
        title = page.get('title', 'Untitled')

        # Extract HTML content from body.storage
        body = page.get('body', {})
        storage = body.get('storage', {})
        html_content = storage.get('value', '')

        if not html_content:
            logger.warning(f"Page {page_id} has no content, skipping")
            return False

        # Clean HTML to extract plain text
        clean_text = clean_html(html_content)

        if not clean_text or len(clean_text.strip()) < 50:
            logger.warning(f"Page {page_id} has insufficient content, skipping")
            return False

        # Compute document hash for deduplication
        doc_hash = compute_document_hash(clean_text)

        # Check if document already exists
        existing_doc = await session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.data_source_id == data_source_id,
                KnowledgeDocument.document_hash == doc_hash
            )
        )
        existing = existing_doc.scalar_one_or_none()

        if existing:
            logger.info(f"Page {page_id} already ingested (hash match), skipping")
            return True

        # Build page URL
        base_url = page.get('_links', {}).get('webui', '')
        page_url = f"{base_url}" if base_url else None

        # Extract metadata
        metadata = {
            'page_id': page_id,
            'space_key': page.get('space', {}).get('key'),
            'version': page.get('version', {}).get('number'),
            'author': page.get('version', {}).get('by', {}).get('displayName'),
            'created_date': page.get('history', {}).get('createdDate'),
            'last_updated': page.get('version', {}).get('when'),
        }

        # Create knowledge document
        document = KnowledgeDocument(
            data_source_id=data_source_id,
            external_id=page_id,
            title=title,
            content=clean_text,
            content_type=ContentType.PAGE,
            url=page_url,
            doc_metadata=metadata,
            document_hash=doc_hash,
            indexed_at=datetime.utcnow(),
            is_deleted=False
        )

        session.add(document)
        await session.flush()  # Get document ID

        # Chunk the document
        chunks = chunk_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        logger.info(f"Page {page_id} chunked into {len(chunks)} chunks")

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
        logger.info(f"Page {page_id} ({title}) ingested with {len(chunks)} chunks")
        return True

    except OpenAIError as e:
        logger.error(f"OpenAI error processing page {page.get('id')}: {e}")
        await session.rollback()
        return False
    except Exception as e:
        logger.error(f"Error processing page {page.get('id')}: {e}", exc_info=True)
        await session.rollback()
        return False


@celery_app.task(
    name="tasks.ingestion.confluence.refresh_confluence_data",
    bind=True,
    max_retries=2,
)
def refresh_confluence_data(self) -> Dict[str, Any]:
    """
    Scheduled task to refresh all active Confluence data sources.

    This task is triggered by Celery Beat scheduler to keep data up-to-date.
    Iterates through all active Confluence data sources and triggers ingestion.

    Returns:
        dict: Summary of refresh operation
    """
    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(_refresh_confluence_data_async())
        return result
    except Exception as exc:
        logger.error(f"Confluence refresh failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=600)  # Retry after 10 minutes


async def _refresh_confluence_data_async() -> Dict[str, Any]:
    """
    Async implementation of Confluence data refresh.

    Returns:
        dict: Refresh summary
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            # Get all active Confluence data sources
            result = await session.execute(
                select(DataSource).where(
                    DataSource.type == DataSourceType.CONFLUENCE,
                    DataSource.is_active == True
                )
            )
            data_sources = result.scalars().all()

            logger.info(f"Found {len(data_sources)} active Confluence data sources")

            # Trigger ingestion for each data source
            triggered = 0
            for data_source in data_sources:
                try:
                    # Queue ingestion task asynchronously
                    ingest_confluence_docs.delay(data_source.id)
                    triggered += 1
                    logger.info(f"Triggered ingestion for data source {data_source.id}")
                except Exception as e:
                    logger.error(f"Failed to trigger ingestion for {data_source.id}: {e}")

            return {
                "status": "success",
                "data_sources_found": len(data_sources),
                "ingestions_triggered": triggered,
            }

        except Exception as e:
            logger.error(f"Refresh failed: {e}", exc_info=True)
            raise
