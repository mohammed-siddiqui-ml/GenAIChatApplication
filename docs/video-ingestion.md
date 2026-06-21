# Video Ingestion Feature

## Overview

The GenAI Chat Application now supports automatic video ingestion through the folder watch service. Videos dropped into the `watch_folder` directory are automatically processed, transcribed using OpenAI Whisper, and made searchable in the RAG system.

## Architecture

### Components

1. **Folder Watcher Service** (`backend/src/services/folder_watcher.py`)
   - Monitors `/app/watch_folder` for new files
   - Supports multiple video formats: MP4, AVI, MOV, MKV, WEBM, FLV, M4V
   - Automatically dispatches Celery tasks for processing

2. **Video Processor** (`backend/src/tasks/ingestion/video_processor.py`)
   - **Audio Extraction**: Uses FFmpeg to extract audio from video (16kHz mono WAV)
   - **Transcription**: Uses OpenAI Whisper to transcribe audio to text
   - **Chunking**: Splits transcript into searchable chunks with timestamps
   - **Embedding**: Generates embeddings using Ollama (nomic-embed-text)
   - **Storage**: Stores chunks and embeddings in PostgreSQL with pgvector

3. **Folder Watch Task** (`backend/src/tasks/ingestion/folder_watch.py`)
   - Celery task that routes files to appropriate processors
   - Handles PDF and video files
   - Moves processed files to `_processed` subfolder

## Technical Details

### Video Processing Pipeline

```
Video File (.mp4)
    ↓
FFmpeg Audio Extraction (16kHz mono WAV)
    ↓
Whisper Transcription (base model, CPU)
    ↓
Timestamp-aware Chunking (500 tokens, 50 overlap)
    ↓
Embedding Generation (Ollama nomic-embed-text, 768 dims)
    ↓
PostgreSQL Storage (document_embeddings table)
```

### Whisper Configuration

- **Model**: `base` (default, configurable via `WHISPER_MODEL`)
- **Device**: CPU mode (no GPU required)
- **Language**: English
- **Output**: Text transcription with word-level timestamps

### FFmpeg Configuration

- **Audio Codec**: PCM 16-bit (`pcm_s16le`)
- **Sample Rate**: 16kHz (Whisper requirement)
- **Channels**: Mono
- **Output Format**: WAV

### Database Schema

Video transcripts are stored in the `knowledge_documents` table with:
- `content_type`: `VIDEO_TRANSCRIPT`
- `video_duration`: Total video length in seconds
- `video_start_time`: Start time for chunk (per embedding)
- `video_end_time`: End time for chunk (per embedding)

## Setup and Configuration

### 1. Environment Variables

Add to `.env` or docker-compose.yml:

```bash
FOLDER_WATCH_ENABLED=true
FOLDER_WATCH_PATH=/app/watch_folder
FOLDER_WATCH_DATA_SOURCE_ID=1
WHISPER_MODEL=base  # Options: tiny, base, small, medium, large
```

### 2. Data Source

Create a folder_watch data source in the database:

```sql
INSERT INTO data_sources (id, name, type, is_active, config)
VALUES (
    1,
    'Local Folder Watch',
    'folder_watch'::data_source_type,
    true,
    '{"path": "/app/watch_folder", "supported_formats": ["pdf", "mp4", "avi", "mov"]}'::jsonb
);
```

### 3. Docker Configuration

The `docker-compose.yml` already includes:
- Volume mount: `./watch_folder:/app/watch_folder`
- FFmpeg installed in backend container
- Environment variables for folder watching

## Usage

### Ingesting a Video

1. Drop a video file into the `watch_folder` directory:
   ```bash
   cp my_video.mp4 watch_folder/
   ```

2. The folder watcher automatically:
   - Detects the new file
   - Uploads it to MinIO
   - Dispatches a Celery task for processing
   - Extracts audio with FFmpeg
   - Transcribes with Whisper
   - Generates embeddings
   - Stores in database
   - Moves file to `watch_folder/_processed/`

3. Query the video content in the chat interface

### Monitoring

Check Celery worker logs for processing status:
```bash
docker logs knowledge_celery_worker --tail 100 | grep "video\|Whisper\|transcript"
```

Check backend logs for folder watcher activity:
```bash
docker logs knowledge_backend --tail 50 | grep "folder_watcher"
```

## Dependencies

### Python Packages

- `openai-whisper>=20231117` - Speech-to-text transcription
- `ffmpeg-python==0.2.0` - Video/audio processing
- `watchdog==3.0.0` - File system monitoring

### System Packages

- `ffmpeg` - Audio extraction (installed in Dockerfile)

## Performance Considerations

### Processing Time

- **5-minute video**: ~2-3 minutes processing time (CPU)
- **Whisper base model**: Good balance of speed and accuracy
- **GPU acceleration**: Not currently enabled (can be added)

### Storage

- Videos are stored in MinIO after processing
- Original files moved to `_processed` folder
- Only transcripts and embeddings stored in PostgreSQL

## Troubleshooting

### "Video processing not implemented" Warning

**Solution**: Ensure the latest code is deployed:
```bash
docker-compose restart backend celery_worker
```

### FFmpeg Not Found

**Verify FFmpeg is installed**:
```bash
docker exec knowledge_backend which ffmpeg
docker exec knowledge_backend ffmpeg -version
```

### Whisper Model Download Issues

Whisper models are auto-downloaded on first use. For the `base` model:
- Model size: ~140MB
- Download location: `~/.cache/whisper/`

### Celery Task Failures

Check Celery logs for detailed errors:
```bash
docker logs knowledge_celery_worker --tail 200
```

Common issues:
- FFmpeg not installed → Check Dockerfile
- Whisper model download failed → Check network/disk space
- Ollama not running → Check Ollama container status

## Future Enhancements

1. **GPU Support**: Add CUDA support for faster Whisper transcription
2. **Video Thumbnails**: Generate thumbnails for better UX
3. **Speaker Diarization**: Identify different speakers in video
4. **Language Detection**: Auto-detect video language
5. **Subtitle Export**: Export SRT/VTT subtitle files
6. **Video Preview**: Show video clips in chat responses with timestamps

## See Also

- [Admin Setup Guide](admin-setup.md)
- [Deployment Guide](deployment.md)
- [RAG System Documentation](rag-system.md)
