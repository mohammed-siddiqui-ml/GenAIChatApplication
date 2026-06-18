"""
Pytest configuration and fixtures for backend tests.

⚠️ CRITICAL: Set EMBEDDING_MODEL environment variable BEFORE any imports
to prevent SSL certificate errors during EmbeddingService module loading.
"""

import os

# CRITICAL: Set this BEFORE importing any app modules
os.environ['EMBEDDING_MODEL'] = 'openai'

import sys
from pathlib import Path

# Add src directory to Python path
backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def test_env_vars():
    """Set up test environment variables."""
    test_vars = {
        "PROJECT_NAME": "ChatApp Test",
        "ENVIRONMENT": "development",
        "API_V1_PREFIX": "/api/v1",
        "DEBUG": "true",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/chatapp_test",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-minimum-32-characters-long-for-jwt",
        "ALGORITHM": "HS256",
        "OPENAI_API_KEY": "sk-test-key-1234567890",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "text",
    }
    
    # Set environment variables
    for key, value in test_vars.items():
        os.environ[key] = value
    
    yield test_vars
    
    # Cleanup (optional - tests usually don't need cleanup for env vars)


@pytest.fixture(scope="module")
def app(test_env_vars):
    """Create FastAPI application instance for testing."""
    # Import after environment variables are set
    from main import app
    return app


@pytest.fixture(scope="module")
def client(app):
    """Create TestClient for making requests to the app."""
    return TestClient(app)
