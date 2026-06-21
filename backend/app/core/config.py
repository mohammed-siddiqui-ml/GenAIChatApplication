"""
Application configuration using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "GenAI Knowledge Retrieval System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS - Allow frontend from any origin in development
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]

    # LLM Provider
    LLM_PROVIDER: str = "ollama"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7

    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_CHAT_MODEL: str = "llama2"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_TEMPERATURE: float = 0.7
    OLLAMA_MAX_TOKENS: int = 500
    OLLAMA_EMBEDDING_DIMENSION: int = 768
    
    # Vector Store
    VECTOR_STORE_TYPE: str = "chromadb"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    COLLECTION_NAME: str = "knowledge_base"
    
    # Confluence
    CONFLUENCE_URL: str = ""
    CONFLUENCE_USERNAME: str = ""
    CONFLUENCE_API_TOKEN: str = ""
    CONFLUENCE_SPACE_KEY: str = ""
    
    # Jira
    JIRA_URL: str = ""
    JIRA_USERNAME: str = ""
    JIRA_API_TOKEN: str = ""
    JIRA_PROJECT_KEY: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Data Refresh
    DATA_REFRESH_INTERVAL_HOURS: int = 24
    AUTO_REFRESH_ENABLED: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Performance
    RESPONSE_TIMEOUT_SECONDS: int = 3
    MAX_CONCURRENT_REQUESTS: int = 100

    # Folder Watch (for stage/internal testing only)
    FOLDER_WATCH_ENABLED: bool = False
    FOLDER_WATCH_PATH: str = "/app/watch_folder"
    FOLDER_WATCH_DATA_SOURCE_ID: int = 1

    # Video Processing (Whisper)
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    FFMPEG_PATH: str = "/usr/bin/ffmpeg"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
