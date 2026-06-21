"""
Authentication Request/Response Schemas

This module defines Pydantic schemas for authentication API endpoints
including request validation and response models for login, register,
and token management.
"""

import re
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """
    Request schema for user registration.
    
    Validates:
    - Email format and uniqueness (enforced at API level)
    - Password strength (min 8 chars, complexity requirements)
    """
    email: EmailStr = Field(
        ...,
        description="User's email address (must be unique)",
        examples=["admin@example.com"]
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password (min 8 chars, must include uppercase, lowercase, digit, and special char)",
        examples=["SecurePass123!"]
    )
    role: Optional[str] = Field(
        default="user",
        description="User role (admin or user)",
        examples=["user", "admin"]
    )
    
    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """
        Validate password complexity requirements.
        
        Requirements:
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character (!@#$%^&*(),.?":{}|<>)')
        
        return v
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is either 'admin' or 'user'."""
        if v not in ['admin', 'user']:
            raise ValueError('Role must be either "admin" or "user"')
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "admin@example.com",
                    "password": "SecurePass123!",
                    "role": "admin"
                }
            ]
        }
    }


class LoginRequest(BaseModel):
    """Request schema for user login."""
    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["admin@example.com"]
    )
    password: str = Field(
        ...,
        description="User's password",
        examples=["SecurePass123!"]
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "admin@example.com",
                    "password": "SecurePass123!"
                }
            ]
        }
    }


class UserInfo(BaseModel):
    """User information included in auth responses."""
    id: int = Field(..., description="User ID", examples=[1])
    email: str = Field(..., description="User email", examples=["admin@example.com"])
    role: str = Field(..., description="User role", examples=["admin", "user"])


class TokenResponse(BaseModel):
    """Response schema for successful authentication."""
    access_token: str = Field(
        ...,
        description="JWT access token (24-hour expiry)",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token (7-day expiry)",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
        examples=["bearer"]
    )
    user: UserInfo = Field(
        ...,
        description="User information"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBleGFtcGxlLmNvbSIsInVzZXJfaWQiOjEsInJvbGUiOiJhZG1pbiIsImV4cCI6MTcwOTI4NDgwMCwiaWF0IjoxNzA5MTk4NDAwLCJ0eXAiOiJhY2Nlc3MifQ...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBleGFtcGxlLmNvbSIsInVzZXJfaWQiOjEsInJvbGUiOiJhZG1pbiIsImV4cCI6MTcwOTgwMzIwMCwiaWF0IjoxNzA5MTk4NDAwLCJ0eXAiOiJyZWZyZXNoIn0...",
                    "token_type": "bearer",
                    "user": {
                        "id": 1,
                        "email": "admin@example.com",
                        "role": "admin"
                    }
                }
            ]
        }
    }


class UserResponse(BaseModel):
    """Response schema for user information."""
    id: int = Field(..., description="User ID", examples=[1])
    email: str = Field(..., description="User's email address", examples=["admin@example.com"])
    role: str = Field(..., description="User role", examples=["admin", "user"])
    is_active: bool = Field(..., description="Whether the user account is active", examples=[True])
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "email": "admin@example.com",
                    "role": "admin",
                    "is_active": True
                }
            ]
        }
    }
