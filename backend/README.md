# GenAI Knowledge Retrieval System - Backend

FastAPI-based backend service for the GenAI Intelligent Chat-Based Knowledge Retrieval System.

## Overview

This backend provides RESTful APIs for a chat-based knowledge retrieval application powered by GenAI. It integrates with multiple data sources including Confluence, issue tracking systems, and supports both authenticated (admin) and non-authenticated (regular) users.

## Features

- **FastAPI Framework**: High-performance async web framework
- **GenAI Integration**: OpenAI GPT-4 for intelligent responses
- **Vector Search**: Semantic search using embeddings and vector databases
- **Multi-Source Integration**: Confluence, Jira, and custom data sources
- **Authentication**: JWT-based authentication for admin users
- **Background Tasks**: Celery for scheduled data ingestion
- **Caching**: Redis for session management and caching
- **Database**: PostgreSQL with SQLAlchemy ORM

## Project Structure

```
backend/
├── src/
│   ├── api/           # API route handlers
│   ├── core/          # Configuration and logging
│   ├── models/        # Database models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   ├── middleware/    # Custom middleware
│   ├── tasks/         # Background tasks
│   └── utils/         # Utility functions
├── tests/             # Test suite
├── requirements.txt   # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── pyproject.toml     # Tool configurations
├── Dockerfile         # Container configuration
└── Makefile          # Development commands
```

## Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker (optional)

## Installation

### Local Development

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
make install-dev
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the application:
```bash
make run
```

The API will be available at http://localhost:8000

- API Documentation: http://localhost:8000/api/v1/docs
- Alternative Docs: http://localhost:8000/api/v1/redoc

### Docker

```bash
make docker-build
make docker-run
```

## Development

### Code Quality

Format code:
```bash
make format
```

Run linter:
```bash
make lint
```

Type checking:
```bash
make type-check
```

### Testing

Run all tests:
```bash
make test
```

Run with coverage:
```bash
make test-cov
```

## Configuration

All configuration is managed through environment variables. See `.env.example` for all available options.

Key settings:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key for GenAI features
- `SECRET_KEY`: JWT secret key (change in production)

## API Endpoints

- `GET /`: Root endpoint with API information
- `GET /health`: Health check endpoint
- `GET /api/v1/docs`: Interactive API documentation

## License

MIT
