#!/bin/bash
# Test script for database migration
# This script tests the Alembic migration in a Docker environment

set -e  # Exit on error

echo "=========================================="
echo "Database Migration Test Script"
echo "=========================================="
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# Navigate to project root
cd "$(dirname "$0")/../.."

echo "Step 1: Starting PostgreSQL container..."
docker compose up -d postgres

echo ""
echo "Step 2: Waiting for PostgreSQL to be ready..."
sleep 10

# Check if postgres is healthy
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U user > /dev/null 2>&1; then
        echo "PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: PostgreSQL failed to start"
        exit 1
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

echo ""
echo "Step 3: Checking pgvector extension availability..."
docker compose exec -T postgres psql -U user -d knowledge_db -c "SELECT 1" > /dev/null 2>&1 || {
    echo "Creating database..."
    docker compose exec -T postgres psql -U user -c "CREATE DATABASE knowledge_db" > /dev/null 2>&1 || true
}

echo ""
echo "Step 4: Running Alembic migration (upgrade head)..."
cd backend
docker compose exec -T backend alembic upgrade head || {
    echo "Note: Backend container may not be running. Attempting manual migration..."
    docker compose run --rm -w /app/backend backend alembic upgrade head
}

echo ""
echo "Step 5: Verifying migration..."
docker compose exec -T postgres psql -U user -d knowledge_db -c "
    SELECT 'Tables created successfully!' 
    WHERE EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('users', 'chat_sessions', 'chat_messages', 'data_sources', 
                          'ingestion_jobs', 'knowledge_documents', 'document_embeddings', 'audit_logs')
    );
"

echo ""
echo "Step 6: Checking pgvector extension..."
docker compose exec -T postgres psql -U user -d knowledge_db -c "
    SELECT * FROM pg_extension WHERE extname = 'vector';
"

echo ""
echo "Step 7: Listing all tables..."
docker compose exec -T postgres psql -U user -d knowledge_db -c "
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    ORDER BY table_name;
"

echo ""
echo "Step 8: Checking indexes..."
docker compose exec -T postgres psql -U user -d knowledge_db -c "
    SELECT indexname, tablename 
    FROM pg_indexes 
    WHERE schemaname = 'public' 
    ORDER BY tablename, indexname;
"

echo ""
echo "Step 9: Testing migration rollback (downgrade -1)..."
cd backend
docker compose exec -T backend alembic downgrade -1 || {
    docker compose run --rm -w /app/backend backend alembic downgrade -1
}

echo ""
echo "Step 10: Re-applying migration (upgrade head)..."
docker compose exec -T backend alembic upgrade head || {
    docker compose run --rm -w /app/backend backend alembic upgrade head
}

echo ""
echo "=========================================="
echo "Migration test completed successfully!"
echo "=========================================="
