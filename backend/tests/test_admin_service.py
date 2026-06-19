"""
Tests for Admin Service - Data Source Management (Task-026)

This test module validates:
- Configuration validation for Confluence, JIRA, Onboarding sources
- CRUD operations (create, read, update, delete)
- Encryption/decryption of sensitive fields
- Cron expression validation
- Pagination and filtering
- Cascade delete operations
- Error handling
"""

import pytest
import pytest_asyncio
from sqlalchemy import select, func

from models.data_source import DataSource, DataSourceType
from models.knowledge import KnowledgeDocument
from models.user import User, UserRole
from services.admin_service import DataSourceService, DataSourceError
from core.security import hash_password


# ========== Test Data ==========

CONFLUENCE_CONFIG = {
    "url": "https://wiki.example.com",
    "username": "admin@example.com",
    "api_token": "confluence-token-12345",
    "space_key": "DOCS"
}

JIRA_CONFIG = {
    "url": "https://jira.example.com",
    "username": "admin@example.com",
    "api_token": "jira-token-67890",
    "project_key": "PROJ"
}

ONBOARDING_CONFIG = {
    "storage_path": "/data/onboarding",
    "api_token": "onboarding-token-11111"
}


# ========== Fixtures ==========

@pytest_asyncio.fixture
async def test_user(db_session):
    """Create test user for data source ownership."""
    user = User(
        email="testuser@example.com",
        password_hash=hash_password("Test123!@#"),
        role=UserRole.USER,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_service(db_session):
    """Create DataSourceService instance."""
    return DataSourceService(db_session)


# ========== Configuration Validation Tests ==========

@pytest.mark.asyncio
async def test_validate_confluence_config_valid(admin_service):
    """TC-C1: Validate valid Confluence configuration."""
    is_valid, error = admin_service.validate_config(DataSourceType.CONFLUENCE, CONFLUENCE_CONFIG)
    
    assert is_valid is True, "Valid Confluence config should pass validation"
    assert error is None, "No error should be returned for valid config"


@pytest.mark.asyncio
async def test_validate_jira_config_valid(admin_service):
    """TC-C2: Validate valid JIRA configuration."""
    is_valid, error = admin_service.validate_config(DataSourceType.JIRA, JIRA_CONFIG)
    
    assert is_valid is True, "Valid JIRA config should pass validation"
    assert error is None, "No error should be returned for valid config"


@pytest.mark.asyncio
async def test_validate_onboarding_config_valid(admin_service):
    """TC-C3: Validate valid Onboarding configuration."""
    is_valid, error = admin_service.validate_config(DataSourceType.ONBOARDING, ONBOARDING_CONFIG)
    
    assert is_valid is True, "Valid Onboarding config should pass validation"
    assert error is None, "No error should be returned for valid config"


@pytest.mark.asyncio
async def test_validate_confluence_config_missing_fields(admin_service):
    """TC-C4: Reject Confluence config with missing fields."""
    config = {
        "url": "https://wiki.example.com",
        "username": "admin@example.com",
        "space_key": "DOCS"
        # Missing api_token
    }
    
    is_valid, error = admin_service.validate_config(DataSourceType.CONFLUENCE, config)
    
    assert is_valid is False, "Config with missing api_token should fail"
    assert error is not None, "Error message should be provided"
    assert "api_token" in error.lower(), "Error should mention missing api_token"


@pytest.mark.asyncio
async def test_validate_jira_config_invalid_project_key(admin_service):
    """TC-C5: Reject JIRA config with invalid project_key format."""
    config = {
        "url": "https://jira.example.com",
        "username": "admin@example.com",
        "api_token": "token123",
        "project_key": "proj-123"  # Should be uppercase alphanumeric
    }
    
    is_valid, error = admin_service.validate_config(DataSourceType.JIRA, config)
    
    assert is_valid is False, "Config with invalid project_key should fail"
    assert error is not None, "Error message should be provided"
    assert "uppercase" in error.lower() or "alphanumeric" in error.lower(), "Error should mention format requirement"


@pytest.mark.asyncio
async def test_validate_config_invalid_url(admin_service):
    """TC-C6: Reject config with invalid URL."""
    config = {
        "url": "not-a-valid-url",
        "username": "admin@example.com",
        "api_token": "token123",
        "space_key": "DOCS"
    }
    
    is_valid, error = admin_service.validate_config(DataSourceType.CONFLUENCE, config)
    
    assert is_valid is False, "Config with invalid URL should fail"
    assert error is not None, "Error message should be provided"
    assert "url" in error.lower(), "Error should mention URL issue"


@pytest.mark.asyncio
async def test_validate_confluence_space_key_format(admin_service):
    """TC-C7: Validate space_key format for Confluence."""
    # Valid formats
    configs = [
        {"url": "https://wiki.com", "username": "user", "api_token": "token", "space_key": "DOCS"},
        {"url": "https://wiki.com", "username": "user", "api_token": "token", "space_key": "MY_SPACE"},
        {"url": "https://wiki.com", "username": "user", "api_token": "token", "space_key": "SPACE-123"},
    ]
    
    for config in configs:
        is_valid, error = admin_service.validate_config(DataSourceType.CONFLUENCE, config)
        assert is_valid is True, f"Valid space_key '{config['space_key']}' should pass"


# ========== CRUD Operations Tests ==========

@pytest.mark.asyncio
async def test_create_confluence_data_source(admin_service, test_user, db_session):
    """TC-D1: Create Confluence data source with valid config."""
    data_source = await admin_service.create_data_source(
        name="Company Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        sync_schedule="0 2 * * *",
        created_by=test_user.id
    )

    assert data_source.id is not None, "Data source should have an ID"
    assert data_source.name == "Company Wiki"
    assert data_source.type == DataSourceType.CONFLUENCE
    assert data_source.sync_schedule == "0 2 * * *"
    assert data_source.is_active is True
    assert data_source.created_by == test_user.id


@pytest.mark.asyncio
async def test_create_jira_data_source(admin_service, test_user):
    """TC-D2: Create JIRA data source with valid config."""
    data_source = await admin_service.create_data_source(
        name="JIRA Project",
        source_type=DataSourceType.JIRA,
        config=JIRA_CONFIG.copy(),
        sync_schedule="*/30 * * * *",
        created_by=test_user.id
    )

    assert data_source.id is not None
    assert data_source.name == "JIRA Project"
    assert data_source.type == DataSourceType.JIRA


@pytest.mark.asyncio
async def test_create_onboarding_data_source(admin_service, test_user):
    """TC-D3: Create Onboarding data source with valid config."""
    data_source = await admin_service.create_data_source(
        name="Employee Onboarding",
        source_type=DataSourceType.ONBOARDING,
        config=ONBOARDING_CONFIG.copy(),
        created_by=test_user.id
    )

    assert data_source.id is not None
    assert data_source.name == "Employee Onboarding"
    assert data_source.type == DataSourceType.ONBOARDING


@pytest.mark.asyncio
async def test_get_data_source_by_id(admin_service, test_user):
    """TC-D4: Retrieve data source by ID."""
    # Create data source
    created = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Retrieve it
    retrieved = await admin_service.get_data_source(created.id, decrypt_config=True)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "Test Wiki"


@pytest.mark.asyncio
async def test_update_data_source_name_and_config(admin_service, test_user):
    """TC-D5: Update data source name and config."""
    # Create data source
    data_source = await admin_service.create_data_source(
        name="Old Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Update
    new_config = {
        "url": "https://new-wiki.example.com",
        "username": "newadmin@example.com",
        "api_token": "new-token-67890",
        "space_key": "NEW"
    }

    updated = await admin_service.update_data_source(
        data_source.id,
        name="Updated Wiki",
        config=new_config
    )

    assert updated.name == "Updated Wiki"
    assert updated.source_config["url"] == "https://new-wiki.example.com"
    assert updated.source_config["username"] == "newadmin@example.com"
    assert updated.source_config["space_key"] == "NEW"


@pytest.mark.asyncio
async def test_update_sync_schedule(admin_service, test_user):
    """TC-D6: Update sync schedule with valid cron."""
    # Create data source
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        sync_schedule="0 2 * * *",
        created_by=test_user.id
    )

    # Update schedule
    updated = await admin_service.update_data_source(
        data_source.id,
        sync_schedule="*/30 * * * *"
    )

    assert updated.sync_schedule == "*/30 * * * *"


@pytest.mark.asyncio
async def test_update_is_active_status(admin_service, test_user):
    """TC-D7: Toggle is_active status."""
    # Create data source
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        is_active=True,
        created_by=test_user.id
    )

    assert data_source.is_active is True

    # Deactivate
    updated = await admin_service.update_data_source(
        data_source.id,
        is_active=False
    )

    assert updated.is_active is False


