"""
Unit tests for DataSourceService (Admin Service).

Tests data source management including CRUD operations,
configuration validation, and encryption.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.admin_service import DataSourceService, DataSourceError
from models.data_source import DataSource, DataSourceType
from utils.crypto import decrypt_config_dict


@pytest.mark.unit
@pytest.mark.asyncio
class TestDataSourceService:
    """Unit tests for DataSourceService."""
    
    async def test_create_confluence_source(self, session):
        """Test creating a Confluence data source."""
        service = DataSourceService(session)
        
        config = {
            "url": "https://confluence.example.com",
            "username": "test_user",
            "api_token": "secret_token_123",
            "space_key": "PROJ"
        }
        
        data_source = await service.create_data_source(
            name="Test Confluence",
            source_type=DataSourceType.CONFLUENCE,
            config=config,
            sync_schedule="0 0 * * *"
        )
        
        assert data_source is not None
        assert data_source.name == "Test Confluence"
        assert data_source.type == DataSourceType.CONFLUENCE
        assert data_source.is_active is True

        # Verify configuration is encrypted
        sensitive_fields = ["api_token", "password", "api_key"]
        decrypted_config = decrypt_config_dict(data_source.source_config, sensitive_fields)
        assert decrypted_config["url"] == config["url"]
        assert decrypted_config["api_token"] == config["api_token"]
    
    async def test_create_jira_source(self, session):
        """Test creating a JIRA data source."""
        service = DataSourceService(session)
        
        config = {
            "url": "https://jira.example.com",
            "username": "jira_user",
            "api_token": "jira_secret_456",
            "project_key": "PROJ"
        }
        
        data_source = await service.create_data_source(
            name="Test JIRA",
            source_type=DataSourceType.JIRA,
            config=config,
            sync_schedule="0 */6 * * *"
        )
        
        assert data_source is not None
        assert data_source.name == "Test JIRA"
        assert data_source.type == DataSourceType.JIRA
    
    async def test_create_source_validation_error(self, session):
        """Test data source creation with invalid configuration."""
        service = DataSourceService(session)
        
        # Missing required fields
        invalid_config = {
            "url": "https://confluence.example.com"
            # Missing username, api_token, space_key
        }
        
        with pytest.raises(DataSourceError) as exc_info:
            await service.create_data_source(
                name="Invalid Source",
                source_type=DataSourceType.CONFLUENCE,
                config=invalid_config,
                sync_schedule="0 0 * * *"
            )
        
        assert "Missing required" in str(exc_info.value) or "Invalid" in str(exc_info.value)
    
    async def test_get_data_source(self, session, confluence_data_source):
        """Test retrieving a data source by ID."""
        service = DataSourceService(session)
        
        data_source = await service.get_data_source(confluence_data_source.id)
        
        assert data_source is not None
        assert data_source.id == confluence_data_source.id
        assert data_source.name == confluence_data_source.name
    
    async def test_get_data_source_not_found(self, session):
        """Test retrieving non-existent data source returns None."""
        service = DataSourceService(session)

        # get_data_source returns None, not raises exception
        result = await service.get_data_source(99999)

        assert result is None

    async def test_list_data_sources(self, session, confluence_data_source, jira_data_source):
        """Test listing all data sources."""
        service = DataSourceService(session)

        # list_data_sources returns tuple of (sources, total_count)
        sources, total = await service.list_data_sources()

        assert len(sources) >= 2
        assert total >= 2
        source_names = [s.name for s in sources]
        assert "Test Confluence" in source_names
        assert "Test JIRA" in source_names
    
    async def test_update_data_source(self, session, confluence_data_source):
        """Test updating a data source."""
        service = DataSourceService(session)

        new_config = {
            "url": "https://new-confluence.example.com",
            "username": "new_user",
            "api_token": "new_token",
            "space_key": "NEW"
        }

        updated = await service.update_data_source(
            data_source_id=confluence_data_source.id,
            name="Updated Confluence",
            config=new_config,
            sync_schedule="0 12 * * *"
        )

        assert updated.name == "Updated Confluence"

        # Use source_config attribute, not config
        sensitive_fields = ['api_token', 'password', 'api_key']
        decrypted_config = decrypt_config_dict(updated.source_config, sensitive_fields)
        assert decrypted_config["url"] == "https://new-confluence.example.com"
    
    async def test_delete_data_source(self, session, confluence_data_source):
        """Test deleting a data source."""
        service = DataSourceService(session)

        result = await service.delete_data_source(confluence_data_source.id)

        assert result is True

        # Verify it's deleted - get_data_source returns None, not raising exception
        deleted_source = await service.get_data_source(confluence_data_source.id)
        assert deleted_source is None
    
    async def test_toggle_data_source_status(self, session, confluence_data_source):
        """Test enabling/disabling a data source using update_data_source."""
        service = DataSourceService(session)

        # Disable using update_data_source
        disabled = await service.update_data_source(
            confluence_data_source.id,
            is_active=False
        )
        assert disabled.is_active is False

        # Enable using update_data_source
        enabled = await service.update_data_source(
            confluence_data_source.id,
            is_active=True
        )
        assert enabled.is_active is True

    async def test_validate_cron_expression(self, session):
        """Test cron expression validation via validate_config."""
        from utils.validators import validate_cron_expression

        # Valid cron expressions
        assert validate_cron_expression("0 0 * * *") is True  # Daily at midnight
        assert validate_cron_expression("0 */6 * * *") is True  # Every 6 hours

        # Invalid cron expression
        assert validate_cron_expression("invalid cron") is False
