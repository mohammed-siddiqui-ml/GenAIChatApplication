-- SQL script to verify database schema after migration
-- Run this with: psql -U user -d knowledge_db -f verify_schema.sql

\echo '=========================================='
\echo 'Database Schema Verification'
\echo '=========================================='
\echo ''

-- Check pgvector extension
\echo 'Checking pgvector extension...'
SELECT extname, extversion 
FROM pg_extension 
WHERE extname = 'vector';
\echo ''

-- Check all tables exist
\echo 'Checking tables...'
SELECT table_name, 
       (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
\echo ''

-- Check ENUM types
\echo 'Checking ENUM types...'
SELECT typname, enumlabel 
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid 
WHERE typname IN ('user_role', 'message_role', 'data_source_type', 'content_type', 'job_status')
ORDER BY typname, enumlabel;
\echo ''

-- Check indexes
\echo 'Checking indexes...'
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
\echo ''

-- Check foreign keys
\echo 'Checking foreign key constraints...'
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
  AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;
\echo ''

-- Check triggers
\echo 'Checking triggers...'
SELECT trigger_name, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'public'
ORDER BY event_object_table, trigger_name;
\echo ''

-- Verify specific tables structure
\echo 'Detailed table structure verification:'
\echo ''

\echo 'Users table:'
\d users
\echo ''

\echo 'Chat Sessions table:'
\d chat_sessions
\echo ''

\echo 'Chat Messages table:'
\d chat_messages
\echo ''

\echo 'Data Sources table:'
\d data_sources
\echo ''

\echo 'Ingestion Jobs table:'
\d ingestion_jobs
\echo ''

\echo 'Knowledge Documents table:'
\d knowledge_documents
\echo ''

\echo 'Document Embeddings table (with pgvector column):'
\d document_embeddings
\echo ''

\echo 'Audit Logs table:'
\d audit_logs
\echo ''

-- Check Alembic version
\echo 'Current Alembic migration version:'
SELECT version_num FROM alembic_version;
\echo ''

\echo '=========================================='
\echo 'Verification complete!'
\echo '=========================================='
