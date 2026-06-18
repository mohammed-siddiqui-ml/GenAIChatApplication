"""
JWT Authentication Middleware

This module provides FastAPI dependencies for JWT authentication,
including token extraction from headers or HTTP-only cookies,
token validation, and user authorization.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.auth_service import AuthService
from models.user import User, UserRole

# Logger
logger = logging.getLogger(__name__)

# HTTP Bearer security scheme for Swagger UI
security = HTTPBearer(auto_error=False)

# Cookie configuration for JWT tokens
COOKIE_NAME = "access_token"
COOKIE_SECURE = True  # Use True in production with HTTPS
COOKIE_HTTPONLY = True  # Prevent JavaScript access to cookie
COOKIE_SAMESITE = "lax"  # CSRF protection
COOKIE_MAX_AGE = 24 * 60 * 60  # 24 hours in seconds


async def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Extract JWT token from request headers or HTTP-only cookie.
    
    Tries to get the token from:
    1. Authorization header (Bearer token)
    2. HTTP-only cookie
    
    Args:
        request: FastAPI request object
        credentials: Optional HTTP Bearer credentials
        
    Returns:
        JWT token string if found, None otherwise
    """
    # Try to get token from Authorization header
    if credentials:
        return credentials.credentials
    
    # Try to get token from HTTP-only cookie
    token = request.cookies.get(COOKIE_NAME)
    if token:
        # Remove "Bearer " prefix if present in cookie
        if token.startswith("Bearer "):
            token = token[7:]
        return token
    
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(get_token_from_request)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    This dependency validates the JWT token and returns the associated user.
    Raises HTTPException if authentication fails.
    
    Args:
        request: FastAPI request object
        db: Database session
        token: JWT token from request
        
    Returns:
        Authenticated User object
        
    Raises:
        HTTPException: If authentication fails (401 Unauthorized)
    """
    if not token:
        logger.warning("Authentication failed: no token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate token and get user
    auth_service = AuthService(db)
    user = await auth_service.get_current_user(token)
    
    if not user:
        logger.warning("Authentication failed: invalid token or user not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"User authenticated: {user.email}")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user.
    
    This dependency ensures the user account is active.
    
    Args:
        current_user: User from get_current_user dependency
        
    Returns:
        Active User object
        
    Raises:
        HTTPException: If user account is inactive (403 Forbidden)
    """
    if not current_user.is_active:
        logger.warning(f"Inactive user attempted access: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Require admin role for access.
    
    This dependency ensures the user has admin privileges.
    Use this for routes that should only be accessible to admins.
    
    Args:
        current_user: Active user from get_current_active_user dependency
        
    Returns:
        Admin User object
        
    Raises:
        HTTPException: If user is not an admin (403 Forbidden)
    """
    if not current_user.is_admin():
        logger.warning(f"Non-admin user attempted admin access: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


def set_auth_cookie(response: Response, token: str) -> None:
    """
    Set JWT token as an HTTP-only cookie in the response.
    
    This provides an additional layer of security by storing the JWT
    in an HTTP-only cookie that cannot be accessed by JavaScript,
    protecting against XSS attacks.
    
    Args:
        response: FastAPI response object
        token: JWT token to set in cookie
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=f"Bearer {token}",
        max_age=COOKIE_MAX_AGE,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )
    logger.debug("Auth cookie set in response")


def clear_auth_cookie(response: Response) -> None:
    """
    Clear the authentication cookie from the response.
    
    Used during logout to remove the JWT cookie.
    
    Args:
        response: FastAPI response object
    """
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )
    logger.debug("Auth cookie cleared from response")
