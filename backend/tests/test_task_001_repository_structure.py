"""
Test Suite for Task-001: Initialize Project Repository and Git Structure

This test suite validates:
- Git repository initialization and branching strategy
- Directory structure (backend, frontend, infrastructure, etc.)
- Configuration files (.gitignore, README.md, Docker files, etc.)
- Essential setup scripts and documentation
"""

import pytest
from pathlib import Path
import subprocess
import re

# Project root is one level up from backend
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestGitRepository:
    """TC-001 to TC-003: Git repository validation"""
    
    def test_git_initialized(self):
        """TC-001: Verify Git repository exists"""
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Git repository not initialized"
        assert ".git" in result.stdout, ".git directory not found"
    
    def test_branches_exist(self):
        """TC-002: Verify main, staging, develop branches exist"""
        result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Failed to list git branches"
        branches_output = result.stdout
        
        # Check for main, staging, develop branches
        assert "main" in branches_output, "Branch 'main' not found"
        assert "staging" in branches_output, "Branch 'staging' not found"
        assert "develop" in branches_output, "Branch 'develop' not found"
    
    def test_initial_commit_exists(self):
        """TC-003: Verify at least one commit exists"""
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Failed to get git log"
        assert len(result.stdout.strip()) > 0, "No commits found in repository"


class TestDirectoryStructure:
    """TC-004 to TC-006: Directory structure validation"""
    
    def test_top_level_directories(self):
        """TC-004: Verify top-level directories exist"""
        required_dirs = ["backend", "frontend", "infrastructure", "docs", "scripts", "config"]
        
        for dir_name in required_dirs:
            dir_path = PROJECT_ROOT / dir_name
            assert dir_path.exists(), f"Directory '{dir_name}' does not exist"
            assert dir_path.is_dir(), f"'{dir_name}' is not a directory"
    
    def test_backend_structure(self):
        """TC-005: Verify backend subdirectory structure"""
        backend_dir = PROJECT_ROOT / "backend"
        required_subdirs = ["app", "tests", "alembic"]
        
        for subdir in required_subdirs:
            subdir_path = backend_dir / subdir
            assert subdir_path.exists(), f"Backend subdirectory '{subdir}' does not exist"
            assert subdir_path.is_dir(), f"Backend '{subdir}' is not a directory"
        
        # Check for Python package marker
        init_file = backend_dir / "app" / "__init__.py"
        assert init_file.exists(), "Backend app/__init__.py does not exist"
    
    def test_frontend_structure(self):
        """TC-006: Verify frontend subdirectory structure"""
        frontend_dir = PROJECT_ROOT / "frontend"
        required_subdirs = ["src", "public"]

        for subdir in required_subdirs:
            subdir_path = frontend_dir / subdir
            assert subdir_path.exists(), f"Frontend subdirectory '{subdir}' does not exist"
            assert subdir_path.is_dir(), f"Frontend '{subdir}' is not a directory"

        # Check for essential React files (support both TypeScript and JavaScript)
        app_tsx = frontend_dir / "src" / "App.tsx"
        app_jsx = frontend_dir / "src" / "App.jsx"
        main_tsx = frontend_dir / "src" / "main.tsx"
        main_jsx = frontend_dir / "src" / "main.jsx"

        assert app_tsx.exists() or app_jsx.exists(), "Frontend src/App.tsx or App.jsx does not exist"
        assert main_tsx.exists() or main_jsx.exists(), "Frontend src/main.tsx or main.jsx does not exist"


class TestGitignore:
    """TC-007 to TC-010: .gitignore configuration validation"""
    
    @pytest.fixture
    def gitignore_content(self):
        """Read .gitignore file content"""
        gitignore_path = PROJECT_ROOT / ".gitignore"
        assert gitignore_path.exists(), ".gitignore file does not exist"
        return gitignore_path.read_text()
    
    def test_gitignore_python_patterns(self, gitignore_content):
        """TC-007: Verify .gitignore contains Python patterns"""
        required_patterns = ["__pycache__", "*.py[cod]", "venv"]
        
        for pattern in required_patterns:
            assert pattern in gitignore_content, f"Python pattern '{pattern}' not found in .gitignore"
    
    def test_nodejs_patterns(self, gitignore_content):
        """TC-008: Verify .gitignore contains Node.js patterns"""
        required_patterns = ["node_modules", "*.log", "dist"]
        
        for pattern in required_patterns:
            assert pattern in gitignore_content, f"Node.js pattern '{pattern}' not found in .gitignore"
    
    def test_docker_patterns(self, gitignore_content):
        """TC-009: Verify .gitignore contains Docker patterns"""
        required_patterns = ["volumes/", "docker-compose.override.yml"]
        
        for pattern in required_patterns:
            assert pattern in gitignore_content, f"Docker pattern '{pattern}' not found in .gitignore"
    
    def test_env_patterns(self, gitignore_content):
        """TC-010: Verify .gitignore contains environment file patterns"""
        assert ".env" in gitignore_content, "Environment pattern '.env' not found in .gitignore"