@pytest.mark.asyncio
async def test_delete_data_source(admin_service, test_user):
    """TC-D8: Delete data source."""
    # Create data source
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Delete
    success = await admin_service.delete_data_source(data_source.id)

    assert success is True

    # Verify it's deleted
    deleted = await admin_service.get_data_source(data_source.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_list_data_sources_with_pagination(admin_service, test_user):
    """TC-D9: List data sources with pagination."""
    # Create 15 data sources
    for i in range(15):
        await admin_service.create_data_source(
            name=f"Wiki {i+1}",
            source_type=DataSourceType.CONFLUENCE,
            config=CONFLUENCE_CONFIG.copy(),
            created_by=test_user.id
        )

    # Get first page
    sources_page1, total1 = await admin_service.list_data_sources(limit=10, offset=0)
    assert len(sources_page1) == 10
    assert total1 == 15

    # Get second page
    sources_page2, total2 = await admin_service.list_data_sources(limit=10, offset=10)
    assert len(sources_page2) == 5
    assert total2 == 15


@pytest.mark.asyncio
async def test_filter_data_sources_by_type(admin_service, test_user):
    """TC-D10: Filter data sources by type."""
    # Create 5 Confluence, 3 JIRA, 2 Onboarding
    for i in range(5):
        await admin_service.create_data_source(
            name=f"Wiki {i+1}",
            source_type=DataSourceType.CONFLUENCE,
            config=CONFLUENCE_CONFIG.copy(),
            created_by=test_user.id
        )

    for i in range(3):
        await admin_service.create_data_source(
            name=f"JIRA {i+1}",
            source_type=DataSourceType.JIRA,
            config=JIRA_CONFIG.copy(),
            created_by=test_user.id
        )

    for i in range(2):
        await admin_service.create_data_source(
            name=f"Onboarding {i+1}",
            source_type=DataSourceType.ONBOARDING,
            config=ONBOARDING_CONFIG.copy(),
            created_by=test_user.id
        )

    # Filter by Confluence
    confluence_sources, confluence_total = await admin_service.list_data_sources(
        source_type=DataSourceType.CONFLUENCE
    )
    assert confluence_total == 5

    # Filter by JIRA
    jira_sources, jira_total = await admin_service.list_data_sources(
        source_type=DataSourceType.JIRA
    )
    assert jira_total == 3


@pytest.mark.asyncio
async def test_filter_data_sources_by_is_active(admin_service, test_user):
    """TC-D11: Filter data sources by is_active status."""
    # Create 3 active and 2 inactive
    for i in range(3):
        await admin_service.create_data_source(
            name=f"Active Wiki {i+1}",
            source_type=DataSourceType.CONFLUENCE,
            config=CONFLUENCE_CONFIG.copy(),
            is_active=True,
            created_by=test_user.id
        )

    for i in range(2):
        await admin_service.create_data_source(
            name=f"Inactive Wiki {i+1}",
            source_type=DataSourceType.CONFLUENCE,
            config=CONFLUENCE_CONFIG.copy(),
            is_active=False,
            created_by=test_user.id
        )

    # Filter active
    active_sources, active_total = await admin_service.list_data_sources(is_active=True)
    assert active_total == 3

    # Filter inactive
    inactive_sources, inactive_total = await admin_service.list_data_sources(is_active=False)
    assert inactive_total == 2


# ========== Encryption Integration Tests ==========

@pytest.mark.asyncio
async def test_encryption_on_create(admin_service, test_user, db_session):
    """TC-E1: Verify sensitive fields are encrypted on create."""
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Query database directly
    result = await db_session.execute(
        select(DataSource).where(DataSource.id == data_source.id)
    )
    db_source = result.scalar_one()

    # Verify api_token is encrypted (not plaintext)
    assert db_source.source_config["api_token"] != CONFLUENCE_CONFIG["api_token"]
    assert "gAAAAA" in db_source.source_config["api_token"], "Should be Fernet encrypted"


@pytest.mark.asyncio
async def test_encryption_remains_in_database(admin_service, test_user, db_session):
    """TC-E2: Verify sensitive fields remain encrypted in database."""
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Query directly from DB
    result = await db_session.execute(
        select(DataSource).where(DataSource.id == data_source.id)
    )
    db_source = result.scalar_one()

    # Encrypted value should not equal plaintext
    assert db_source.source_config["api_token"] != "confluence-token-12345"


@pytest.mark.asyncio
async def test_decryption_when_requested(admin_service, test_user):
    """TC-E3: Verify sensitive fields are decrypted when decrypt_config=True."""
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Retrieve with decryption
    retrieved = await admin_service.get_data_source(data_source.id, decrypt_config=True)

    # Verify decrypted value matches original
    assert retrieved.source_config["api_token"] == CONFLUENCE_CONFIG["api_token"]


@pytest.mark.asyncio
async def test_encryption_preserved_when_decrypt_false(admin_service, test_user):
    """TC-E4: Verify encryption preserved when decrypt_config=False."""
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Retrieve without decryption
    retrieved = await admin_service.get_data_source(data_source.id, decrypt_config=False)

    # Verify api_token is still encrypted
    assert retrieved.source_config["api_token"] != CONFLUENCE_CONFIG["api_token"]
    assert "gAAAAA" in retrieved.source_config["api_token"]


@pytest.mark.asyncio
async def test_update_preserves_encryption(admin_service, test_user):
    """TC-E5: Update operation preserves encryption."""
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Update config
    new_config = CONFLUENCE_CONFIG.copy()
    new_config["api_token"] = "new-secret-token-99999"

    updated = await admin_service.update_data_source(
        data_source.id,
        config=new_config
    )

    # Verify encryption
    assert updated.source_config["api_token"] != "new-secret-token-99999"

    # Verify decryption works
    retrieved = await admin_service.get_data_source(data_source.id, decrypt_config=True)
    assert retrieved.source_config["api_token"] == "new-secret-token-99999"


# ========== Cascade Delete Tests ==========

@pytest.mark.asyncio
async def test_delete_data_source_no_documents(admin_service, test_user):
    """TC-F1: Delete data source with no associated documents."""
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Delete
    success = await admin_service.delete_data_source(data_source.id)
    assert success is True


@pytest.mark.asyncio
async def test_delete_data_source_with_documents_cascade(admin_service, test_user, db_session):
    """TC-F2: Delete data source with associated documents (cascade)."""
    # Create data source
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Create 5 knowledge documents
    from models.knowledge import ContentType
    for i in range(5):
        doc = KnowledgeDocument(
            data_source_id=data_source.id,
            title=f"Document {i+1}",
            content=f"Content {i+1}",
            content_type=ContentType.PAGE,
            url=f"https://wiki.example.com/doc{i+1}"
        )
        db_session.add(doc)
    await db_session.commit()

    # Verify documents exist
    result = await db_session.execute(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.data_source_id == data_source.id
        )
    )
    count_before = result.scalar()
    assert count_before == 5

    # Delete data source
    success = await admin_service.delete_data_source(data_source.id)
    assert success is True

    # Expire session to ensure fresh query after cascade delete
    db_session.expire_all()

    # Verify documents are deleted (cascade)
    result = await db_session.execute(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.data_source_id == data_source.id
        )
    )
    count_after = result.scalar()
    assert count_after == 0, "Documents should be cascade deleted"


