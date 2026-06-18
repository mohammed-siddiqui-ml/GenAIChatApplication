# Alembic Quick Start Guide

## First Time Setup

```bash
# 1. Ensure PostgreSQL is running
docker compose up -d postgres

# 2. Wait for PostgreSQL to be ready (check health)
docker compose ps postgres

# 3. Run the initial migration
docker compose exec backend alembic upgrade head

# 4. Verify migration succeeded
docker compose exec backend alembic current
```

Expected output:
```
001 (head)
```

## Common Commands

### Check Current Migration Status
```bash
alembic current
```

### View Migration History
```bash
alembic history
```

### Upgrade Database
```bash
# To latest version
alembic upgrade head

# To specific version
alembic upgrade 001

# Upgrade by one version
alembic upgrade +1
```

### Downgrade Database
```bash
# Downgrade by one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade 001

# Downgrade all
alembic downgrade base
```

### Create New Migration
```bash
# Manual migration (empty template)
alembic revision -m "add new column to users"

# Auto-generate from model changes (after models are created)
alembic revision --autogenerate -m "add new column to users"
```

## Docker Commands

When running in Docker environment:

```bash
# All commands should be prefixed with docker compose exec backend
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose exec backend alembic history
```

## Troubleshooting

### Error: "relation already exists"
Tables were created outside of Alembic. Fix:
```bash
# Mark database as current without running migrations
alembic stamp head
```

### Error: "can't connect to database"
Check database is running:
```bash
docker compose ps postgres
docker compose logs postgres
```

### Error: "pgvector extension not found"
Ensure using correct PostgreSQL image:
```yaml
# In docker-compose.yml
postgres:
  image: pgvector/pgvector:pg15
```

### Reset Database Completely
```bash
# WARNING: This deletes all data!
docker compose down -v  # Remove volumes
docker compose up -d postgres
docker compose exec backend alembic upgrade head
```

## Production Deployment

```bash
# 1. Backup database first!
pg_dump -U user -d knowledge_db > backup_$(date +%Y%m%d).sql

# 2. Test migration on staging environment

# 3. Run migration on production
alembic upgrade head

# 4. Verify
alembic current
psql -U user -d knowledge_db -c "SELECT COUNT(*) FROM users;"
```

## Files Overview

- `env.py` - Alembic configuration (loads .env, handles database URL)
- `alembic.ini` - Settings file (database URL, logging)
- `script.py.mako` - Template for new migrations
- `versions/` - Directory containing all migration scripts
- `versions/001_initial_schema.py` - Initial database schema

## Environment Variables

Required in `.env` file:

```bash
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/knowledge_db
```

Note: Alembic automatically converts `asyncpg` to `psycopg2` driver.
