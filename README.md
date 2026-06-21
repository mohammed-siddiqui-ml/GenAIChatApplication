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

***
### System Architecture
```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[React Frontend<br/>Port 3000]
        UI --> |WebSocket| WS[Socket.IO]
        UI --> |HTTP/REST| API
    end

    subgraph "API Gateway"
        API[FastAPI Backend<br/>Port 8000]
        API --> |Routes| AUTH[Auth Endpoints<br/>/api/v1/auth]
        API --> |Routes| CHAT[Chat Endpoints<br/>/api/v1/chat]
        API --> |Routes| ADMIN[Admin Endpoints<br/>/api/v1/admin]
        WS --> |Real-time| CHAT_WS[Chat WebSocket Handler]
    end

    subgraph "Authentication & Security"
        AUTH --> |JWT| JWT_SERVICE[JWT Token Service]
        AUTH --> |Bcrypt| HASH[Password Hashing]
        AUTH --> |Verify| USER_DB[(Users Table)]
        ADMIN --> |RBAC| AUDIT[(Audit Logs)]
    end

    subgraph "Core RAG Engine"
        CHAT --> RAG[RAG Service]
        CHAT_WS --> RAG
        RAG --> |1. Embed Query| EMB_GEN[Embedding Generator]
        RAG --> |2. Vector Search| VEC_SEARCH[pgvector Similarity]
        RAG --> |3. Generate Answer| LLM_GEN[LLM Generator]
        
        EMB_GEN --> LLM_FACTORY[LLM Factory]
        LLM_GEN --> LLM_FACTORY
    end

    subgraph "LLM Provider Abstraction"
        LLM_FACTORY --> |Provider Switch| OLLAMA[Ollama Client<br/>Local LLM]
        LLM_FACTORY --> |Fallback| OPENAI[OpenAI Client<br/>Cloud API]
        OLLAMA --> |Chat| LLAMA[llama2 Model]
        OLLAMA --> |Embeddings| NOMIC[nomic-embed-text<br/>768 dimensions]
    end

    subgraph "Document Ingestion Pipeline"
        FOLDER_WATCH[Folder Watcher Service<br/>watchdog] --> |Detect Files| WATCH_FOLDER[/watch_folder/]
        FOLDER_WATCH --> |Dispatch| CELERY_TASK[Celery Task Queue]
        
        CELERY_TASK --> |PDFs| PDF_PROC[PDF Processor<br/>PyPDF2]
        CELERY_TASK --> |Videos| VIDEO_PROC[Video Processor]
        CELERY_TASK --> |Confluence| CONF_PROC[Confluence Integration]
        CELERY_TASK --> |Jira| JIRA_PROC[Jira Integration]
        
        VIDEO_PROC --> |1. Extract| FFMPEG[FFmpeg<br/>Audio Extraction]
        VIDEO_PROC --> |2. Transcribe| WHISPER[OpenAI Whisper<br/>Speech-to-Text]
        VIDEO_PROC --> |3. Chunk| CHUNKER[Text Chunker<br/>500 tokens + timestamps]
        
        PDF_PROC --> CHUNKER
        CONF_PROC --> CHUNKER
        JIRA_PROC --> CHUNKER
        
        CHUNKER --> |4. Embed| EMB_BATCH[Batch Embedding<br/>via Ollama]
        EMB_BATCH --> |5. Store| DOC_DB[(Documents + Embeddings)]
    end

    subgraph "Storage Layer - PostgreSQL"
        USER_DB
        AUDIT
        DOC_DB
        CHAT_DB[(Chat Sessions<br/>& Messages)]
        DATA_SRC[(Data Sources)]
        JOBS[(Ingestion Jobs)]
        
        DOC_DB --> |pgvector| VEC_INDEX[Vector Index<br/>Cosine Similarity]
        VEC_SEARCH --> VEC_INDEX
    end

    subgraph "Object Storage - MinIO"
        MINIO[(MinIO<br/>Port 9000/9001)]
        VIDEO_PROC --> |Upload| MINIO
        PDF_PROC --> |Upload| MINIO
        MINIO --> |Retrieve| VIDEO_PROC
    end

    subgraph "Background Services"
        CELERY_WORKER[Celery Worker<br/>Task Processor]
        CELERY_BROKER[Redis<br/>Message Broker<br/>Port 6379]
        
        CELERY_TASK --> CELERY_BROKER
        CELERY_BROKER --> CELERY_WORKER
        CELERY_WORKER --> PDF_PROC
        CELERY_WORKER --> VIDEO_PROC
        CELERY_WORKER --> CONF_PROC
        CELERY_WORKER --> JIRA_PROC
    end

    subgraph "Monitoring & Observability"
        METRICS[Prometheus<br/>Metrics Collection]
        LOGS[Loki<br/>Log Aggregation]
        PROMTAIL[Promtail<br/>Log Shipper]
        
        API --> |Expose| METRICS
        CELERY_WORKER --> |Expose| METRICS
        API --> |Logs| PROMTAIL
        CELERY_WORKER --> |Logs| PROMTAIL
        PROMTAIL --> LOGS
    end

    subgraph "External Services"
        OLLAMA_SVC[Ollama Service<br/>Port 11434]
        OLLAMA --> |API Calls| OLLAMA_SVC
        OLLAMA_SVC --> |Models| LLAMA
        OLLAMA_SVC --> |Models| NOMIC
    end

    style UI fill:#e1f5ff
    style API fill:#fff3e0
    style RAG fill:#f3e5f5
    style LLM_FACTORY fill:#e8f5e9
    style OLLAMA_SVC fill:#e8f5e9
    style DOC_DB fill:#fce4ec
    style CELERY_WORKER fill:#fff9c4
    style MINIO fill:#e0f2f1
    style METRICS fill:#ede7f6

```
***
### Component Details & Purposes
```mermaid
graph LR
    subgraph "1. User Interface Layer"
        A1[React Frontend] --> A1P["Purpose: User interaction<br/>- Chat interface<br/>- Admin dashboard<br/>- Real-time updates via WebSocket"]
    end
    
    subgraph "2. API & Gateway"
        B1[FastAPI Backend] --> B1P["Purpose: API Gateway<br/>- Route HTTP requests<br/>- WebSocket management<br/>- Middleware & CORS<br/>- Request validation"]
    end
    
    subgraph "3. Authentication System"
        C1[JWT Service] --> C1P["Purpose: Stateless Auth<br/>- Generate access tokens<br/>- Token validation<br/>- Secure sessions"]
        C2[Bcrypt Hashing] --> C2P["Purpose: Password Security<br/>- Hash user passwords<br/>- Prevent plaintext storage<br/>- Rainbow table protection"]
        C3[RBAC] --> C3P["Purpose: Access Control<br/>- Admin vs User roles<br/>- Permission enforcement<br/>- Audit trail"]
    end
    
    subgraph "4. RAG Core Engine"
        D1[RAG Service] --> D1P["Purpose: Intelligent QA<br/>- Query understanding<br/>- Context retrieval<br/>- Answer generation<br/>- Citation management"]
        D2[Embedding Generator] --> D2P["Purpose: Query Vectorization<br/>- Convert text to 768d vectors<br/>- Enable semantic search<br/>- Match user intent"]
        D3[pgvector Search] --> D3P["Purpose: Similarity Ranking<br/>- Cosine similarity @ 0.6<br/>- Find relevant chunks<br/>- Return top-k results"]
        D4[LLM Generator] --> D4P["Purpose: Natural Answers<br/>- Generate human-like text<br/>- Stay grounded in context<br/>- Cite sources"]
    end
    
    subgraph "5. LLM Abstraction"
        E1[LLM Factory] --> E1P["Purpose: Provider Flexibility<br/>- Switch between Ollama/OpenAI<br/>- Abstract API differences<br/>- Enable local-first deployment"]
        E2[Ollama Client] --> E2P["Purpose: Local LLM Inference<br/>- No cloud dependency<br/>- Data privacy<br/>- Cost savings<br/>- llama2 + nomic-embed-text"]
        E3[OpenAI Client] --> E3P["Purpose: Cloud Fallback<br/>- Higher quality models<br/>- GPT-4 support<br/>- Production reliability"]
    end
    
    subgraph "6. Document Ingestion"
        F1[Folder Watcher] --> F1P["Purpose: Auto-Ingestion<br/>- Monitor watch_folder/<br/>- Detect new files<br/>- Trigger processing<br/>- Move to _processed/"]
        F2[PDF Processor] --> F2P["Purpose: Extract PDF Text<br/>- PyPDF2 parsing<br/>- Preserve structure<br/>- Handle multi-page docs"]
        F3[Video Processor] --> F3P["Purpose: Video-to-Text<br/>- FFmpeg audio extraction<br/>- Whisper transcription<br/>- Timestamp preservation<br/>- Video citations"]
        F4[Confluence] --> F4P["Purpose: Wiki Integration<br/>- Fetch spaces/pages<br/>- Sync knowledge base<br/>- Auto-update on changes"]
        F5[Jira] --> F5P["Purpose: Ticket Integration<br/>- Index issues/comments<br/>- Capture project context<br/>- Answer from tickets"]
    end
    
    subgraph "7. Processing Pipeline"
        G1[FFmpeg] --> G1P["Purpose: Audio Extraction<br/>- Convert video to 16kHz WAV<br/>- Prepare for Whisper<br/>- Handle all video formats"]
        G2[Whisper] --> G2P["Purpose: Speech-to-Text<br/>- Industry-standard accuracy<br/>- Multi-language support<br/>- Timestamped segments"]
        G3[Text Chunker] --> G3P["Purpose: Smart Chunking<br/>- 500 token chunks<br/>- 50 token overlap<br/>- Preserve context<br/>- Timestamp metadata"]
        G4[Batch Embedder] --> G4P["Purpose: Vectorization<br/>- Generate 768d vectors<br/>- Batch processing<br/>- Store in pgvector"]
    end
    
    subgraph "8. Storage - PostgreSQL"
        H1[knowledge_documents] --> H1P["Purpose: Document Storage<br/>- Full text content<br/>- Metadata fields<br/>- Video timestamps<br/>- Source tracking"]
        H2[document_embeddings] --> H2P["Purpose: Vector Storage<br/>- 768d vectors<br/>- Chunk text<br/>- Token counts<br/>- Similarity search index"]
        H3[users] --> H3P["Purpose: User Management<br/>- Credentials<br/>- Roles<br/>- Profile data"]
        H4[chat_sessions] --> H4P["Purpose: Conversation History<br/>- Track chat threads<br/>- Message storage<br/>- Context preservation"]
        H5[data_sources] --> H5P["Purpose: Source Registry<br/>- Track ingestion sources<br/>- Configuration<br/>- Status monitoring"]
        H6[ingestion_jobs] --> H6P["Purpose: Job Tracking<br/>- Processing status<br/>- Error logs<br/>- Retry logic"]
    end
    
    subgraph "9. Object Storage - MinIO"
        I1[MinIO] --> I1P["Purpose: File Storage<br/>- Store original files<br/>- S3-compatible API<br/>- Backup & retrieval<br/>- Scale storage separately"]
    end
    
    subgraph "10. Task Queue - Celery + Redis"
        J1[Redis] --> J1P["Purpose: Message Broker<br/>- Queue async tasks<br/>- Fast in-memory cache<br/>- Reliable message delivery"]
        J2[Celery Worker] --> J2P["Purpose: Background Processing<br/>- Offload heavy tasks<br/>- Parallel processing<br/>- Keep API responsive<br/>- Handle failures gracefully"]
    end
    
    subgraph "11. Monitoring & Observability"
        K1[Prometheus] --> K1P["Purpose: Metrics Collection<br/>- Track performance<br/>- Monitor resource usage<br/>- Alert on anomalies"]
        K2[Loki] --> K2P["Purpose: Log Aggregation<br/>- Centralized logs<br/>- Query across services<br/>- Debug production issues"]
        K3[Promtail] --> K3P["Purpose: Log Shipping<br/>- Collect container logs<br/>- Label & filter<br/>- Send to Loki"]
    end
    
    subgraph "12. External Services"
        L1[Ollama Service] --> L1P["Purpose: Model Serving<br/>- Host LLM models locally<br/>- REST API endpoint<br/>- Model management<br/>- GPU acceleration support"]
    end

    style A1P fill:#e1f5ff
    style B1P fill:#fff3e0
    style C1P fill:#fce4ec
    style C2P fill:#fce4ec
    style C3P fill:#fce4ec
    style D1P fill:#f3e5f5
    style D2P fill:#f3e5f5
    style D3P fill:#f3e5f5
    style D4P fill:#f3e5f5
    style E1P fill:#e8f5e9
    style E2P fill:#e8f5e9
    style E3P fill:#e8f5e9
    style F1P fill:#fff9c4
    style F2P fill:#fff9c4
    style F3P fill:#fff9c4
    style F4P fill:#fff9c4
    style F5P fill:#fff9c4
    style H1P fill:#ffebee
    style H2P fill:#ffebee
    style I1P fill:#e0f2f1
    style J1P fill:#fce4ec
    style J2P fill:#fce4ec
    style K1P fill:#ede7f6
    style L1P fill:#f1f8e9

```
