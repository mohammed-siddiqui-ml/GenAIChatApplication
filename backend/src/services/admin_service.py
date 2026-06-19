"""
Admin Service for Data Source Management

This module provides administrative services for managing data sources,
including CRUD operations, configuration validation, and sync schedule management.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.data_source import DataSource, DataSourceType
from models.knowledge import KnowledgeDocument
from utils.crypto import encrypt_config_dict, decrypt_config_dict, CryptoError
from utils.validators import validate_url, validate_cron_expression, ValidationError

# Logger
logger = logging.getLogger(__name__)


class DataSourceError(Exception):
    """Custom exception for data source management errors."""
    pass


class DataSourceService:
    """
    Service for managing data sources and their configurations.
    
    Provides CRUD operations for data sources with:
    - Configuration validation for each data source type
    - Encryption of sensitive fields (API tokens, credentials)
    - Cron expression validation for sync schedules
    - Cascade deletion of related documents
    """
    
    # Define sensitive fields for each data source type
    SENSITIVE_FIELDS = {
        DataSourceType.CONFLUENCE: ['api_token', 'password', 'api_key'],
        DataSourceType.JIRA: ['api_token', 'password', 'api_key'],
        DataSourceType.ONBOARDING: ['api_token', 'password', 'api_key'],
        DataSourceType.CUSTOM: ['api_token', 'password', 'api_key', 'credentials'],
    }
    
    # Required configuration fields for each data source type
    REQUIRED_CONFIG_FIELDS = {
        DataSourceType.CONFLUENCE: ['url', 'username', 'api_token', 'space_key'],
        DataSourceType.JIRA: ['url', 'username', 'api_token', 'project_key'],
        DataSourceType.ONBOARDING: ['storage_path'],
        DataSourceType.CUSTOM: ['url'],
    }
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the data source service.
        
        Args:
            db_session: Async database session for data source operations
        """
        self.db = db_session
    
    def validate_config(self, source_type: DataSourceType, config: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate configuration for a specific data source type.
        
        Validates:
        - Required fields are present
        - URL format is valid
        - API credentials are provided
        
        Args:
            source_type: Type of data source (confluence, jira, etc.)
            config: Configuration dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            
        Example:
            >>> valid, error = service.validate_config(
            ...     DataSourceType.CONFLUENCE,
            ...     {"url": "https://wiki.example.com", "username": "user", 
            ...      "api_token": "token123", "space_key": "DOCS"}
            ... )
            >>> assert valid is True
        """
        if not config:
            return False, "Configuration is required"
        
        # Check required fields
        required_fields = self.REQUIRED_CONFIG_FIELDS.get(source_type, [])
        missing_fields = [field for field in required_fields if field not in config or not config[field]]
        
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        
        # Validate URLs
        if 'url' in config:
            if not validate_url(config['url']):
                return False, f"Invalid URL format: {config['url']}"
        
        # Type-specific validation
        if source_type == DataSourceType.CONFLUENCE:
            # Validate space key format (alphanumeric, underscores, hyphens)
            space_key = config.get('space_key', '')
            if not space_key.replace('-', '').replace('_', '').isalnum():
                return False, "Space key must be alphanumeric (with hyphens/underscores)"
        
        elif source_type == DataSourceType.JIRA:
            # Validate project key format (uppercase alphanumeric)
            project_key = config.get('project_key', '')
            if not project_key.isupper() or not project_key.isalnum():
                return False, "Project key must be uppercase alphanumeric"
        
        elif source_type == DataSourceType.ONBOARDING:
            # Validate storage path exists (basic check)
            storage_path = config.get('storage_path', '')
            if not storage_path or storage_path.strip() == '':
                return False, "Storage path cannot be empty"
        
        return True, None
    
    def _encrypt_sensitive_fields(self, source_type: DataSourceType, config: dict) -> dict:
        """
        Encrypt sensitive configuration fields.
        
        Args:
            source_type: Type of data source
            config: Configuration dictionary
            
        Returns:
            dict: Configuration with encrypted sensitive fields
        """
        sensitive_fields = self.SENSITIVE_FIELDS.get(source_type, [])
        try:
            return encrypt_config_dict(config, sensitive_fields)
        except CryptoError as e:
            logger.error(f"Failed to encrypt config fields: {str(e)}")
            raise DataSourceError(f"Encryption failed: {str(e)}")
    
    def _decrypt_sensitive_fields(self, source_type: DataSourceType, config: dict) -> dict:
        """
        Decrypt sensitive configuration fields.

        Args:
            source_type: Type of data source
            config: Configuration dictionary with encrypted fields

        Returns:
            dict: Configuration with decrypted sensitive fields
        """
        sensitive_fields = self.SENSITIVE_FIELDS.get(source_type, [])
        try:
            return decrypt_config_dict(config, sensitive_fields)
        except CryptoError as e:
            logger.error(f"Failed to decrypt config fields: {str(e)}")
            # Return original config if decryption fails
            return config

    async def create_data_source(
        self,
        name: str,
        source_type: DataSourceType,
        config: dict,
        sync_schedule: Optional[str] = None,
        is_active: bool = True,
        created_by: Optional[int] = None
    ) -> DataSource:
        """
        Create a new data source with validated configuration.

        Validates configuration, encrypts sensitive fields, and validates
        cron expression for sync schedule.

        Args:
            name: Display name for the data source
            source_type: Type of data source (confluence, jira, onboarding)
            config: Configuration dictionary with connection details
            sync_schedule: Optional cron expression for sync scheduling
            is_active: Whether the data source is active (default: True)
            created_by: Optional user ID who created this source

        Returns:
            DataSource: Created data source instance

        Raises:
            DataSourceError: If validation fails or creation errors occur

        Example:
            >>> source = await service.create_data_source(
            ...     name="Company Wiki",
            ...     source_type=DataSourceType.CONFLUENCE,
            ...     config={"url": "https://wiki.example.com", ...},
            ...     sync_schedule="0 2 * * *"
            ... )
        """
        try:
            # Validate configuration
            is_valid, error_msg = self.validate_config(source_type, config)
            if not is_valid:
                logger.warning(f"Config validation failed: {error_msg}")
                raise DataSourceError(f"Invalid configuration: {error_msg}")

            # Validate cron expression if provided
            if sync_schedule:
                if not validate_cron_expression(sync_schedule):
                    logger.warning(f"Invalid cron expression: {sync_schedule}")
                    raise DataSourceError(f"Invalid cron expression: {sync_schedule}")

            # Encrypt sensitive fields
            encrypted_config = self._encrypt_sensitive_fields(source_type, config)

            # Create data source instance
            data_source = DataSource(
                name=name,
                type=source_type,
                source_config=encrypted_config,
                sync_schedule=sync_schedule,
                is_active=is_active,
                created_by=created_by,
            )

            # Add to database
            self.db.add(data_source)
            await self.db.commit()
            await self.db.refresh(data_source)

            logger.info(f"Created data source: {name} (ID: {data_source.id}, Type: {source_type.value})")
            return data_source

        except DataSourceError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create data source: {str(e)}")
            raise DataSourceError(f"Failed to create data source: {str(e)}")

    async def update_data_source(
        self,
        data_source_id: int,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        sync_schedule: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> DataSource:
        """
        Update an existing data source.

        Updates configuration, sync schedule, or active status.
        Validates configuration if provided and encrypts sensitive fields.

        Args:
            data_source_id: ID of the data source to update
            name: Optional new name
            config: Optional new configuration (replaces existing)
            sync_schedule: Optional new cron expression (pass empty string to clear)
            is_active: Optional new active status

        Returns:
            DataSource: Updated data source instance

        Raises:
            DataSourceError: If data source not found or validation fails
        """
        try:
            # Fetch existing data source
            result = await self.db.execute(
                select(DataSource).where(DataSource.id == data_source_id)
            )
            data_source = result.scalar_one_or_none()

            if not data_source:
                raise DataSourceError(f"Data source not found: {data_source_id}")

            # Update name if provided
            if name is not None:
                data_source.name = name

            # Update configuration if provided
            if config is not None:
                # Validate new configuration
                is_valid, error_msg = self.validate_config(data_source.type, config)
                if not is_valid:
                    raise DataSourceError(f"Invalid configuration: {error_msg}")

                # Encrypt sensitive fields
                encrypted_config = self._encrypt_sensitive_fields(data_source.type, config)
                data_source.source_config = encrypted_config

            # Update sync schedule if provided
            if sync_schedule is not None:
                if sync_schedule == "":
                    # Clear schedule
                    data_source.sync_schedule = None
                else:
                    # Validate cron expression
                    if not validate_cron_expression(sync_schedule):
                        raise DataSourceError(f"Invalid cron expression: {sync_schedule}")
                    data_source.sync_schedule = sync_schedule

            # Update active status if provided
            if is_active is not None:
                data_source.is_active = is_active

            # Commit changes
            await self.db.commit()
            await self.db.refresh(data_source)

            logger.info(f"Updated data source: {data_source.name} (ID: {data_source_id})")
            return data_source

        except DataSourceError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update data source: {str(e)}")
            raise DataSourceError(f"Failed to update data source: {str(e)}")

    async def delete_data_source(self, data_source_id: int) -> bool:
        """
        Delete a data source and cascade delete all related documents.

        Deletes the data source and all associated knowledge documents
        and embeddings (cascade delete is handled by database constraints).

        Args:
            data_source_id: ID of the data source to delete

        Returns:
            bool: True if deletion successful

        Raises:
            DataSourceError: If data source not found or deletion fails

        Example:
            >>> success = await service.delete_data_source(123)
            >>> assert success is True
        """
        try:
            # Fetch data source to verify it exists
            result = await self.db.execute(
                select(DataSource).where(DataSource.id == data_source_id)
            )
            data_source = result.scalar_one_or_none()

            if not data_source:
                raise DataSourceError(f"Data source not found: {data_source_id}")

            # Log documents to be deleted
            doc_count_result = await self.db.execute(
                select(func.count(KnowledgeDocument.id))
                .where(KnowledgeDocument.data_source_id == data_source_id)
            )
            doc_count = doc_count_result.scalar()

            logger.info(
                f"Deleting data source: {data_source.name} (ID: {data_source_id}) "
                f"and {doc_count} associated documents"
            )

            # Delete data source (cascade delete handles documents and embeddings)
            await self.db.delete(data_source)
            await self.db.commit()

            logger.info(f"Successfully deleted data source: {data_source_id}")
            return True

        except DataSourceError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete data source: {str(e)}")
            raise DataSourceError(f"Failed to delete data source: {str(e)}")

    async def list_data_sources(
        self,
        source_type: Optional[DataSourceType] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
        decrypt_config: bool = False
    ) -> Tuple[List[DataSource], int]:
        """
        List data sources with filtering and pagination.

        Supports filtering by source type and active status.
        Returns paginated results with total count.

        Args:
            source_type: Optional filter by data source type
            is_active: Optional filter by active status
            limit: Maximum number of results (default: 100, max: 1000)
            offset: Number of results to skip (default: 0)
            decrypt_config: Whether to decrypt sensitive fields (default: False)

        Returns:
            Tuple of (list of data sources, total count)

        Example:
            >>> sources, total = await service.list_data_sources(
            ...     source_type=DataSourceType.CONFLUENCE,
            ...     is_active=True,
            ...     limit=10,
            ...     offset=0
            ... )
        """
        try:
            # Enforce maximum limit
            limit = min(limit, 1000)

            # Build base query
            query = select(DataSource)
            count_query = select(func.count(DataSource.id))

            # Apply filters
            if source_type is not None:
                query = query.where(DataSource.type == source_type)
                count_query = count_query.where(DataSource.type == source_type)

            if is_active is not None:
                query = query.where(DataSource.is_active == is_active)
                count_query = count_query.where(DataSource.is_active == is_active)

            # Get total count
            total_result = await self.db.execute(count_query)
            total_count = total_result.scalar()

            # Apply pagination and ordering
            query = query.order_by(DataSource.created_at.desc())
            query = query.limit(limit).offset(offset)

            # Execute query
            result = await self.db.execute(query)
            data_sources = list(result.scalars().all())

            # Decrypt sensitive fields if requested
            if decrypt_config:
                for source in data_sources:
                    if source.source_config:
                        source.source_config = self._decrypt_sensitive_fields(
                            source.type,
                            source.source_config
                        )

            logger.debug(
                f"Listed {len(data_sources)} data sources "
                f"(total: {total_count}, limit: {limit}, offset: {offset})"
            )

            return data_sources, total_count

        except Exception as e:
            logger.error(f"Failed to list data sources: {str(e)}")
            raise DataSourceError(f"Failed to list data sources: {str(e)}")

    async def get_data_source(
        self,
        data_source_id: int,
        decrypt_config: bool = False
    ) -> Optional[DataSource]:
        """
        Get a single data source by ID.

        Args:
            data_source_id: ID of the data source
            decrypt_config: Whether to decrypt sensitive fields (default: False)

        Returns:
            DataSource instance or None if not found
        """
        try:
            result = await self.db.execute(
                select(DataSource).where(DataSource.id == data_source_id)
            )
            data_source = result.scalar_one_or_none()

            if data_source and decrypt_config and data_source.source_config:
                data_source.source_config = self._decrypt_sensitive_fields(
                    data_source.type,
                    data_source.source_config
                )

            return data_source

        except Exception as e:
            logger.error(f"Failed to get data source: {str(e)}")
            raise DataSourceError(f"Failed to get data source: {str(e)}")
