# Database Migrations with Alembic

This directory contains Alembic database migrations for the GenAI Knowledge Retrieval System.

## Overview

Alembic is used to manage database schema changes in a version-controlled manner. Each migration represents a change to the database schema and can be applied or rolled back.

## Directory Structure

```
alembic/
├── versions/           # Migration scripts
│   └── 001_initial_schema.py  # Initial database schema
├── env.py             # Alembic environment configuration
├── script.py.mako     # Template for new migrations
└── README.md          # This file
```

## Prerequisites

- PostgreSQL 15+ with pgvector extension
- Python environment with dependencies installed
- Database connection configured in `.env` file

## Common Commands

### Apply Migrations

```bash
# Upgrade to the latest version
alembic upgrade head

# Upgrade to a specific revision
alembic upgrade 001

# Upgrade by one revision
alembic upgrade +1
```

### Rollback Migrations

```bash
# Downgrade by one revision
alembic downgrade -1

# Downgrade to a specific revision
alembic downgrade 001

# Downgrade all migrations
alembic downgrade base
```

### View Migration Status

```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show migration history with verbose details
alembic history --verbose
```

### Create New Migrations

```bash
# Create a new empty migration
alembic revision -m "description of changes"

# Auto-generate migration from model changes (when models are set up)
alembic revision --autogenerate -m "description of changes"
```

## Initial Schema (Migration 001)

The initial migration creates the following:

### Extensions
- **pgvector**: Vector similarity search extension

### Tables
1. **users** - Admin user accounts
2. **chat_sessions** - User chat sessions
3. **chat_messages** - Individual chat messages
4. **data_sources** - Configured data sources (Confluence, JIRA, etc.)
5. **ingestion_jobs** - Data ingestion job tracking
6. **knowledge_documents** - Ingested documents with metadata
7. **document_embeddings** - Vector embeddings for semantic search
8. **audit_logs** - Admin action audit trail

### Indexes
- **B-tree indexes**: Standard indexes on foreign keys and frequently queried columns
- **HNSW index**: High-performance vector similarity search on `document_embeddings.embedding`
- **GIN index**: Full-text search on `knowledge_documents.tsvector_content`
- **Unique indexes**: On `users.email`, `chat_sessions.session_token`, etc.

### Triggers
- **tsvector_update_trigger**: Automatically updates full-text search vector when document content changes

## Docker Usage

When running in Docker, use the following command:

```bash
# From the project root
docker-compose exec backend alembic upgrade head

# Or SSH into the container
docker-compose exec backend bash
cd /app
alembic upgrade head
```

## Configuration

Database connection is configured in:
1. `alembic.ini` - Default configuration (for local development)
2. `.env` file - Environment-specific configuration (overrides alembic.ini)

The `env.py` file automatically loads the `DATABASE_URL` from environment variables and converts it from the async driver (`asyncpg`) to the sync driver (`psycopg2`) that Alembic requires.

## Best Practices

1. **Never modify existing migrations** - Create a new migration instead
2. **Test rollbacks** - Always test the downgrade path before deploying
3. **Review auto-generated migrations** - Alembic's autogenerate may miss some changes
4. **Backup before production migrations** - Always backup the database before running migrations in production
5. **Use transactions** - Migrations run in a transaction by default (can be disabled if needed)

## Troubleshooting

### Migration fails with "relation already exists"
- Check if tables were manually created
- Use `alembic stamp head` to mark the database as up-to-date without running migrations

### Can't connect to database
- Verify `DATABASE_URL` in `.env` file
- Check database is running: `docker-compose ps postgres`
- Check database credentials match Docker environment variables

### pgvector extension not found
- Ensure using `pgvector/pgvector:pg15` Docker image
- Manually create extension: `CREATE EXTENSION vector;`
