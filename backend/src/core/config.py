"""
Application Configuration

Centralized configuration management using Pydantic Settings.
Environment variables are loaded from .env file and validated.
"""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All sensitive configuration should be provided via environment variables
    and never hardcoded in the source code.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # Application Settings
    PROJECT_NAME: str = "GenAI Knowledge Retrieval System"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    API_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = Field(default=False)
    
    # Server Settings
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000, ge=1, le=65535)
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    
    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/knowledge_db"
    )
    DATABASE_POOL_SIZE: int = Field(default=20, ge=1)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0)
    
    # Redis Settings (for caching and session management)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, ge=1)
    
    # JWT Authentication Settings
    SECRET_KEY: str = Field(
        default="your-secret-key-change-this-in-production",
        min_length=32,
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, ge=1)  # 24 hours = 1440 minutes
    ACCESS_TOKEN_EXPIRE_HOURS: int = Field(default=24, ge=1)  # 24-hour expiry as per requirements
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)
    
    # GenAI Settings
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview")  # GPT-4 Turbo for chat completions
    OPENAI_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    OPENAI_MAX_TOKENS: int = Field(default=500, ge=1)

    # Embedding Settings
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")  # text-embedding-3-small (1536 dimensions)
    EMBEDDING_DIMENSION: int = Field(default=1536, ge=1)
    
    # Vector Database Settings (for semantic search)
    VECTOR_DB_URL: str = Field(default="http://localhost:6333")
    VECTOR_COLLECTION_NAME: str = Field(default="knowledge_base")
    
    # Confluence Integration Settings
    CONFLUENCE_URL: str = Field(default="")
    CONFLUENCE_USERNAME: str = Field(default="")
    CONFLUENCE_API_TOKEN: str = Field(default="")
    CONFLUENCE_SPACE_KEY: str = Field(default="")
    
    # Issue Tracking Integration Settings
    JIRA_URL: str = Field(default="")
    JIRA_USERNAME: str = Field(default="")
    JIRA_API_TOKEN: str = Field(default="")
    JIRA_PROJECT_KEY: str = Field(default="")
    
    # Data Ingestion Settings
    INGESTION_SCHEDULE_CRON: str = Field(default="0 2 * * *")  # Daily at 2 AM
    INGESTION_BATCH_SIZE: int = Field(default=100, ge=1)
    
    # Performance Settings
    MAX_RESPONSE_TIME_SECONDS: float = Field(default=3.0, ge=0.1)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1)
    
    # Logging Settings
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = "json"  # json or text
    
    # File Upload Settings
    MAX_UPLOAD_SIZE_MB: int = Field(default=10, ge=1)
    ALLOWED_FILE_TYPES: List[str] = Field(
        default=["pdf", "txt", "md", "docx", "csv"]
    )

    # MinIO Object Storage Settings
    MINIO_ENDPOINT: str = Field(default="minio:9000")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin")
    MINIO_SECRET_KEY: str = Field(default="minioadmin123")
    MINIO_USE_SSL: bool = Field(default=False)
    MINIO_BUCKET_NAME: str = Field(default="knowledge-assets")  # Legacy bucket

    # MinIO Bucket Names
    MINIO_BUCKET_KNOWLEDGE_FILES: str = Field(default="knowledge-files")
    MINIO_BUCKET_EMBEDDINGS_BACKUP: str = Field(default="embeddings-backup")
    MINIO_BUCKET_AUDIT_LOGS: str = Field(default="audit-logs")

    # Celery Settings (Background Task Queue)
    CELERY_BROKER_URL: str = Field(default="redis://:redispassword@redis:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://:redispassword@redis:6379/2")
    CELERY_TASK_ALWAYS_EAGER: bool = Field(default=False)  # Execute tasks synchronously in testing
    CELERY_TASK_EAGER_PROPAGATES: bool = Field(default=True)  # Propagate exceptions in eager mode

    # Sentry Error Tracking Settings
    SENTRY_DSN: str = Field(default="")  # Sentry Data Source Name
    SENTRY_ENVIRONMENT: str = Field(default="development")  # Sentry environment (development, staging, production)
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1, ge=0.0, le=1.0)  # 10% transaction sampling
    SENTRY_ENABLE_TRACING: bool = Field(default=True)  # Enable performance monitoring


# Global settings instance
settings = Settings()
