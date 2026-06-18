"""
Test suite for Task 006: PostgreSQL Database Schema with Alembic
Tests the Alembic configuration and migration setup (file structure validation).
Database connection tests are skipped if PostgreSQL is not available.
"""
import pytest
from pathlib import Path


class TestAlembicConfiguration:
    """Test Alembic configuration files exist and are properly set up."""
    
    @pytest.fixture
    def backend_dir(self):
        """Get the backend directory path."""
        return Path(__file__).parent.parent
    
    def test_alembic_ini_exists(self, backend_dir):
        """Test that alembic.ini configuration file exists."""
        alembic_ini = backend_dir / "alembic.ini"
        assert alembic_ini.exists(), "alembic.ini configuration file does not exist"
        
        # Verify it contains required sections
        content = alembic_ini.read_text()
        assert "[alembic]" in content, "alembic.ini missing [alembic] section"
        assert "script_location" in content, "alembic.ini missing script_location"
        assert "sqlalchemy.url" in content, "alembic.ini missing sqlalchemy.url"
    
    def test_alembic_directory_exists(self, backend_dir):
        """Test that alembic/ directory exists."""
        alembic_dir = backend_dir / "alembic"
        assert alembic_dir.exists(), "alembic/ directory does not exist"
        assert alembic_dir.is_dir(), "alembic/ is not a directory"
    
    def test_alembic_env_py_exists(self, backend_dir):
        """Test that alembic/env.py exists and has correct configuration."""
        env_py = backend_dir / "alembic" / "env.py"
        assert env_py.exists(), "alembic/env.py does not exist"
        
        # Verify it contains async→sync URL conversion logic
        content = env_py.read_text()
        assert "replace" in content and ("asyncpg" in content or "postgresql+asyncpg" in content), \
            "alembic/env.py missing async→sync URL conversion logic"
        assert "DATABASE_URL" in content, "alembic/env.py not reading DATABASE_URL environment variable"
    
    def test_alembic_script_template_exists(self, backend_dir):
        """Test that script.py.mako template file exists."""
        template = backend_dir / "alembic" / "script.py.mako"
        assert template.exists(), "alembic/script.py.mako template does not exist"
    
    def test_alembic_versions_directory_exists(self, backend_dir):
        """Test that alembic/versions/ directory exists."""
        versions_dir = backend_dir / "alembic" / "versions"
        assert versions_dir.exists(), "alembic/versions/ directory does not exist"
        assert versions_dir.is_dir(), "alembic/versions/ is not a directory"


class TestInitialMigration:
    """Test that the initial migration file exists and has correct content."""
    
    @pytest.fixture
    def backend_dir(self):
        """Get the backend directory path."""
        return Path(__file__).parent.parent
    
    @pytest.fixture
    def migration_file(self, backend_dir):
        """Find the initial migration file."""
        versions_dir = backend_dir / "alembic" / "versions"
        migration_files = list(versions_dir.glob("001_*.py"))
        if not migration_files:
            migration_files = list(versions_dir.glob("*_initial_schema.py"))
        return migration_files[0] if migration_files else None
    
    def test_initial_migration_exists(self, backend_dir):
        """Test that the initial migration file exists."""
        versions_dir = backend_dir / "alembic" / "versions"
        migration_files = list(versions_dir.glob("001_*.py")) or list(versions_dir.glob("*_initial_schema.py"))
        assert len(migration_files) > 0, "Initial migration file (001_*.py or *_initial_schema.py) does not exist"
    
    def test_migration_has_upgrade_function(self, migration_file):
        """Test that migration file has upgrade() function."""
        assert migration_file is not None, "Migration file not found"
        content = migration_file.read_text()
        assert "def upgrade()" in content, "Migration file missing upgrade() function"
    
    def test_migration_has_downgrade_function(self, migration_file):
        """Test that migration file has downgrade() function."""
        assert migration_file is not None, "Migration file not found"
        content = migration_file.read_text()
        assert "def downgrade()" in content, "Migration file missing downgrade() function"
    
    def test_migration_creates_pgvector_extension(self, migration_file):
        """Test that migration enables pgvector extension."""
        assert migration_file is not None, "Migration file not found"
        content = migration_file.read_text()
        assert "vector" in content.lower() and "extension" in content.lower(), \
            "Migration file does not create pgvector extension"
    
    def test_migration_creates_all_tables(self, migration_file):
        """Test that migration creates all 8 required tables."""
        assert migration_file is not None, "Migration file not found"
        content = migration_file.read_text()
        
        required_tables = [
            "users",
            "chat_sessions",
            "chat_messages",
            "data_sources",
            "ingestion_jobs",
            "knowledge_documents",
            "document_embeddings",
            "audit_logs"
        ]
        
        for table in required_tables:
            assert table in content, f"Migration file does not create table '{table}'"
    
    def test_migration_creates_enum_types(self, migration_file):
        """Test that migration creates required ENUM types."""
        assert migration_file is not None, "Migration file not found"
        content = migration_file.read_text()
        
        required_enums = [
            "user_role",
            "message_role",
            "data_source_type",
            "content_type",
            "job_status"
        ]
        
        for enum_type in required_enums:
            assert enum_type in content, f"Migration file does not create ENUM type '{enum_type}'"


class TestTestingScripts:
    """Test that testing and verification scripts exist."""
    
    @pytest.fixture
    def backend_dir(self):
        """Get the backend directory path."""
        return Path(__file__).parent.parent
    
    def test_verify_schema_sql_exists(self, backend_dir):
        """Test that verify_schema.sql script exists."""
        verify_script = backend_dir / "alembic" / "verify_schema.sql"
        assert verify_script.exists(), "alembic/verify_schema.sql does not exist"
    
    def test_test_migration_script_exists(self, backend_dir):
        """Test that test_migration.sh script exists."""
        test_script = backend_dir / "test_migration.sh"
        assert test_script.exists(), "test_migration.sh does not exist"
