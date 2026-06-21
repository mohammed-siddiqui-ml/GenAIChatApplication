#!/usr/bin/env python3
"""
Video Ingestion Pipeline - Integration Test
Tests video processing components in isolation
"""

import sys
import os
import tempfile
import subprocess

# Add src to path
sys.path.insert(0, '/app/src')

print("=" * 60)
print("Video Integration Test")
print("=" * 60)

def test_step(name, test_func):
    """Run a test step and report results"""
    try:
        print(f"\n[TEST] {name}")
        result = test_func()
        print(f"[✓ PASS] {name}")
        return True
    except Exception as e:
        print(f"[✗ FAIL] {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ffmpeg_extraction():
    """Test FFmpeg audio extraction"""
    # Create test video
    video_path = "/tmp/integration_test.mp4"
    audio_path = "/tmp/integration_test.wav"
    
    # Create video with ffmpeg
    cmd = [
        'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=3:size=320x240:rate=1',
        '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=3',
        '-c:v', 'libx264', '-c:a', 'aac', video_path, '-y'
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg video creation failed: {result.stderr.decode()}")
    
    # Import video processor
    from tasks.ingestion.video_processor import extract_audio
    
    # Extract audio
    extracted_audio = extract_audio(video_path, audio_path)
    
    if not os.path.exists(extracted_audio):
        raise Exception(f"Audio file not created: {extracted_audio}")
    
    file_size = os.path.getsize(extracted_audio)
    if file_size == 0:
        raise Exception("Audio file is empty")
    
    print(f"  Audio extracted: {file_size} bytes")
    
    # Cleanup
    os.remove(video_path)
    os.remove(audio_path)
    
    return True

def test_whisper_import():
    """Test Whisper can be imported"""
    import whisper
    print(f"  Whisper module: {whisper.__file__}")
    return True

def test_video_processor_imports():
    """Test all video processor imports"""
    from tasks.ingestion.video_processor import (
        extract_audio,
        transcribe_audio,
        chunk_video_transcript,
        process_video_async
    )
    print("  All video processor functions imported")
    return True

def test_folder_watch_imports():
    """Test folder watch task imports"""
    from tasks.ingestion.folder_watch import (
        process_file_from_folder,
        _process_video_from_watch_sync,
        _process_pdf_from_watch_sync
    )
    print("  All folder watch functions imported")
    return True

def test_llm_factory():
    """Test LLM factory can create client"""
    from integrations.llm_factory import LLMFactory
    
    client = LLMFactory.create_client()
    print(f"  LLM client created: {client.__class__.__name__}")
    
    embedding_dim = LLMFactory.get_embedding_dimension()
    print(f"  Embedding dimension: {embedding_dim}")
    
    return True

def test_database_schema():
    """Test database has required tables and fields"""
    from core.database import get_session_factory
    from sqlalchemy import inspect, text
    import asyncio
    
    async def check_schema():
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Check if knowledge_documents table has video fields
            result = await session.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'knowledge_documents'")
            )
            columns = [row[0] for row in result]
            
            required_columns = ['video_duration', 'content_type']
            for col in required_columns:
                if col not in columns:
                    raise Exception(f"Missing column: {col}")
            
            print(f"  Database has all required fields")
            return True
    
    return asyncio.run(check_schema())

def test_chunking():
    """Test transcript chunking with timestamps"""
    from tasks.ingestion.video_processor import chunk_video_transcript
    
    # Mock Whisper transcript result
    mock_transcript = {
        'text': 'This is a test transcript. It has multiple sentences. This helps test chunking.',
        'segments': [
            {'text': 'This is a test transcript.', 'start': 0.0, 'end': 2.5},
            {'text': ' It has multiple sentences.', 'start': 2.5, 'end': 5.0},
            {'text': ' This helps test chunking.', 'start': 5.0, 'end': 7.5}
        ]
    }
    
    chunks = chunk_video_transcript(mock_transcript, chunk_size=50, chunk_overlap=10)
    
    if len(chunks) == 0:
        raise Exception("No chunks created")
    
    # Verify chunks have timestamps
    for chunk in chunks:
        if 'start_time' not in chunk or 'end_time' not in chunk:
            raise Exception(f"Chunk missing timestamps: {chunk}")
    
    print(f"  Created {len(chunks)} chunks with timestamps")
    return True

# Run all tests
if __name__ == "__main__":
    tests = [
        ("Whisper import", test_whisper_import),
        ("Video processor imports", test_video_processor_imports),
        ("Folder watch imports", test_folder_watch_imports),
        ("LLM factory", test_llm_factory),
        ("Database schema", test_database_schema),
        ("Transcript chunking", test_chunking),
        ("FFmpeg audio extraction", test_ffmpeg_extraction),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        if test_step(name, test_func):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
