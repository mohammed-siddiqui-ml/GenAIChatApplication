# GenAI Chat Application - Complete Components List

## Frontend Components

1. **React** - JavaScript UI framework for building the chat interface
2. **Socket.IO Client** - WebSocket library for real-time chat communication
3. **Axios/Fetch** - HTTP client for REST API calls
4. **React Router** - Client-side routing for navigation

---

## Backend - API Layer

5. **FastAPI** - Modern Python web framework for building REST APIs
6. **Uvicorn** - ASGI server for running FastAPI applications
7. **Pydantic** - Data validation and settings management
8. **Python-JOSE** - JWT token creation and validation
9. **Passlib** - Password hashing library (bcrypt implementation)
10. **Python-SocketIO** - WebSocket server implementation
11. **Python-Multipart** - File upload handling
12. **CORS Middleware** - Cross-origin resource sharing for frontend access

---

## Database & Storage

13. **PostgreSQL** - Primary relational database for structured data
14. **pgvector** - PostgreSQL extension for vector similarity search
15. **SQLAlchemy** - Python ORM for database operations
16. **Alembic** - Database migration tool
17. **MinIO** - S3-compatible object storage for files
18. **Redis** - In-memory data store for task queue and caching

---

## RAG (Retrieval-Augmented Generation)

19. **RAG Service** - Core service orchestrating query-to-answer flow
20. **Embedding Generator** - Converts text to 768-dimensional vectors
21. **Vector Search** - Cosine similarity search using pgvector
22. **Context Retriever** - Fetches relevant document chunks
23. **LLM Generator** - Generates natural language answers from context

---

## LLM & AI Models

24. **Ollama** - Local LLM serving platform
25. **llama2** - Open-source language model for chat completion
26. **nomic-embed-text** - 768-dimension embedding model
27. **OpenAI Whisper** - Speech-to-text transcription model
28. **LLM Factory** - Abstraction layer for switching LLM providers
29. **OpenAI Client** - Cloud LLM provider (GPT-3.5/GPT-4) fallback

---

## Document Ingestion

30. **Folder Watcher Service** - Monitors watch_folder/ for new files
31. **Watchdog** - Python library for filesystem event monitoring
32. **PDF Processor** - Extracts text from PDF documents
33. **PyPDF2** - Python library for PDF parsing
34. **Video Processor** - Converts video to searchable text
35. **Confluence Connector** - Fetches and syncs Confluence pages
36. **Jira Connector** - Fetches and syncs Jira issues/comments

---

## Video Processing Pipeline

37. **FFmpeg** - Multimedia framework for audio extraction from video
38. **OpenAI Whisper** - Converts speech audio to timestamped text
39. **Text Chunker** - Splits transcripts into 500-token chunks with overlap
40. **Timestamp Tracker** - Preserves video timestamps for citations

---

## Background Task Processing

41. **Celery** - Distributed task queue for async processing
42. **Celery Worker** - Process that executes background tasks
43. **Celery Beat** - Scheduler for periodic tasks
44. **Redis Broker** - Message broker for Celery task distribution
45. **Kombu** - Messaging library used by Celery

---

## Authentication & Security

46. **JWT (JSON Web Tokens)** - Stateless authentication mechanism
47. **Bcrypt** - Password hashing algorithm
48. **RBAC System** - Role-based access control (Admin/User)
49. **Audit Logger** - Tracks admin actions for compliance
50. **Password Validator** - Enforces password complexity rules

---

## Data Models (PostgreSQL Tables)

51. **users** - Stores user accounts and credentials
52. **knowledge_documents** - Stores ingested document content
53. **document_embeddings** - Stores 768d vectors for similarity search
54. **chat_sessions** - Stores user conversation threads
55. **chat_messages** - Stores individual messages in conversations
56. **data_sources** - Registry of ingestion sources (Confluence, Jira, folder)
57. **ingestion_jobs** - Tracks status of ingestion tasks
58. **audit_logs** - Records admin actions for security tracking

---

## Monitoring & Observability

59. **Prometheus** - Metrics collection and monitoring system
60. **Loki** - Log aggregation system
61. **Promtail** - Log shipping agent that sends logs to Loki
62. **Grafana** - Visualization dashboards (optional, for metrics/logs)
63. **Python Logging** - Built-in logging framework

---

## Infrastructure & DevOps

64. **Docker** - Containerization platform
65. **Docker Compose** - Multi-container orchestration
66. **Nginx** - Reverse proxy and load balancer (optional)
67. **Git** - Version control system
68. **GitHub** - Code repository hosting

---

## Python Libraries (Additional)

69. **Requests** - HTTP library for external API calls
70. **Python-dotenv** - Environment variable management
71. **Tiktoken** - Token counting for OpenAI models
72. **NumPy** - Numerical computing for vector operations
73. **PyTorch** - Deep learning framework (required by Whisper)
74. **Numba** - JIT compiler for Python (Whisper dependency)
75. **Typing-Extensions** - Type hints for Python
76. **Asyncio** - Asynchronous I/O support
77. **Aiofiles** - Async file operations

---

## Testing & Development

78. **Pytest** - Python testing framework
79. **HTTPx** - Async HTTP client for testing
80. **Factory Boy** - Test data generation
81. **Black** - Python code formatter
82. **Flake8** - Python linter for code quality
83. **MyPy** - Static type checker for Python

---

## Utilities & Helpers

84. **UUID** - Unique identifier generation
85. **Hashlib** - Hashing utilities
86. **JSON** - Data serialization
87. **DateTime** - Date and time handling
88. **OS/Path** - File system operations
89. **Tempfile** - Temporary file management
90. **Subprocess** - Execute shell commands (FFmpeg)

---

## Configuration Management

91. **Pydantic Settings** - Environment-based configuration
92. **Config.py** - Centralized configuration file
93. **Environment Variables** - Deployment-specific settings
94. **docker-compose.yml** - Service configuration and orchestration

---

## Network & Communication

95. **HTTP/HTTPS** - Standard web protocols
96. **WebSocket** - Bidirectional real-time communication
97. **REST API** - Standard API architecture pattern
98. **JSON API** - Data exchange format

---

## File Format Support

99. **PDF** - Portable Document Format support
100. **MP4/AVI/MOV/MKV/WEBM** - Video format support
101. **WAV** - Audio format for Whisper processing
102. **Markdown** - Documentation format

---

## Summary by Category

| Category | Component Count |
|----------|----------------|
| Frontend | 4 |
| Backend API | 8 |
| Database & Storage | 6 |
| RAG Engine | 5 |
| LLM & AI | 6 |
| Document Ingestion | 7 |
| Video Processing | 4 |
| Background Tasks | 5 |
| Authentication | 5 |
| Data Models | 8 |
| Monitoring | 5 |
| Infrastructure | 5 |
| Python Libraries | 9 |
| Testing | 6 |
| Utilities | 7 |
| Configuration | 4 |
| Network | 4 |
| File Formats | 4 |
| **TOTAL** | **102 Components** |