class TestDocumentation:
    """TC-011: README.md validation"""

    def test_readme_exists_and_content(self):
        """TC-011: Verify README.md exists and contains required sections"""
        readme_path = PROJECT_ROOT / "README.md"
        assert readme_path.exists(), "README.md does not exist"

        content = readme_path.read_text()
        assert len(content) > 0, "README.md is empty"

        # Check for required sections
        content_lower = content.lower()
        assert "project structure" in content_lower or "structure" in content_lower, \
            "README.md missing 'Project Structure' section"

        # Check for tech stack mentions
        tech_stack = ["fastapi", "react", "postgresql", "redis"]
        found_tech = [tech for tech in tech_stack if tech in content_lower]
        assert len(found_tech) >= 2, \
            f"README.md should mention tech stack (found: {found_tech})"

        # Check for installation or quick start
        assert "installation" in content_lower or "quick start" in content_lower or "getting started" in content_lower, \
            "README.md missing installation/quick start section"


class TestConfigFiles:
    """TC-012 to TC-016: Configuration files validation"""

    def test_essential_config_files(self):
        """TC-012: Verify essential configuration files exist"""
        required_files = [
            ".env.example",
            ".editorconfig",
            "backend/requirements.txt",
            "backend/pytest.ini",
            "backend/alembic.ini",
            "frontend/package.json"
        ]

        for file_path in required_files:
            full_path = PROJECT_ROOT / file_path
            assert full_path.exists(), f"Configuration file '{file_path}' does not exist"
            assert full_path.is_file(), f"'{file_path}' is not a file"
            # Verify non-empty
            assert full_path.stat().st_size > 0, f"Configuration file '{file_path}' is empty"

        # Check for Vite config (support both TypeScript and JavaScript)
        vite_ts = PROJECT_ROOT / "frontend" / "vite.config.ts"
        vite_js = PROJECT_ROOT / "frontend" / "vite.config.js"
        assert vite_ts.exists() or vite_js.exists(), "Frontend vite.config.ts or vite.config.js does not exist"

    def test_dockerfiles(self):
        """TC-013: Verify Dockerfile exists for backend and frontend"""
        dockerfiles = [
            "backend/Dockerfile",
            "frontend/Dockerfile"
        ]

        for dockerfile in dockerfiles:
            full_path = PROJECT_ROOT / dockerfile
            assert full_path.exists(), f"Dockerfile '{dockerfile}' does not exist"
            assert full_path.is_file(), f"'{dockerfile}' is not a file"
            assert full_path.stat().st_size > 0, f"Dockerfile '{dockerfile}' is empty"

    def test_docker_compose(self):
        """TC-014: Verify docker-compose.yml exists"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml does not exist"
        assert compose_file.is_file(), "docker-compose.yml is not a file"
        assert compose_file.stat().st_size > 0, "docker-compose.yml is empty"

    def test_setup_scripts(self):
        """TC-015: Verify setup scripts exist"""
        required_scripts = [
            "scripts/setup_backend.sh",
            "scripts/setup_frontend.sh",
            "scripts/start_dev.sh"
        ]

        for script_path in required_scripts:
            full_path = PROJECT_ROOT / script_path
            assert full_path.exists(), f"Setup script '{script_path}' does not exist"
            assert full_path.is_file(), f"'{script_path}' is not a file"
            assert full_path.stat().st_size > 0, f"Setup script '{script_path}' is empty"

    def test_infrastructure_docs(self):
        """TC-016: Verify infrastructure directory documentation"""
        infra_readme = PROJECT_ROOT / "infrastructure" / "README.md"
        assert infra_readme.exists(), "infrastructure/README.md does not exist"
        assert infra_readme.is_file(), "infrastructure/README.md is not a file"
        assert infra_readme.stat().st_size > 0, "infrastructure/README.md is empty"
