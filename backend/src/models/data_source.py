"""
Data source models for managing external data integrations.

This module defines models for data sources and their ingestion jobs,
supporting integrations with Confluence, JIRA, and other systems.
"""
from datetime import datetime
from typing import List, Optional
import enum

from sqlalchemy import (
    BigInteger, Integer, String, Text, TIMESTAMP, Boolean, ForeignKey,
    Enum as SQLEnum, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .types import JSONB


class DataSourceType(str, enum.Enum):
    """Enumeration of supported data source types."""
    CONFLUENCE = "confluence"
    JIRA = "jira"
    ONBOARDING = "onboarding"
    CUSTOM = "custom"


class JobStatus(str, enum.Enum):
    """Enumeration of ingestion job statuses."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class DataSource(Base, TimestampMixin):
    """
    Data source model representing external knowledge repositories.

    Represents configured data sources like Confluence spaces, JIRA projects,
    or custom document repositories.

    Attributes:
        id: Primary key
        name: Display name of the data source
        type: Type of data source (confluence, jira, etc.)
        config: Configuration settings (JSON)
        is_active: Flag indicating if the data source is active
        sync_schedule: Cron expression for sync scheduling
        last_sync_at: Timestamp of last successful sync
        created_by: User who created this data source
        created_at: Creation timestamp
        updated_at: Last update timestamp

    Relationships:
        creator: User who created this data source
        ingestion_jobs: List of ingestion jobs for this source
        knowledge_documents: List of documents from this source
    """
    __tablename__ = "data_sources"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique data source identifier"
    )

    # Data source attributes
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name of the data source"
    )

    type: Mapped[DataSourceType] = mapped_column(
        SQLEnum(DataSourceType, name="data_source_type", create_constraint=True),
        nullable=False,
        index=True,
        comment="Type of data source"
    )

    source_config: Mapped[Optional[dict]] = mapped_column(
        "config",  # Database column name
        JSONB,
        nullable=True,
        comment="Configuration settings (URLs, credentials, filters)"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Flag indicating if the data source is active"
    )

    sync_schedule: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Cron expression for sync scheduling"
    )

    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
        comment="Timestamp of last successful sync"
    )

    # Foreign keys
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who created this data source"
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="data_sources",
        foreign_keys=[created_by],
        lazy="selectin"
    )

    ingestion_jobs: Mapped[List["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="data_source",
        cascade="all, delete-orphan",
        order_by="IngestionJob.started_at.desc()",
        lazy="selectin"
    )

    knowledge_documents: Mapped[List["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        back_populates="data_source",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """String representation of the DataSource model."""
        return f"<DataSource(id={self.id}, name='{self.name}', type='{self.type.value}')>"




class IngestionJob(Base):
    """
    Ingestion job model for tracking data synchronization tasks.

    Tracks the progress and status of data ingestion from external sources.

    Attributes:
        id: Primary key
        data_source_id: Foreign key to data_sources table
        status: Current job status (pending, running, success, failed)
        started_at: When the job started
        completed_at: When the job completed
        documents_processed: Number of documents successfully processed
        documents_failed: Number of documents that failed processing
        error_message: Error message if job failed
        metadata: Additional metadata (JSON)

    Relationships:
        data_source: Associated data source
    """
    __tablename__ = "ingestion_jobs"

    # Primary key
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Unique ingestion job identifier"
    )

    # Foreign keys
    data_source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated data source ID"
    )

    # Job attributes
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status", create_constraint=True),
        nullable=False,
        comment="Current job status"
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
        comment="Job start timestamp"
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
        comment="Job completion timestamp"
    )

    documents_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of documents successfully processed"
    )

    documents_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of documents that failed processing"
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if job failed"
    )

    job_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",  # Database column name
        JSONB,
        nullable=True,
        comment="Additional metadata (logs, stats, etc.)"
    )

    # Relationships
    data_source: Mapped["DataSource"] = relationship(
        "DataSource",
        back_populates="ingestion_jobs",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """String representation of the IngestionJob model."""
        return (
            f"<IngestionJob(id={self.id}, data_source_id={self.data_source_id}, "
            f"status='{self.status.value}', processed={self.documents_processed})>"
        )

    def is_complete(self) -> bool:
        """Check if the job is complete (success or failed)."""
        return self.status in (JobStatus.SUCCESS, JobStatus.FAILED)

    def is_running(self) -> bool:
        """Check if the job is currently running."""
        return self.status == JobStatus.RUNNING
