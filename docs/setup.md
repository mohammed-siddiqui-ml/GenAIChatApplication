# Local Development Setup Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- **Docker Desktop**: 4.20+ ([Download](https://www.docker.com/products/docker-desktop))
- **Node.js**: 18+ ([Download](https://nodejs.org/))
- **Python**: 3.11+ ([Download](https://www.python.org/downloads/))
- **Git**: 2.30+ ([Download](https://git-scm.com/downloads))

### Recommended Tools
- **Visual Studio Code** with extensions:
  - Python
  - ESLint
  - Prettier
  - Docker
  - REST Client
- **Postman** or **Insomnia** for API testing
- **pgAdmin** or **DBeaver** for database management

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo
```

### 2. Setup Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# The defaults work for local development
# Edit if needed:
nano .env
```

### 3. Start All Services

```bash
# Start all services with Docker Compose
docker-compose up -d

# This will start:
# - PostgreSQL (port 5432)
# - Redis (port 6379)
# - MinIO (port 9000, console: 9001)
# - Backend API (port 8000)
# - Frontend (port 3000)
# - Celery Worker
# - Nginx (port 80)
# - Prometheus (port 9090)
# - Grafana (port 3001)
# - Loki (port 3100)
```

### 4. Initialize Database

```bash
# Run database migrations
docker-compose exec backend alembic upgrade head

# Create sample admin user (optional)
docker-compose exec backend python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.user import User
from core.security import hash_password
import os

engine = create_engine(os.getenv('DATABASE_URL').replace('asyncpg', 'psycopg2'))
Session = sessionmaker(bind=engine)
session = Session()

admin = User(
    email='admin@example.com',
    username='admin',
    password_hash=hash_password('admin123'),
    is_active=True,
    is_admin=True
)
session.add(admin)
session.commit()
print('Admin user created: admin@example.com / admin123')
"
```

### 5. Access Applications

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/v1/docs
- **MinIO Console**: http://localhost:9001 (minioadmin / minioadmin123)
- **Grafana Dashboard**: http://localhost:3001 (admin / admin123)
- **Prometheus**: http://localhost:9090

### 6. Verify Setup

```bash
# Check all services are running
docker-compose ps

# Check backend health
curl http://localhost:8000/health

# View logs
docker-compose logs -f backend
```

## Detailed Setup

## Backend Setup

### Option 1: Docker Development (Recommended)

```bash
# Start backend in development mode
docker-compose up -d backend celery_worker

# View logs
docker-compose logs -f backend

# Access backend shell
docker-compose exec backend bash

# Run migrations
docker-compose exec backend alembic upgrade head

# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "description"
```

#### Option 2: Local Python Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/knowledge_db"
export REDIS_URL="redis://localhost:6379/0"
# ... other variables from .env

# Run migrations
alembic upgrade head

# Start development server
uvicorn src.main:app_with_socketio --reload --host 0.0.0.0 --port 8000

# Or use the Makefile
make dev
```

## Frontend Setup

### Option 1: Docker Development

```bash
# Start frontend in development mode
docker-compose up -d frontend

# View logs
docker-compose logs -f frontend

# Access frontend shell
docker-compose exec frontend sh

# Install new package
docker-compose exec frontend npm install <package-name>
```

#### Option 2: Local Node Development

```bash
cd frontend

# Install dependencies
npm install

# Set environment variables
export VITE_API_URL=http://localhost:8000

# Start development server
npm run dev

# Runs on http://localhost:3000

# Build for production
npm run build

# Preview production build
npm run preview
```

## Development Workflow

### Working with Database

#### Access PostgreSQL

```bash
# Using Docker
docker-compose exec postgres psql -U user -d knowledge_db

# Using local psql client
psql -h localhost -U user -d knowledge_db
```

#### Database Migrations

```bash
# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "Add new table"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback last migration
docker-compose exec backend alembic downgrade -1

# View migration history
docker-compose exec backend alembic history
```

### Working with Redis

```bash
# Access Redis CLI
docker-compose exec redis redis-cli

# Authenticate
AUTH redispassword

# Check keys
KEYS *

# Monitor commands
MONITOR
```

### Working with MinIO

```bash
# Access MinIO Console: http://localhost:9001
# Login: minioadmin / minioadmin123

# List buckets
docker-compose exec minio mc ls local

# Upload file
docker-compose exec minio mc cp /path/to/file local/knowledge-files/
```

### Working with Celery

```bash
# View active tasks
docker-compose exec celery_worker celery -A src.celery_app inspect active

# View scheduled tasks
docker-compose exec celery_worker celery -A src.celery_app inspect scheduled

# Purge all tasks
docker-compose exec celery_worker celery -A src.celery_app purge
```

## Testing

### Backend Tests

```bash
# Run all tests
docker-compose exec backend pytest

# Run with coverage
docker-compose exec backend pytest --cov=src --cov-report=html

# Run specific test file
docker-compose exec backend pytest tests/test_auth.py

# Run specific test
docker-compose exec backend pytest tests/test_auth.py::test_user_registration

# View coverage report
open backend/htmlcov/index.html
```

### Frontend Tests

```bash
# Run all tests
docker-compose exec frontend npm test

# Run with coverage
docker-compose exec frontend npm run test:coverage

# Run in watch mode
docker-compose exec frontend npm run test:watch

# View coverage report
open frontend/coverage/index.html
```

### Integration Tests

```bash
# Run integration tests
cd tests
python -m pytest integration/

# Run end-to-end tests
npm run test:e2e
```

### API Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test authentication
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "Test123!@#"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!@#"
  }'
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :8000  # On macOS/Linux
netstat -ano | findstr :8000  # On Windows

# Kill process
kill -9 <PID>  # On macOS/Linux
taskkill /PID <PID> /F  # On Windows

# Or change port in .env file
```

### Docker Issues

```bash
# Remove all containers and volumes
docker-compose down -v

# Rebuild all images
docker-compose build --no-cache

# Restart all services
docker-compose up -d --force-recreate

# Check Docker disk usage
docker system df

# Clean up Docker
docker system prune -a
```

### Database Migration Issues

```bash
# Reset database (WARNING: Deletes all data)
docker-compose down -v
docker-compose up -d postgres
docker-compose exec backend alembic upgrade head

# If migrations are stuck, manually delete alembic_version
docker-compose exec postgres psql -U user -d knowledge_db -c "DELETE FROM alembic_version;"
docker-compose exec backend alembic upgrade head
```

### Frontend Build Issues

```bash
# Clear npm cache
docker-compose exec frontend npm cache clean --force

# Delete node_modules and reinstall
docker-compose exec frontend rm -rf node_modules
docker-compose exec frontend npm install

# Or rebuild frontend container
docker-compose build --no-cache frontend
```

### Backend Module Import Issues

```bash
# Ensure PYTHONPATH is set correctly
docker-compose exec backend bash
export PYTHONPATH=/app/src:$PYTHONPATH

# Or add to .env file
PYTHONPATH=/app/src
```

### Can't Access Services

```bash
# Check if services are running
docker-compose ps

# Check service logs
docker-compose logs <service-name>

# Check network connectivity
docker-compose exec backend ping postgres
docker-compose exec backend ping redis

# Restart networking
docker-compose down
docker network prune
docker-compose up -d
```

## Environment Variables

### Required Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/knowledge_db
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=knowledge_db

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=redispassword

# Application
SECRET_KEY=your-secret-key-min-32-chars
ENVIRONMENT=development
DEBUG=true

# GenAI
OPENAI_API_KEY=sk-your-api-key
```

### Optional Variables

See `.env.example` for complete list of environment variables.

## Code Quality

### Linting

```bash
# Backend (Python)
docker-compose exec backend flake8 src/
docker-compose exec backend black src/ --check
docker-compose exec backend mypy src/

# Frontend (TypeScript)
docker-compose exec frontend npm run lint
docker-compose exec frontend npm run type-check
```

### Formatting

```bash
# Backend
docker-compose exec backend black src/
docker-compose exec backend isort src/

# Frontend
docker-compose exec frontend npm run format
```

## Hot Reload

Both backend and frontend support hot reload in development mode:

- **Backend**: Changes to Python files automatically reload uvicorn
- **Frontend**: Changes to React/TypeScript files trigger Vite HMR

## IDE Setup

### VS Code Settings

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

## Next Steps

1. Review [API Documentation](./api.md)
2. Read [Deployment Guide](./deployment.md)
3. Explore [Architecture Documentation](../README.md)
4. Join development discussions

## Support

- **Documentation**: `/docs`
- **API Docs**: http://localhost:8000/api/v1/docs
- **Issues**: GitHub Issues
- **Email**: dev@yourdomain.com

```

