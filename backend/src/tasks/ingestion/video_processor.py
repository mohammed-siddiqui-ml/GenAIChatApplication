"""
Video Processing Pipeline for Whisper Transcription

Handles video file processing:
1. Audio extraction using FFmpeg
2. Transcription using OpenAI Whisper
3. Timestamp-aware chunking
4. Embedding generation and storage

For internal testing/stage environment only.
"""

import os
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio

import ffmpeg
import whisper

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.config import settings
from core.minio_client import download_file, BUCKET_KNOWLEDGE_FILES
from models.data_source import DataSource
from models.knowledge import KnowledgeDocument, DocumentEmbedding, ContentType
from integrations.llm_factory import LLMFactory
from utils.text_processing import chunk_text, count_tokens

logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 500  # tokens
CHUNK_OVERLAP = 50  # tokens
EMBEDDING_BATCH_SIZE = 100
WHISPER_MODEL = settings.WHISPER_MODEL if hasattr(settings, 'WHISPER_MODEL') else 'base'


def extract_audio(video_path: str, output_audio_path: Optional[str] = None) -> str:
    """
    Extract audio from video using FFmpeg
    
    Args:
        video_path: Path to video file
        output_audio_path: Optional output path, creates temp file if not provided
    
    Returns:
        str: Path to extracted audio file
    
    Raises:
        Exception: If audio extraction fails
    """
    try:
        if output_audio_path is None:
            # Create temporary WAV file
            temp_fd, output_audio_path = tempfile.mkstemp(suffix='.wav')
            os.close(temp_fd)
        
        logger.info(f"Extracting audio from video: {video_path}")
        
        # Extract audio with FFmpeg
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(
            stream,
            output_audio_path,
            acodec='pcm_s16le',  # 16-bit PCM
            ar='16000',          # 16kHz sample rate (Whisper requirement)
            ac=1                 # Mono
        )
        ffmpeg.run(stream, overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)
        
        logger.info(f"✅ Audio extracted: {output_audio_path}")
        return output_audio_path
        
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"FFmpeg audio extraction failed: {error_msg}")
        raise Exception(f"Audio extraction failed: {error_msg}")


def transcribe_audio(audio_path: str, model_name: str = WHISPER_MODEL) -> Dict[str, Any]:
    """
    Transcribe audio using Whisper
    
    Args:
        audio_path: Path to audio file
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
    
    Returns:
        dict: Transcription result with 'text' and 'segments' (with timestamps)
    
    Raises:
        Exception: If transcription fails
    """
    try:
        logger.info(f"Loading Whisper model: {model_name}")
        model = whisper.load_model(model_name, device='cpu')
        
        logger.info(f"Transcribing audio: {audio_path}")
        result = model.transcribe(
            audio_path,
            task='transcribe',
            language='en',  # Can be made configurable
            fp16=False      # CPU mode
        )
        
        logger.info(f"✅ Transcription complete: {len(result['segments'])} segments")
        return result
        
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        raise Exception(f"Transcription failed: {e}")


