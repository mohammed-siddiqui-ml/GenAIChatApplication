# GenAI Intelligent Chat-Based Knowledge Retrieval System

A GenAI-powered chat-based knowledge retrieval application that enables users to query and obtain accurate, context-aware responses from multiple structured and unstructured data sources.

## Features

- **Chat Interface**: Conversational interface for querying knowledge sources
- **Multi-Source Integration**: Confluence, Jira, and onboarding materials
- **GenAI Powered**: Context-aware responses using LLMs
- **Role-Based Access**: Regular users and admin users with different permissions
- **Real-time Updates**: Scheduled data refresh from knowledge sources

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Database**: PostgreSQL
- **Cache**: Redis
- **ORM**: SQLAlchemy with Alembic migrations
- **GenAI**: OpenAI API, LangChain
- **Vector Store**: ChromaDB / FAISS
- **Task Queue**: Celery

### Frontend
- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **Data Fetching**: React Query
- **Routing**: React Router

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### Installation

See [setup-log.md](artifacts/setup/setup-log.md) for detailed setup instructions.

## Project Structure

```
project-code/
├── backend/           # FastAPI backend application
├── frontend/          # React frontend application
├── infrastructure/    # Infrastructure as Code and deployment configs
├── config/            # Configuration files
├── docs/              # Documentation
└── scripts/           # Utility scripts
```

## License

Proprietary
