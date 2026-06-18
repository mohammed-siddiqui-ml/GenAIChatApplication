"""
User model for authentication and authorization.

This module defines the User model representing admin and regular users
in the system with role-based access control.
"""
from typing import List, Optional
import enum

from sqlalchemy import Boolean, Integer, String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """Enumeration of user roles in the system."""
    ADMIN = "admin"
    USER = "user"


class User(Base, TimestampMixin):
    """
    User model for authentication and authorization.
    
    Represents both admin users (who can manage data sources and configurations)
    and regular users in the system.
    
    Attributes:
        id: Primary key
        email: Unique email address for login
        password_hash: Hashed password for authentication
        role: User role (admin or user)
        is_active: Flag indicating if the user account is active
        created_at: Timestamp when the user was created
        updated_at: Timestamp when the user was last updated
        
    Relationships:
        chat_sessions: List of chat sessions associated with this user
        data_sources: List of data sources created by this user
        audit_logs: List of audit log entries for this user's actions
    """
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique user identifier"
    )
    
    # User credentials
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="User's email address (unique)"
    )
    
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password for authentication"
    )
    
    # User attributes
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        server_default="user",
        comment="User role (admin or user)"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Flag indicating if the user account is active"
    )
    
    # Relationships
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    data_sources: Mapped[List["DataSource"]] = relationship(
        "DataSource",
        back_populates="creator",
        foreign_keys="[DataSource.created_by]",
        lazy="selectin"
    )
    
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        """String representation of the User model."""
        return f"<User(id={self.id}, email='{self.email}', role='{self.role.value}')>"
    
    def has_role(self, role: UserRole) -> bool:
        """
        Check if the user has a specific role.
        
        Args:
            role: UserRole to check
            
        Returns:
            True if user has the specified role, False otherwise
        """
        return self.role == role
    
    def is_admin(self) -> bool:
        """
        Check if the user is an admin.
        
        Returns:
            True if user is an admin, False otherwise
        """
        return self.role == UserRole.ADMIN
