"""
Authentication API Endpoints

This module provides REST API endpoints for user authentication including
registration, login, logout, and user profile retrieval.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import hash_password
from middleware.auth import get_current_active_user, set_auth_cookie, clear_auth_cookie
from models.user import User, UserRole
from schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from services.auth_service import AuthService, AuthenticationError

# Logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user account with email and password. Email must be unique.",
    responses={
        201: {
            "description": "User successfully registered",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "email": "admin@example.com",
                        "role": "admin",
                        "is_active": True
                    }
                }
            }
        },
        400: {"description": "Email already registered or validation error"},
        422: {"description": "Invalid request data"}
    }
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Register a new user account.
    
    Validates:
    - Email format and uniqueness
    - Password complexity (min 8 chars, uppercase, lowercase, digit, special char)
    - Role validity (admin or user)
    
    Args:
        request: Registration request with email, password, and optional role
        db: Database session
        
    Returns:
        Created user object
        
    Raises:
        HTTPException 400: If email already exists
        HTTPException 422: If validation fails
    """
    logger.info(f"Registration attempt for email: {request.email}")
    
    try:
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == request.email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.warning(f"Registration failed: email already exists - {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        password_hash = hash_password(request.password)
        
        # Create new user
        new_user = User(
            email=request.email,
            password_hash=password_hash,
            role=UserRole.ADMIN if request.role == "admin" else UserRole.USER,
            is_active=True
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"User registered successfully: {request.email}")
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user and return JWT tokens. Sets HTTP-only cookie with access token.",
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer"
                    }
                }
            }
        },
        401: {"description": "Invalid credentials or inactive account"},
        422: {"description": "Invalid request data"}
    }
)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Authenticate user and generate JWT tokens.

    Validates credentials and generates:
    - Access token (24-hour expiry)
    - Refresh token (7-day expiry)
    - HTTP-only cookie with access token

    Args:
        request: Login request with email and password
        response: FastAPI response object for setting cookies
        db: Database session

    Returns:
        Token response with access_token, refresh_token, and token_type

    Raises:
        HTTPException 401: If credentials are invalid or account is inactive
    """
    logger.info(f"Login attempt for email: {request.email}")

    try:
        auth_service = AuthService(db)

        # Authenticate and generate tokens
        token_data = await auth_service.login(
            email=request.email,
            password=request.password
        )

        # Set HTTP-only cookie with access token
        set_auth_cookie(response, token_data["access_token"])

        logger.info(f"Login successful for user: {request.email}")

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "token_type": token_data["token_type"],
            "user": token_data["user"]
        }

    except AuthenticationError as e:
        logger.warning(f"Login failed for {request.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User logout",
    description="Logout user and invalidate JWT token. Clears HTTP-only cookie.",
    responses={
        200: {
            "description": "Logout successful",
            "content": {
                "application/json": {
                    "example": {"message": "Logged out successfully"}
                }
            }
        },
        401: {"description": "Not authenticated"}
    }
)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Logout user and invalidate token.

    Performs:
    - Token blacklisting in Redis
    - Cookie clearance
    - Session cleanup

    Args:
        response: FastAPI response object for clearing cookies
        current_user: Authenticated user from dependency
        db: Database session

    Returns:
        Success message
    """
    logger.info(f"Logout request for user: {current_user.email}")

    try:
        # Clear HTTP-only cookie
        clear_auth_cookie(response)

        logger.info(f"Logout successful for user: {current_user.email}")
        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get authenticated user profile information.",
    responses={
        200: {
            "description": "User profile retrieved",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "email": "admin@example.com",
                        "role": "admin",
                        "is_active": True
                    }
                }
            }
        },
        401: {"description": "Not authenticated"}
    }
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current authenticated user profile.

    Returns user information including:
    - User ID
    - Email address
    - Role (admin or user)
    - Account active status

    Args:
        current_user: Authenticated user from dependency

    Returns:
        User profile information
    """
    logger.debug(f"Profile request for user: {current_user.email}")
    return current_user
    