# ========== Error Handling Tests ==========

@pytest.mark.asyncio
async def test_create_data_source_invalid_config(admin_service, test_user):
    """TC-G1: Create data source with invalid config."""
    invalid_config = {
        "url": "https://wiki.example.com",
        "username": "admin@example.com",
        "space_key": "DOCS"
        # Missing api_token
    }

    with pytest.raises(DataSourceError) as exc_info:
        await admin_service.create_data_source(
            name="Test Wiki",
            source_type=DataSourceType.CONFLUENCE,
            config=invalid_config,
            created_by=test_user.id
        )

    assert "api_token" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_create_data_source_invalid_cron(admin_service, test_user):
    """TC-G2: Create data source with invalid cron expression."""
    with pytest.raises(DataSourceError) as exc_info:
        await admin_service.create_data_source(
            name="Test Wiki",
            source_type=DataSourceType.CONFLUENCE,
            config=CONFLUENCE_CONFIG.copy(),
            sync_schedule="invalid cron",
            created_by=test_user.id
        )

    assert "cron" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_update_nonexistent_data_source(admin_service):
    """TC-G3: Update non-existent data source."""
    with pytest.raises(DataSourceError) as exc_info:
        await admin_service.update_data_source(99999, name="New Name")

    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_delete_nonexistent_data_source(admin_service):
    """TC-G4: Delete non-existent data source."""
    with pytest.raises(DataSourceError) as exc_info:
        await admin_service.delete_data_source(99999)

    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_nonexistent_data_source(admin_service):
    """TC-G5: Get non-existent data source."""
    result = await admin_service.get_data_source(99999)
    assert result is None


