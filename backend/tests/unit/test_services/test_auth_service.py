"""
Unit tests for AuthService.

Tests authentication service including login, logout, token management,
and session handling with Redis-based token blacklist.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from services.auth_service import AuthService, AuthenticationError
from models.user import User, UserRole
from core.security import hash_password


@pytest.mark.unit
@pytest.mark.asyncio
class TestAuthService:
    """Unit tests for AuthService."""
    
    async def test_login_success(self, session, admin_user, clean_redis):
        """Test successful user login."""
        auth_service = AuthService(session)
        
        result = await auth_service.login(
            email="admin@test.com",
            password="Admin123!@#"
        )
        
        assert "access_token" in result
        assert "refresh_token" in result
        assert "token_type" in result
        assert result["token_type"] == "bearer"
        assert "user" in result
        assert result["user"]["email"] == "admin@test.com"
        assert result["user"]["role"] == "admin"
    
    async def test_login_invalid_email(self, session, clean_redis):
        """Test login with invalid email."""
        auth_service = AuthService(session)
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login(
                email="nonexistent@test.com",
                password="SomePassword123!"
            )
        
        assert "Invalid email or password" in str(exc_info.value)
    
    async def test_login_invalid_password(self, session, admin_user, clean_redis):
        """Test login with invalid password."""
        auth_service = AuthService(session)
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login(
                email="admin@test.com",
                password="WrongPassword123!"
            )
        
        assert "Invalid email or password" in str(exc_info.value)
    
    async def test_login_inactive_user(self, session, inactive_user, clean_redis):
        """Test login with inactive user account."""
        auth_service = AuthService(session)
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login(
                email="inactive@test.com",
                password="Test123!@#"
            )
        
        assert "Account is inactive" in str(exc_info.value)
    
    async def test_logout_success(self, session, admin_user, clean_redis):
        """Test successful user logout."""
        auth_service = AuthService(session)
        
        # First login to get a token
        login_result = await auth_service.login(
            email="admin@test.com",
            password="Admin123!@#"
        )
        access_token = login_result["access_token"]
        
        # Now logout
        result = await auth_service.logout(access_token)
        
        assert result is True
        
        # Verify token is blacklisted
        is_blacklisted = await auth_service.is_token_blacklisted(access_token)
        assert is_blacklisted is True
    
    async def test_validate_token_valid(self, session, admin_user, clean_redis):
        """Test token validation with valid token."""
        auth_service = AuthService(session)

        # Login to get a valid token
        login_result = await auth_service.login(
            email="admin@test.com",
            password="Admin123!@#"
        )
        access_token = login_result["access_token"]

        # Validate the token
        payload = await auth_service.validate_token(access_token)

        assert payload is not None
        assert "sub" in payload  # User email
        assert payload["sub"] == "admin@test.com"

    async def test_validate_token_blacklisted(self, session, admin_user, clean_redis):
        """Test token validation with blacklisted token."""
        auth_service = AuthService(session)

        # Login and logout
        login_result = await auth_service.login(
            email="admin@test.com",
            password="Admin123!@#"
        )
        access_token = login_result["access_token"]
        await auth_service.logout(access_token)

        # Try to validate blacklisted token
        payload = await auth_service.validate_token(access_token)

        # Should return None for blacklisted token
        assert payload is None

    async def test_refresh_token_success(self, session, admin_user, clean_redis):
        """Test successful token refresh."""
        auth_service = AuthService(session)

        # Login to get tokens
        login_result = await auth_service.login(
            email="admin@test.com",
            password="Admin123!@#"
        )
        refresh_token = login_result["refresh_token"]
        old_access_token = login_result["access_token"]

        # Refresh the token
        new_access_token = await auth_service.refresh_access_token(refresh_token)

        assert new_access_token is not None
        assert isinstance(new_access_token, str)
        assert new_access_token != old_access_token
