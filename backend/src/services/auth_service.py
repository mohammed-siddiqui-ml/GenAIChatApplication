"""
Authentication Service

This module provides authentication services including user login, logout,
token generation and validation, and session management with Redis-based
token blacklist for secure logout functionality.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token,
)
from core.redis import get_redis_client
from models.user import User, UserRole

# Logger
logger = logging.getLogger(__name__)

# Redis key prefixes for token blacklist
TOKEN_BLACKLIST_PREFIX = "auth:blacklist:"
TOKEN_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours in seconds


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    pass


class AuthService:
    """
    Authentication service for user login, logout, and token management.
    
    This service handles:
    - User authentication with email and password
    - JWT token generation (access and refresh tokens)
    - Token validation and verification
    - Token blacklist management in Redis for secure logout
    - Session management
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the authentication service.
        
        Args:
            db_session: Async database session for user queries
        """
        self.db = db_session
        self.redis_client = get_redis_client()
    
    async def authenticate_user(
        self,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate a user with email and password.
        
        Verifies the user's credentials against the database and checks
        that the account is active.
        
        Args:
            email: User's email address
            password: Plain text password to verify
            
        Returns:
            User object if authentication successful, None otherwise
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Query user by email
            result = await self.db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            
            # Check if user exists
            if not user:
                logger.warning(f"Authentication failed: user not found - {email}")
                return None
            
            # Check if account is active
            if not user.is_active:
                logger.warning(f"Authentication failed: account inactive - {email}")
                raise AuthenticationError("Account is inactive")
            
            # Verify password
            if not verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed: invalid password - {email}")
                return None
            
            logger.info(f"User authenticated successfully: {email}")
            return user
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    async def login(
        self,
        email: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Perform user login and generate JWT tokens.
        
        Authenticates the user and generates both access and refresh tokens
        with appropriate expiration times (24 hours for access, 7 days for refresh).
        
        Args:
            email: User's email address
            password: Plain text password
            
        Returns:
            Dictionary containing:
            - access_token: JWT access token (24-hour expiry)
            - refresh_token: JWT refresh token (7-day expiry)
            - token_type: "bearer"
            - user: User information (id, email, role)
            
        Raises:
            AuthenticationError: If login fails
        """
        # Authenticate user
        user = await self.authenticate_user(email, password)
        
        if not user:
            raise AuthenticationError("Invalid email or password")
        
        # Prepare token payload
        token_data = {
            "sub": user.email,
            "user_id": user.id,
            "role": user.role.value,
        }
        
        # Generate access token (24-hour expiry as per requirements)
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(hours=24)
        )

        # Generate refresh token (7-day expiry)
        refresh_token = create_refresh_token(data=token_data)

        logger.info(f"Login successful for user: {email}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role.value,
            }
        }

    async def logout(self, token: str) -> bool:
        """
        Logout user by blacklisting their JWT token in Redis.

        Adds the token to a Redis-based blacklist with expiration matching
        the token's remaining validity period. This ensures that even if
        someone has the token, it cannot be used after logout.

        Args:
            token: JWT access token to blacklist

        Returns:
            True if logout successful, False otherwise
        """
        try:
            # Decode token to get expiration time
            payload = decode_token(token)

            if not payload:
                logger.warning("Logout failed: invalid token")
                return False

            # Calculate remaining time until token expiry
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                remaining_seconds = int((exp_datetime - datetime.utcnow()).total_seconds())

                # Only blacklist if token hasn't expired yet
                if remaining_seconds > 0:
                    # Store token in Redis blacklist with expiration
                    blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
                    await self.redis_client.setex(
                        blacklist_key,
                        remaining_seconds,
                        "1"  # Value doesn't matter, just the key existence
                    )

                    logger.info(f"Token blacklisted successfully for user: {payload.get('sub')}")
                    return True

            logger.info("Token already expired, logout successful")
            return True

        except JWTError as e:
            logger.error(f"Logout error: invalid token - {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False

    async def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted in Redis.

        Args:
            token: JWT token to check

        Returns:
            True if token is blacklisted, False otherwise
        """
        try:
            blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
            result = await self.redis_client.exists(blacklist_key)
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking token blacklist: {str(e)}")
            # On error, assume token is valid to avoid blocking legitimate users
            return False

    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a JWT token with comprehensive checks.

        Performs the following validations:
        1. JWT signature verification
        2. Expiration time check
        3. Token blacklist check (for logged out tokens)

        Args:
            token: JWT token to validate

        Returns:
            Token payload if valid, None otherwise
        """
        try:
            # Check if token is blacklisted
            if await self.is_token_blacklisted(token):
                logger.warning("Token validation failed: token is blacklisted")
                return None

            # Decode and validate token (includes signature and expiry check)
            payload = decode_token(token)

            if not payload:
                logger.warning("Token validation failed: invalid payload")
                return None

            logger.debug("Token validated successfully")
            return payload

        except JWTError as e:
            logger.warning(f"Token validation failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return None

    async def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Generate a new access token using a valid refresh token.

        Args:
            refresh_token: Valid JWT refresh token

        Returns:
            New access token if refresh successful, None otherwise
        """
        try:
            # Validate refresh token
            payload = await self.validate_token(refresh_token)

            if not payload:
                logger.warning("Token refresh failed: invalid refresh token")
                return None

            # Check token type
            if payload.get("typ") != "refresh":
                logger.warning("Token refresh failed: not a refresh token")
                return None

            # Generate new access token with same user data
            new_token_data = {
                "sub": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "role": payload.get("role"),
            }

            new_access_token = create_access_token(
                data=new_token_data,
                expires_delta=timedelta(hours=24)
            )

            logger.info(f"Access token refreshed for user: {payload.get('sub')}")
            return new_access_token

        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return None

    async def get_current_user(self, token: str) -> Optional[User]:
        """
        Get the current user from a valid JWT token.

        Args:
            token: JWT access token

        Returns:
            User object if token is valid, None otherwise
        """
        try:
            # Validate token
            payload = await self.validate_token(token)

            if not payload:
                return None

            # Get user from database
            user_email = payload.get("sub")
            if not user_email:
                logger.warning("Token validation failed: missing subject")
                return None

            result = await self.db.execute(
                select(User).where(User.email == user_email)
            )
            user = result.scalar_one_or_none()

            if not user or not user.is_active:
                logger.warning(f"User not found or inactive: {user_email}")
                return None

            return user

        except Exception as e:
            logger.error(f"Get current user error: {str(e)}")
            return None