@pytest.mark.asyncio
async def test_update_with_invalid_config(admin_service, test_user):
    """TC-G1: Update data source with invalid config."""
    # Create valid data source
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Try to update with invalid config
    invalid_config = {
        "url": "https://wiki.example.com",
        "username": "admin@example.com",
        "space_key": "DOCS"
        # Missing api_token
    }

    with pytest.raises(DataSourceError):
        await admin_service.update_data_source(
            data_source.id,
            config=invalid_config
        )


@pytest.mark.asyncio
async def test_update_with_invalid_cron(admin_service, test_user):
    """TC-G2: Update data source with invalid cron expression."""
    # Create valid data source
    data_source = await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # Try to update with invalid cron
    with pytest.raises(DataSourceError):
        await admin_service.update_data_source(
            data_source.id,
            sync_schedule="60 25 * * *"  # Invalid: minute 60, hour 25
        )


@pytest.mark.asyncio
async def test_list_data_sources_empty(admin_service):
    """Edge case: List data sources when none exist."""
    sources, total = await admin_service.list_data_sources()

    assert len(sources) == 0
    assert total == 0


@pytest.mark.asyncio
async def test_list_data_sources_decrypt_config(admin_service, test_user):
    """Verify list_data_sources decrypts config when requested."""
    # Create data source
    await admin_service.create_data_source(
        name="Test Wiki",
        source_type=DataSourceType.CONFLUENCE,
        config=CONFLUENCE_CONFIG.copy(),
        created_by=test_user.id
    )

    # List with decryption
    sources, total = await admin_service.list_data_sources(decrypt_config=True)

    assert len(sources) == 1
    assert sources[0].source_config["api_token"] == CONFLUENCE_CONFIG["api_token"]
