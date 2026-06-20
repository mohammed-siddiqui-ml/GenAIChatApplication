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
- **Database**: PostgreSQL with pgvector
- **Cache**: Redis
- **ORM**: SQLAlchemy with Alembic migrations
- **GenAI**: OpenAI API or Ollama (local LLM), LangChain
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

### Environment Configuration

Before running the application, you need to configure environment variables:

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file with your credentials:**
   ```bash
   nano .env  # or use your preferred editor
   ```

3. **Required configurations (minimum to start):**
   - `SECRET_KEY`: Generate using `openssl rand -hex 32`
   - `LLM_PROVIDER`: Choose `ollama` (free, local) or `openai` (cloud, requires API key)
   - `POSTGRES_PASSWORD`: Change from default for production
   - `REDIS_PASSWORD`: Change from default for production
   - `MINIO_ROOT_PASSWORD`: Change from default for production

   **For Ollama (Recommended - No API Key Required):**
   - Set `LLM_PROVIDER=ollama` in `.env`
   - See [OLLAMA_SETUP.md](OLLAMA_SETUP.md) for detailed setup instructions
   - Run `./scripts/setup-ollama.sh` to download required models

   **For OpenAI:**
   - Set `LLM_PROVIDER=openai` in `.env`
   - `OPENAI_API_KEY`: Get from [OpenAI Platform](https://platform.openai.com/api-keys)

4. **Optional configurations (for full functionality):**
   - **Confluence Integration:**
     - `CONFLUENCE_URL`: Your Confluence instance URL
     - `CONFLUENCE_USERNAME`: Your Confluence email
     - `CONFLUENCE_API_TOKEN`: Generate at [Atlassian API Tokens](https://id.atlassian.com/manage/api-tokens)
     - `CONFLUENCE_SPACE_KEY`: Space key to index (e.g., "DOCS")

   - **Jira Integration:**
     - `JIRA_URL`: Your Jira instance URL
     - `JIRA_USERNAME`: Your Jira email
     - `JIRA_API_TOKEN`: Generate at [Atlassian API Tokens](https://id.atlassian.com/manage/api-tokens)
     - `JIRA_PROJECT_KEY`: Project key to index (e.g., "PROJ")

5. **Security best practices:**
   - **Never commit `.env` file to version control** (already in `.gitignore`)
   - Use strong, unique passwords for all services
   - Rotate credentials regularly in production
   - Use different credentials for development, staging, and production
   - Store production secrets in a secure secret manager (e.g., AWS Secrets Manager, HashiCorp Vault)

6. **Verify your configuration:**
   ```bash
   # Check if .env file exists and is readable
   cat .env | grep -v "^#" | grep -v "^$" | head -5

   # Validate required variables are set (example)
   grep "SECRET_KEY" .env
   grep "OPENAI_API_KEY" .env
   ```

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
