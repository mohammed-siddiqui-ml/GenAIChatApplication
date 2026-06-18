"""
Audit log model for tracking admin actions.

This module defines the AuditLog model for maintaining an audit trail
of administrative actions in the system.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .types import INET, JSONB


class AuditLog(Base):
    """
    Audit log model for tracking administrative actions.
    
    Maintains a comprehensive audit trail of all admin actions including
    data source configuration, user management, and system changes.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table (who performed the action)
        action: Description of the action performed
        resource_type: Type of resource affected (e.g., 'data_source', 'user')
        resource_id: ID of the affected resource
        changes: JSON object containing the changes made
        ip_address: IP address of the user
        created_at: Timestamp when the action occurred
        
    Relationships:
        user: User who performed the action
    """
    __tablename__ = "audit_logs"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Unique audit log identifier"
    )
    
    # Foreign keys
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the action"
    )
    
    # Audit attributes
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Description of the action performed"
    )
    
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of resource affected"
    )
    
    resource_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="ID of the affected resource"
    )
    
    audit_changes: Mapped[Optional[dict]] = mapped_column(
        "changes",  # Database column name
        JSONB,
        nullable=True,
        comment="JSON object containing the changes made"
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        comment="IP address of the user"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Timestamp when the action occurred"
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        """String representation of the AuditLog model."""
        return (
            f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}', "
            f"resource='{self.resource_type}:{self.resource_id}')>"
        )
    
    def get_user_email(self) -> Optional[str]:
        """
        Get the email of the user who performed the action.
        
        Returns:
            User's email if user exists, None otherwise
        """
        return self.user.email if self.user else None
