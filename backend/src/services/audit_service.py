"""
Audit Service for Admin Action Tracking

This module provides audit logging services for tracking all administrative
actions in the system, including CRUD operations on data sources, user management,
and system configuration changes.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.audit import AuditLog
from models.user import User

# Logger
logger = logging.getLogger(__name__)


class AuditServiceError(Exception):
    """Custom exception for audit service errors."""
    pass


class AuditService:
    """
    Service for managing audit logs and tracking administrative actions.
    
    Provides functionality for:
    - Creating audit log entries for admin actions
    - Querying audit logs with filtering and pagination
    - Tracking before/after state changes
    - Recording IP addresses and user information
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the audit service.
        
        Args:
            db_session: Async database session for audit log operations
        """
        self.db = db_session
    
    async def create_audit_log(
        self,
        user_id: Optional[int],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Create a new audit log entry.
        
        Records an administrative action with all relevant context including
        user, action type, resource affected, changes made, and IP address.
        
        Args:
            user_id: ID of the user who performed the action (None for system actions)
            action: Description of the action (e.g., 'create', 'update', 'delete')
            resource_type: Type of resource affected (e.g., 'data_source', 'user', 'config')
            resource_id: ID of the affected resource
            changes: Dictionary containing before/after state or change details
            ip_address: IP address of the user performing the action
            
        Returns:
            AuditLog: Created audit log instance
            
        Raises:
            AuditServiceError: If audit log creation fails
            
        Example:
            >>> audit_log = await service.create_audit_log(
            ...     user_id=1,
            ...     action="create",
            ...     resource_type="data_source",
            ...     resource_id=5,
            ...     changes={"name": "New Wiki", "type": "confluence"},
            ...     ip_address="192.168.1.100"
            ... )
        """
        try:
            # Create audit log entry
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                audit_changes=changes,
                ip_address=ip_address
            )
            
            self.db.add(audit_log)
            await self.db.flush()
            await self.db.refresh(audit_log)
            
            logger.info(
                f"Audit log created: user_id={user_id}, action={action}, "
                f"resource={resource_type}:{resource_id}"
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            raise AuditServiceError(f"Failed to create audit log: {str(e)}")
    
    async def get_audit_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[AuditLog], int]:
        """
        Query audit logs with filtering and pagination.
        
        Supports filtering by user, action type, resource type, and date range.
        Returns paginated results with total count for UI pagination.
        
        Args:
            user_id: Filter by user ID
            action: Filter by action type (e.g., 'create', 'update', 'delete')
            resource_type: Filter by resource type (e.g., 'data_source', 'user')
            start_date: Filter logs created on or after this date
            end_date: Filter logs created on or before this date
            limit: Maximum number of results to return (default: 50)
            offset: Number of results to skip for pagination (default: 0)

        Returns:
            Tuple of (audit_logs, total_count)

        Raises:
            AuditServiceError: If query fails

        Example:
            >>> logs, total = await service.get_audit_logs(
            ...     user_id=1,
            ...     action="delete",
            ...     limit=20,
            ...     offset=0
            ... )
        """
        try:
            # Build query with filters
            query = select(AuditLog)
            count_query = select(func.count(AuditLog.id))

            filters = []

            # Apply filters
            if user_id is not None:
                filters.append(AuditLog.user_id == user_id)

            if action is not None:
                filters.append(AuditLog.action == action)

            if resource_type is not None:
                filters.append(AuditLog.resource_type == resource_type)

            if start_date is not None:
                filters.append(AuditLog.created_at >= start_date)

            if end_date is not None:
                filters.append(AuditLog.created_at <= end_date)

            # Apply filters to both queries
            if filters:
                query = query.where(and_(*filters))
                count_query = count_query.where(and_(*filters))

            # Order by created_at descending (newest first)
            query = query.order_by(AuditLog.created_at.desc())

            # Apply pagination
            query = query.limit(limit).offset(offset)

            # Execute queries
            result = await self.db.execute(query)
            audit_logs = result.scalars().all()

            count_result = await self.db.execute(count_query)
            total_count = count_result.scalar() or 0

            logger.debug(
                f"Retrieved {len(audit_logs)} audit logs (total: {total_count}) "
                f"with filters: user_id={user_id}, action={action}, "
                f"resource_type={resource_type}"
            )

            return list(audit_logs), total_count

        except Exception as e:
            logger.error(f"Failed to query audit logs: {str(e)}")
            raise AuditServiceError(f"Failed to query audit logs: {str(e)}")