def chunk_video_transcript(
    transcript: Dict[str, Any],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    """
    Chunk video transcript while preserving timestamps
    
    Args:
        transcript: Whisper transcription result
        chunk_size: Max tokens per chunk
        chunk_overlap: Token overlap between chunks
    
    Returns:
        List of chunks with metadata: text, start_time, end_time, chunk_index
    """
    # Get full text
    full_text = transcript['text']
    segments = transcript['segments']
    
    # Chunk the text
    text_chunks = chunk_text(full_text, chunk_size, chunk_overlap)
    
    # Map chunks to timestamps
    chunks_with_timestamps = []
    current_char = 0
    
    for chunk_idx, chunk in enumerate(text_chunks):
        # Find corresponding segments for this chunk
        # Simple approach: match by character position
        chunk_start_char = current_char
        chunk_end_char = current_char + len(chunk)
        
        start_time = None
        end_time = None
        
        # Find segments that overlap with this chunk
        segment_char_pos = 0
        for segment in segments:
            segment_text = segment['text']
            segment_start_pos = segment_char_pos
            segment_end_pos = segment_char_pos + len(segment_text)
            
            # Check if segment overlaps with chunk
            if segment_end_pos >= chunk_start_char and segment_start_pos <= chunk_end_char:
                if start_time is None:
                    start_time = segment['start']
                end_time = segment['end']
            
            segment_char_pos = segment_end_pos
        
        chunks_with_timestamps.append({
            'text': chunk,
            'start_time': start_time or 0.0,
            'end_time': end_time or 0.0,
            'chunk_index': chunk_idx,
            'total_chunks': len(text_chunks)
        })
        
        current_char = chunk_end_char
    
    logger.info(f"Created {len(chunks_with_timestamps)} chunks with timestamps")
    return chunks_with_timestamps


async def process_video_async(
    data_source_id: int,
    minio_path: str,
    filename: str
) -> Dict[str, Any]:
    """
    Process video file: extract audio, transcribe, chunk, embed, store

    Args:
        data_source_id: Data source ID
        minio_path: Path in MinIO bucket
        filename: Original filename

    Returns:
        dict: Processing result with status and counts
    """
    session_factory = get_session_factory()
    video_path = None
    audio_path = None

    try:
        # Download video from MinIO to temp file
        logger.info(f"Downloading video from MinIO: {minio_path}")
        file_stream = download_file(BUCKET_KNOWLEDGE_FILES, minio_path)
        if not file_stream:
            raise Exception(f"Failed to download video: {minio_path}")

        # Save to temporary file
        temp_fd, video_path = tempfile.mkstemp(suffix=Path(filename).suffix)
        os.close(temp_fd)

        with open(video_path, 'wb') as f:
            f.write(file_stream.read())
        file_stream.close()

        logger.info(f"Video saved to temp file: {video_path}")

        # Extract audio
        audio_path = extract_audio(video_path)

        # Transcribe audio
        transcript = transcribe_audio(audio_path)

        # Chunk with timestamps
        chunks = chunk_video_transcript(transcript)

        # Get video duration from last segment
        video_duration = transcript['segments'][-1]['end'] if transcript['segments'] else 0.0

        # Store in database
        async with session_factory() as session:
            # Get data source
            result = await session.execute(
                select(DataSource).where(DataSource.id == data_source_id)
            )
            data_source = result.scalar_one_or_none()
            if not data_source:
                raise Exception(f"Data source not found: {data_source_id}")

            # Create document hash for deduplication
            content_hash = hashlib.sha256(transcript['text'].encode()).hexdigest()

            # Check for existing document
            existing = await session.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.document_hash == content_hash
                )
            )
            if existing.scalar_one_or_none():
                logger.warning(f"Video already processed (duplicate): {filename}")
                return {
                    'documents_processed': 0,
                    'documents_failed': 0,
                    'note': 'Duplicate video skipped'
                }

            # Create knowledge document
            document = KnowledgeDocument(
                data_source_id=data_source_id,
                title=filename,
                content=transcript['text'],
                content_type=ContentType.VIDEO_TRANSCRIPT,
                url=minio_path,
                document_hash=content_hash,
                video_duration=video_duration
            )
            session.add(document)
            await session.flush()

            # Generate embeddings and store chunks
            llm_client = LLMFactory.create_client()
            chunk_texts = [chunk['text'] for chunk in chunks]

            # Check if client supports batch_size parameter (OpenAI does, Ollama doesn't)
            if hasattr(llm_client, '__class__') and llm_client.__class__.__name__ == 'OpenAIClient':
                embeddings = await llm_client.generate_embeddings_batch(
                    chunk_texts,
                    batch_size=EMBEDDING_BATCH_SIZE
                )
            else:
                embeddings = await llm_client.generate_embeddings_batch(chunk_texts)

            # Store embeddings with timestamps
            for chunk, embedding in zip(chunks, embeddings):
                embedding_record = DocumentEmbedding(
                    document_id=document.id,
                    chunk_index=chunk['chunk_index'],
                    chunk_text=chunk['text'],
                    embedding=embedding,
                    token_count=count_tokens(chunk['text'])
                )
                session.add(embedding_record)

                # Update document with timestamp for this chunk
                # Note: We're storing per-chunk, but could aggregate if needed
                document.video_start_time = chunk['start_time']
                document.video_end_time = chunk['end_time']

            await session.commit()
            logger.info(f"✅ Stored video transcript: {len(chunks)} chunks, {document.id}")

            return {
                'documents_processed': 1,
                'documents_failed': 0,
                'chunks_created': len(chunks),
                'video_duration': video_duration
            }

    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        return {
            'documents_processed': 0,
            'documents_failed': 1,
            'error': str(e)
        }

    finally:
        # Cleanup temp files
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
