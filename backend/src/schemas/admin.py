"""
Admin Request/Response Schemas

This module defines Pydantic schemas for admin API endpoints
including data source CRUD operations and configuration management.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from models.data_source import DataSourceType


class DataSourceCreate(BaseModel):
    """
    Request schema for creating a new data source.

    Validates:
    - Data source name (1-100 characters)
    - Data source type (confluence, jira, onboarding, custom)
    - Configuration dictionary with required fields based on type
    - Optional sync schedule (cron expression)
    - Optional active status (defaults to True)
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name of the data source",
        examples=["Company Wiki"]
    )
    type: DataSourceType = Field(
        ...,
        description="Type of data source (confluence, jira, onboarding, custom)",
        examples=["confluence"]
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Configuration settings (URLs, credentials, filters). Required fields vary by type.",
        examples=[{
            "url": "https://wiki.example.com",
            "username": "admin",
            "api_token": "token123",
            "space_key": "DOCS"
        }]
    )
    sync_schedule: Optional[str] = Field(
        default=None,
        description="Cron expression for sync scheduling (e.g., '0 2 * * *' for 2 AM daily)",
        examples=["0 2 * * *", "*/30 * * * *"]
    )
    is_active: bool = Field(
        default=True,
        description="Whether the data source is active",
        examples=[True]
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Company Wiki",
                    "type": "confluence",
                    "config": {
                        "url": "https://wiki.example.com",
                        "username": "admin",
                        "api_token": "token123",
                        "space_key": "DOCS"
                    },
                    "sync_schedule": "0 2 * * *",
                    "is_active": True
                },
                {
                    "name": "Support Tickets",
                    "type": "jira",
                    "config": {
                        "url": "https://jira.example.com",
                        "username": "admin",
                        "api_token": "token456",
                        "project_key": "SUP"
                    },
                    "sync_schedule": "*/30 * * * *",
                    "is_active": True
                }
            ]
        }
    }


class DataSourceUpdate(BaseModel):
    """
    Request schema for updating an existing data source.

    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated display name",
        examples=["Updated Wiki Name"]
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Updated configuration (replaces existing config)",
        examples=[{
            "url": "https://newwiki.example.com",
            "username": "admin",
            "api_token": "newtoken",
            "space_key": "DOCS"
        }]
    )
    sync_schedule: Optional[str] = Field(
        default=None,
        description="Updated cron expression (pass empty string to clear)",
        examples=["0 3 * * *", ""]
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Updated active status",
        examples=[False]
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate name is not empty or just whitespace if provided."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Name cannot be empty or whitespace')
            return v.strip()
        return v

    @field_validator('sync_schedule')
    @classmethod
    def validate_sync_schedule(cls, v: Optional[str]) -> Optional[str]:
        """Validate sync_schedule is not just whitespace if provided."""
        if v is not None and v != "" and not v.strip():
            raise ValueError('Sync schedule cannot be just whitespace')
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Updated Company Wiki",
                    "is_active": False
                },
                {
                    "sync_schedule": "0 3 * * *"
                }
            ]
        }
    }



class DataSourceResponse(BaseModel):
    """
    Response schema for data source information.

    Returns complete data source information including metadata
    and timestamps. Sensitive fields in config are encrypted.
    """
    id: int = Field(..., description="Data source ID", examples=[1])
    name: str = Field(..., description="Display name", examples=["Company Wiki"])
    type: str = Field(..., description="Data source type", examples=["confluence"])
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration settings (sensitive fields encrypted)",
        examples=[{
            "url": "https://wiki.example.com",
            "username": "admin",
            "api_token": "[ENCRYPTED]",
            "space_key": "DOCS"
        }]
    )
    is_active: bool = Field(..., description="Active status", examples=[True])
    sync_schedule: Optional[str] = Field(
        None,
        description="Cron expression for sync scheduling",
        examples=["0 2 * * *"]
    )
    last_sync_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last successful sync",
        examples=["2024-01-15T02:00:00Z"]
    )
    created_by: Optional[int] = Field(
        None,
        description="User ID who created this data source",
        examples=[1]
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
        examples=["2024-01-01T10:00:00Z"]
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
        examples=["2024-01-15T14:30:00Z"]
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Company Wiki",
                    "type": "confluence",
                    "config": {
                        "url": "https://wiki.example.com",
                        "username": "admin",
                        "api_token": "[ENCRYPTED]",
                        "space_key": "DOCS"
                    },
                    "is_active": True,
                    "sync_schedule": "0 2 * * *",
                    "last_sync_at": "2024-01-15T02:00:00Z",
                    "created_by": 1,
                    "created_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-15T14:30:00Z"
                }
            ]
        }
    }


class DataSourceListResponse(BaseModel):
    """
    Response schema for paginated data source list.

    Returns list of data sources with pagination metadata.
    """
    items: list[DataSourceResponse] = Field(
        ...,
        description="List of data sources",
        examples=[[]]
    )
    total: int = Field(
        ...,
        description="Total number of data sources matching filters",
        examples=[42]
    )
    limit: int = Field(
        ...,
        description="Number of items per page",
        examples=[20]
    )
    offset: int = Field(
        ...,
        description="Number of items skipped",
        examples=[0]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "name": "Company Wiki",
                            "type": "confluence",
                            "config": {
                                "url": "https://wiki.example.com",
                                "space_key": "DOCS"
                            },
                            "is_active": True,
                            "sync_schedule": "0 2 * * *",
                            "last_sync_at": "2024-01-15T02:00:00Z",
                            "created_by": 1,
                            "created_at": "2024-01-01T10:00:00Z",
                            "updated_at": "2024-01-15T14:30:00Z"
                        }
                    ],
                    "total": 42,
                    "limit": 20,
                    "offset": 0
                }
            ]
        }
    }
