#!/bin/bash
# Comprehensive Video Ingestion Pipeline Test Script
# Tests all components of the video processing system

set -e

echo "======================================================"
echo "Video Ingestion Pipeline - Comprehensive Test Suite"
echo "======================================================"
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

test_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED${NC}: $1"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}: $1"
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "Test 1: Verify Docker containers are running"
docker ps --format "{{.Names}}" | grep -q "knowledge_backend" && \
docker ps --format "{{.Names}}" | grep -q "knowledge_celery_worker" && \
docker ps --format "{{.Names}}" | grep -q "knowledge_postgres" && \
docker ps --format "{{.Names}}" | grep -q "knowledge_ollama"
test_status "All required containers are running"

echo
echo "Test 2: Verify FFmpeg is installed in backend"
docker exec knowledge_backend which ffmpeg > /dev/null 2>&1
test_status "FFmpeg is installed"

echo
echo "Test 3: Verify FFmpeg can create video"
docker exec knowledge_backend ffmpeg -f lavfi -i testsrc=duration=2:size=320x240:rate=1 \
    -f lavfi -i sine=frequency=1000:duration=2 \
    -c:v libx264 -c:a aac /tmp/test_video.mp4 -y > /dev/null 2>&1
test_status "FFmpeg can create test video"

echo
echo "Test 4: Verify FFmpeg can extract audio"
docker exec knowledge_backend ffmpeg -i /tmp/test_video.mp4 \
    -acodec pcm_s16le -ar 16000 -ac 1 /tmp/test_audio.wav -y > /dev/null 2>&1
test_status "FFmpeg can extract audio"

echo
echo "Test 5: Verify Whisper is installed"
docker exec knowledge_celery_worker python3 -c "import whisper" 2>/dev/null
test_status "Whisper module is importable"

echo
echo "Test 6: Verify folder watch data source exists"
docker exec knowledge_postgres psql -U user -d knowledge_db -t -c \
    "SELECT COUNT(*) FROM data_sources WHERE id = 1 AND type = 'folder_watch'" | grep -q "1"
test_status "Folder watch data source configured"

echo
echo "Test 7: Verify folder watcher is running"
docker logs knowledge_backend 2>&1 | grep -q "Started watching folder: /app/watch_folder"
test_status "Folder watcher service started"

echo
echo "Test 8: Verify video processor code exists"
docker exec knowledge_backend test -f /app/src/tasks/ingestion/video_processor.py
test_status "Video processor file exists"

echo
echo "Test 9: Verify video processor imports correctly"
docker exec knowledge_celery_worker python3 -c \
    "import sys; sys.path.insert(0, '/app/src'); from tasks.ingestion.video_processor import process_video_async" 2>/dev/null
test_status "Video processor imports without errors"

echo
echo "Test 10: Verify folder watch task imports correctly"
docker exec knowledge_celery_worker python3 -c \
    "import sys; sys.path.insert(0, '/app/src'); from tasks.ingestion.folder_watch import process_file_from_folder" 2>/dev/null
test_status "Folder watch task imports without errors"

echo
echo "Test 11: Verify Ollama is accessible"
curl -s http://localhost:11434/api/tags > /dev/null 2>&1
test_status "Ollama API is accessible"

echo
echo "Test 12: Verify nomic-embed-text model exists"
curl -s http://localhost:11434/api/tags | grep -q "nomic-embed-text"
test_status "nomic-embed-text model is available"

echo
echo "Test 13: Check database schema for video fields"
docker exec knowledge_postgres psql -U user -d knowledge_db -c "\d knowledge_documents" | grep -q "video_duration"
test_status "Database has video metadata fields"

echo
echo "Test 14: Verify MinIO is accessible"
curl -s http://localhost:9000/minio/health/live > /dev/null 2>&1
test_status "MinIO is accessible"

echo
echo "Test 15: Verify watch folder exists and is writable"
docker exec knowledge_backend test -d /app/watch_folder && \
docker exec knowledge_backend test -w /app/watch_folder
test_status "Watch folder exists and is writable"

echo
echo "======================================================"
echo "Test Summary"
echo "======================================================"
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo -e "Total Tests:  $((TESTS_PASSED + TESTS_FAILED))"
echo

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo
    echo "The video ingestion pipeline is ready for end-to-end testing."
    echo "Next step: Drop a video file into watch_folder/ to test the full pipeline."
    exit 0
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    echo "Please review the errors above."
    exit 1
fi
