"""
Tests for Authorization Middleware with RBAC (Task 013)

Tests cover:
- JWT token extraction from headers and cookies
- User authentication and validation
- Active user checks
- Admin authorization (RBAC)
- Cookie management
- End-to-end route protection
"""

import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from jose import jwt

from middleware.auth import (
    get_token_from_request,
    get_current_user,
    get_current_active_user,
    require_admin,
    set_auth_cookie,
    clear_auth_cookie,
    COOKIE_NAME,
)
from models.user import User, UserRole
from services.auth_service import AuthService
from core.config import settings
from core.security import create_access_token


class TestTokenExtraction:
    """Test Suite A: Token Extraction from Request"""
    
    @pytest.mark.asyncio
    async def test_extract_token_from_header(self):
        """TC-A1: Extract JWT from Authorization header"""
        # Create mock request with Authorization header
        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        
        # Create mock credentials
        from fastapi.security import HTTPAuthorizationCredentials
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="test-jwt-token-123"
        )
        
        # Call function
        token = await get_token_from_request(mock_request, mock_credentials)
        
        # Verify
        assert token == "test-jwt-token-123"
    
    @pytest.mark.asyncio
    async def test_extract_token_from_cookie(self):
        """TC-A2: Extract JWT from HTTP-only cookie"""
        # Create mock request with cookie
        mock_request = Mock(spec=Request)
        mock_request.cookies = {COOKIE_NAME: "Bearer test-cookie-token"}
        
        # Call function (no credentials)
        token = await get_token_from_request(mock_request, None)
        
        # Verify - should strip "Bearer " prefix
        assert token == "test-cookie-token"
    
    @pytest.mark.asyncio
    async def test_missing_token(self):
        """TC-A3: Handle missing token"""
        # Create mock request without token
        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        
        # Call function
        token = await get_token_from_request(mock_request, None)
        
        # Verify
        assert token is None
    
    @pytest.mark.asyncio
    async def test_prioritize_header_over_cookie(self):
        """TC-A5: Prioritize header token over cookie"""
        # Create mock request with both header and cookie
        mock_request = Mock(spec=Request)
        mock_request.cookies = {COOKIE_NAME: "cookie-token"}
        
        from fastapi.security import HTTPAuthorizationCredentials
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="header-token"
        )
        
        # Call function
        token = await get_token_from_request(mock_request, mock_credentials)
        
        # Verify header token is returned
        assert token == "header-token"


class TestUserAuthentication:
    """Test Suite B: User Authentication (get_current_user)"""
    
    @pytest.mark.asyncio
    async def test_authenticate_valid_token(self, session, regular_user):
        """TC-B1: Authenticate user with valid token"""
        # Generate valid token
        token = create_access_token({"sub": regular_user.email})

        # Create mock request
        mock_request = Mock(spec=Request)

        # Call function
        user = await get_current_user(mock_request, session, token)

        # Verify
        assert user is not None
        assert user.email == regular_user.email
        assert user.role == UserRole.USER

    @pytest.mark.asyncio
    async def test_reject_invalid_token(self, session):
        """TC-B2: Reject invalid token signature"""
        # Create invalid token
        invalid_token = "invalid.jwt.token"

        # Create mock request
        mock_request = Mock(spec=Request)

        # Call function and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, session, invalid_token)

        # Verify
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid authentication credentials"

    @pytest.mark.asyncio
    async def test_reject_token_for_nonexistent_user(self, session):
        """TC-B4: Reject token for non-existent user"""
        # Create token for non-existent user
        token = create_access_token({"sub": "deleted@example.com"})

        # Create mock request
        mock_request = Mock(spec=Request)

        # Call function and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, session, token)

        # Verify
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid authentication credentials"

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self, session):
        """Test missing token raises 401"""
        # Create mock request
        mock_request = Mock(spec=Request)

        # Call function with None token
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, session, None)

        # Verify
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"


class TestActiveUserValidation:
    """Test Suite C: Active User Validation"""

    @pytest.mark.asyncio
    async def test_allow_active_user(self, regular_user):
        """TC-C1: Allow active user to proceed"""
        # regular_user fixture is active by default
        user = await get_current_active_user(regular_user)

        # Verify
        assert user == regular_user
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_block_inactive_user(self, inactive_user):
        """TC-C2: Block inactive user with 403"""
        # Call function with inactive user
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(inactive_user)

        # Verify
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Inactive user account"


class TestAdminAuthorization:
    """Test Suite D: Admin Authorization (RBAC)"""

    @pytest.mark.asyncio
    async def test_allow_admin_access(self, admin_user):
        """TC-D1: Allow admin user access"""
        # Call require_admin with admin user
        user = await require_admin(admin_user)

        # Verify
        assert user == admin_user
        assert user.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_block_non_admin_user(self, regular_user):
        """TC-D2: Block non-admin user with 403"""
        # Call require_admin with regular user
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(regular_user)

        # Verify
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Admin access required"

    @pytest.mark.asyncio
    async def test_block_inactive_admin(self, inactive_user):
        """TC-D3: Block inactive admin user"""
        # Change inactive_user to admin role
        inactive_user.role = UserRole.ADMIN

        # Test the dependency chain: require_admin -> get_current_active_user
        # First, the active check should fail
        with pytest.raises(HTTPException) as exc_info:
            # Call get_current_active_user first (which is what require_admin depends on)
            active_user = await get_current_active_user(inactive_user)
            # If it somehow passes (shouldn't), then call require_admin
            await require_admin(active_user)

        # Verify - should fail at active check, not admin check
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Inactive user account"


class TestCookieManagement:
    """Test Suite E: Cookie Management"""

    def test_set_auth_cookie(self):
        """TC-E1: Set authentication cookie with correct attributes"""
        # Create mock response
        mock_response = Mock(spec=Response)
        test_token = "test-jwt-token"

        # Call function
        set_auth_cookie(mock_response, test_token)

        # Verify cookie was set with correct attributes
        mock_response.set_cookie.assert_called_once()
        call_kwargs = mock_response.set_cookie.call_args[1]

        assert call_kwargs['key'] == COOKIE_NAME
        assert call_kwargs['value'] == f"Bearer {test_token}"
        assert call_kwargs['httponly'] is True
        assert call_kwargs['samesite'] == "lax"

    def test_clear_auth_cookie(self):
        """TC-E2: Clear authentication cookie on logout"""
        # Create mock response
        mock_response = Mock(spec=Response)

        # Call function
        clear_auth_cookie(mock_response)

        # Verify cookie was deleted
        mock_response.delete_cookie.assert_called_once()
        call_kwargs = mock_response.delete_cookie.call_args[1]

        assert call_kwargs['key'] == COOKIE_NAME
        assert call_kwargs['httponly'] is True
