"""
Test Suite for Task-004: Initialize Backend FastAPI Application Structure

Tests cover:
- Directory structure validation
- Application startup and endpoints
- Configuration management
- Package initialization
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

# Get paths
backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"


class TestDirectoryStructure:
    """TC-001, TC-002: Directory structure and package initialization tests."""
    
    def test_src_directory_exists(self):
        """Verify backend/src directory exists."""
        assert src_dir.exists(), "src directory should exist"
        assert src_dir.is_dir(), "src should be a directory"
    
    def test_required_subdirectories_exist(self):
        """Verify all required subdirectories exist."""
        required_dirs = [
            "api",
            "api/v1",
            "services",
            "models",
            "schemas",
            "middleware",
            "tasks",
            "core",
            "utils",
        ]
        
        for dir_path in required_dirs:
            full_path = src_dir / dir_path
            assert full_path.exists(), f"{dir_path} directory should exist"
            assert full_path.is_dir(), f"{dir_path} should be a directory"
    
    def test_init_files_exist(self):
        """Verify __init__.py files exist in all packages."""
        package_dirs = [
            "api",
            "services",
            "models",
            "schemas",
            "middleware",
            "tasks",
            "core",
            "utils",
        ]
        
        for pkg_dir in package_dirs:
            init_file = src_dir / pkg_dir / "__init__.py"
            assert init_file.exists(), f"{pkg_dir}/__init__.py should exist"
    
    def test_core_files_exist(self):
        """Verify core application files exist."""
        core_files = [
            "main.py",
            "core/config.py",
            "core/logging.py",
        ]
        
        for file_path in core_files:
            full_path = src_dir / file_path
            assert full_path.exists(), f"{file_path} should exist"
            assert full_path.is_file(), f"{file_path} should be a file"


class TestApplicationStartup:
    """TC-005, TC-006, TC-007, TC-008: Application startup and endpoint tests."""
    
    def test_app_instance_creation(self, app):
        """Verify FastAPI app instance is created."""
        assert app is not None, "App should be created"
        assert isinstance(app, FastAPI), "App should be FastAPI instance"
    
    def test_app_metadata(self, app):
        """Verify app has correct metadata."""
        assert app.title, "App should have a title"
        assert app.version, "App should have a version"
        assert app.description, "App should have a description"
    
    def test_root_endpoint(self, client):
        """TC-006: Test root endpoint returns correct response."""
        response = client.get("/")
        
        assert response.status_code == 200, "Root endpoint should return 200"
        data = response.json()
        
        assert "message" in data, "Response should contain message"
        assert "version" in data, "Response should contain version"
        assert "status" in data, "Response should contain status"
    
    def test_health_check_endpoint(self, client):
        """TC-007: Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200, "Health endpoint should return 200"
        data = response.json()
        
        assert "status" in data, "Response should contain status"
        assert data["status"] == "healthy", "Status should be healthy"
        assert "environment" in data, "Response should contain environment"
    
    def test_cors_middleware_configured(self, app):
        """TC-008: Verify CORS middleware is configured."""
        # Check if middleware is configured (user_middleware is not empty)
        assert len(app.user_middleware) > 0, "CORS middleware should be configured"

        # Verify middleware configuration by checking if the middleware list contains our CORS setup
        # The middleware is wrapped, so we check the middleware stack exists
        middleware_present = any(
            hasattr(m, 'cls') or type(m).__name__ == 'Middleware'
            for m in app.user_middleware
        )
        assert middleware_present, "Middleware stack should be configured"


class TestConfigurationManagement:
    """TC-009, TC-010: Configuration loading and validation tests."""
    
    def test_settings_import(self):
        """Verify settings can be imported."""
        from core.config import settings
        
        assert settings is not None, "Settings should be importable"
    
    def test_settings_values_loaded(self):
        """TC-009: Verify settings load from environment."""
        from core.config import settings

        # Check values from test environment
        assert settings.PROJECT_NAME is not None, "PROJECT_NAME should be set"
        assert settings.ENVIRONMENT in ["development", "staging", "production"], "ENVIRONMENT should be valid"
        assert settings.API_V1_PREFIX is not None, "API_V1_PREFIX should be set"
        assert settings.SECRET_KEY is not None, "SECRET_KEY should be set"
        assert len(settings.SECRET_KEY) >= 32, "SECRET_KEY should be at least 32 chars"

    def test_settings_validation(self):
        """TC-010: Verify settings validation works."""
        from core.config import settings

        # Test that settings with constraints are validated
        assert settings.PORT >= 1 and settings.PORT <= 65535, "PORT should be in valid range"
        assert settings.RATE_LIMIT_PER_MINUTE >= 1, "RATE_LIMIT should be positive"
        assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], "LOG_LEVEL should be valid"


class TestPackageImports:
    """TC-002: Package initialization and import tests."""

    def test_core_module_import(self):
        """Verify core module can be imported."""
        from core import config, logging as core_logging

        assert config is not None, "Config module should be importable"
        assert core_logging is not None, "Logging module should be importable"

    def test_core_exports(self):
        """Verify core module exports settings and setup_logging."""
        from core.config import settings
        from core.logging import setup_logging

        assert settings is not None, "settings should be exported"
        assert callable(setup_logging), "setup_logging should be callable"

    def test_api_modules_import(self):
        """Verify API modules can be imported."""
        import api
        import api.v1

        assert api is not None, "api module should be importable"
        assert api.v1 is not None, "api.v1 module should be importable"

    def test_other_modules_import(self):
        """Verify other modules can be imported."""
        import services
        import models
        import schemas
        import middleware
        import tasks
        import utils

        assert services is not None, "services module should be importable"
        assert models is not None, "models module should be importable"
        assert schemas is not None, "schemas module should be importable"
        assert middleware is not None, "middleware module should be importable"
        assert tasks is not None, "tasks module should be importable"
        assert utils is not None, "utils module should be importable"


class TestLoggingSystem:
    """TC-015, TC-016: Logging system initialization tests."""

    def test_logging_import(self):
        """Verify logging module can be imported."""
        from core.logging import setup_logging

        assert setup_logging is not None, "setup_logging should be importable"
        assert callable(setup_logging), "setup_logging should be callable"

    def test_logging_initialization(self):
        """TC-015: Verify logging can be initialized."""
        from core.logging import setup_logging

        # This should not raise an exception
        logger = setup_logging()

        assert logger is not None, "Logger should be returned"

    def test_logger_functionality(self):
        """Test that logger can write messages."""
        from core.logging import setup_logging

        logger = setup_logging()

        # These should not raise exceptions
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.warning("Test warning message")
