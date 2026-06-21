"""
Security Module for Password Hashing and JWT Token Management

This module provides cryptographic utilities for password hashing using bcrypt
and JWT token generation and validation with configurable expiration times.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
from jose import JWTError, jwt

from core.config import settings

# Logger
logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt with cost factor 12.

    The bcrypt algorithm is specifically designed for password hashing and
    includes automatic salting and protection against rainbow table attacks.
    Cost factor 12 provides a good balance between security and performance.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string suitable for database storage

    Example:
        >>> hashed = hash_password("mySecurePassword123")
        >>> verify_password("mySecurePassword123", hashed)
        True
    """
    # Convert password to bytes and hash with bcrypt
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    logger.debug("Password hashed successfully")
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    Uses constant-time comparison to prevent timing attacks.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
        
    Example:
        >>> hashed = hash_password("myPassword")
        >>> verify_password("myPassword", hashed)
        True
        >>> verify_password("wrongPassword", hashed)
        False
    """
    try:
        # Convert inputs to bytes
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')

        # Use bcrypt to verify
        is_valid = bcrypt.checkpw(password_bytes, hashed_bytes)
        logger.debug(f"Password verification: {'successful' if is_valid else 'failed'}")
        return is_valid
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token with configurable expiration time.
    
    The token includes:
    - User data (typically user_id, email, role)
    - Expiration timestamp (exp claim)
    - Issued at timestamp (iat claim)
    - Token type (typ claim)
    
    Args:
        data: Dictionary of claims to encode in the token (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration time delta.
                      Defaults to 24 hours as per requirements.
        
    Returns:
        Encoded JWT token string
        
    Example:
        >>> token = create_access_token({"sub": "user@example.com", "role": "admin"})
        >>> # Returns a JWT token valid for 24 hours
    """
    to_encode = data.copy()
    
    # Set expiration time (default 24 hours as per requirements)
    if expires_delta is None:
        expires_delta = timedelta(hours=24)
    
    expire = datetime.utcnow() + expires_delta
    
    # Add standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "typ": "access"
    })
    
    # Encode JWT token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    logger.debug(f"Access token created with expiration: {expire}")
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token with longer expiration time.
    
    Refresh tokens are used to obtain new access tokens without re-authentication.
    They have a longer validity period (default 7 days).
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time delta.
                      Defaults to 7 days from settings.
        
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    
    # Set expiration time (default from settings)
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    expire = datetime.utcnow() + expires_delta

    # Add standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "typ": "refresh"
    })

    # Encode JWT token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    logger.debug(f"Refresh token created with expiration: {expire}")
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Performs comprehensive validation including:
    - Signature verification using SECRET_KEY
    - Expiration time check
    - Token structure validation

    Args:
        token: JWT token string to decode

    Returns:
        Dictionary containing token payload if valid, None otherwise

    Raises:
        JWTError: If token is invalid, expired, or malformed

    Example:
        >>> token = create_access_token({"sub": "user@example.com"})
        >>> payload = decode_token(token)
        >>> payload["sub"]
        'user@example.com'
    """
    try:
        # Decode and validate token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        logger.debug("Token decoded and validated successfully")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise JWTError("Token has expired")

    except jwt.JWTError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise JWTError(f"Invalid token: {str(e)}")

    except Exception as e:
        logger.error(f"Token decoding error: {str(e)}")
        raise JWTError(f"Token decoding failed: {str(e)}")


def verify_token(token: str) -> bool:
    """
    Verify if a JWT token is valid without decoding the payload.

    Useful for quick validation checks without needing the payload data.

    Args:
        token: JWT token string to verify

    Returns:
        True if token is valid and not expired, False otherwise
    """
    try:
        decode_token(token)
        return True
    except JWTError:
        return False


def get_token_expiration(token: str) -> Optional[datetime]:
    """
    Extract the expiration timestamp from a JWT token.

    Args:
        token: JWT token string

    Returns:
        Expiration datetime if token is valid, None otherwise
    """
    try:
        payload = decode_token(token)
        exp_timestamp = payload.get("exp")

        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp)

        return None

    except JWTError:
        return None
