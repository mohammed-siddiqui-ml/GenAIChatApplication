"""
Celery tasks for processing files from watched folder

Handles routing of PDFs and videos to appropriate processing pipelines.
For internal testing/stage environment only.
"""

import logging
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any

from tasks.celery import celery_app
from core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.ingestion.folder_watch.process_file_from_folder")
def process_file_from_folder(
    self,
    data_source_id: int,
    filepath: str,
    file_type: str
) -> Dict[str, Any]:
    """
    Process file from watched folder (synchronous)

    Args:
        data_source_id: ID of data source
        filepath: Full path to file on disk
        file_type: 'pdf' or 'video'

    Returns:
        dict: Processing result
    """
    try:
        filename = Path(filepath).name
        logger.info(f"🔄 Processing {file_type}: {filename}")

        # 1. Upload to MinIO
        minio_path = f"folder-watch/{filename}"
        upload_success = _upload_to_minio_sync(filepath, minio_path, file_type)

        if not upload_success:
            raise Exception(f"Failed to upload {filename} to MinIO")

        logger.info(f"✅ Uploaded {filename} to MinIO: {minio_path}")

        # 2. Process based on file type
        if file_type == 'pdf':
            result = _process_pdf_from_watch_sync(data_source_id, minio_path, filename)
        elif file_type == 'video':
            result = _process_video_from_watch_sync(data_source_id, minio_path, filename)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # 3. Move file to processed folder
        try:
            processed_folder = Path(filepath).parent / "_processed"
            logger.info(f"📁 Creating processed folder: {processed_folder}")
            processed_folder.mkdir(exist_ok=True)

            source_path = Path(filepath)
            dest_path = processed_folder / filename

            logger.info(f"📦 Moving file from {source_path} to {dest_path}")
            shutil.move(str(source_path), str(dest_path))
            logger.info(f"✅ File moved successfully to _processed folder")
        except Exception as move_error:
            logger.error(f"⚠️ Failed to move file to _processed (continuing anyway): {move_error}")

        logger.info(f"✅ Completed processing: {filename}")
        
        return {
            'status': 'success',
            'filename': filename,
            'file_type': file_type,
            'minio_path': minio_path,
            **result
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing {filepath}: {e}")
        return {
            'status': 'failed',
            'filename': Path(filepath).name,
            'error': str(e)
        }


def _upload_to_minio_sync(filepath: str, minio_path: str, file_type: str) -> bool:
    """
    Upload file to MinIO
    
    Args:
        filepath: Local file path
        minio_path: Path in MinIO bucket
        file_type: Type of file for content-type detection
    
    Returns:
        bool: Success status
    """
    try:
        from core.minio_client import upload_file, BUCKET_KNOWLEDGE_FILES
        
        # Determine content type
        content_type_map = {
            'pdf': 'application/pdf',
            'video': 'video/mp4'  # Generic, will be auto-detected
        }
        content_type = content_type_map.get(file_type, 'application/octet-stream')
        
        # Upload file
        with open(filepath, 'rb') as f:
            file_size = Path(filepath).stat().st_size
            success = upload_file(
                bucket_name=BUCKET_KNOWLEDGE_FILES,
                object_name=minio_path,
                file_data=f,
                file_size=file_size,
                content_type=content_type
            )
        
        return success
        
    except Exception as e:
        logger.error(f"MinIO upload failed: {e}")
        return False


def _process_pdf_from_watch_sync(data_source_id: int, minio_path: str, filename: str) -> Dict[str, Any]:
    """
    Process PDF using existing onboarding pipeline

    Args:
        data_source_id: Data source ID
        minio_path: Path in MinIO
        filename: Original filename

    Returns:
        dict: Processing result
    """
    # Import the async function and run it synchronously
    import asyncio
    from tasks.ingestion.onboarding import _ingest_onboarding_materials_async
    import core.database as db_module

    logger.info(f"📄 Processing PDF through onboarding pipeline: {filename}")

    # Reset global database engine to avoid event loop conflicts in Celery workers
    db_module._engine = None
    db_module._async_session_factory = None

    # Use asyncio.run() to properly handle async execution in Celery worker
    try:
        result = asyncio.run(_ingest_onboarding_materials_async(data_source_id, minio_path, None))
        return result if result else {}
    except Exception as e:
        logger.error(f"Error in PDF processing: {e}")
        return {'status': 'error', 'message': str(e)}
    finally:
        # Clean up the engine created in this async context
        db_module._engine = None
        db_module._async_session_factory = None


def _process_video_from_watch_sync(data_source_id: int, minio_path: str, filename: str) -> Dict[str, Any]:
    """
    Process video using video pipeline

    Args:
        data_source_id: Data source ID
        minio_path: Path in MinIO
        filename: Original filename

    Returns:
        dict: Processing result
    """
    logger.info(f"🎬 Processing video through Whisper pipeline: {filename}")
    # For now, return a placeholder - video processing needs to be implemented separately
    logger.warning(f"Video processing not yet implemented for: {filename}")
    return {'status': 'skipped', 'reason': 'video processing not implemented'}
