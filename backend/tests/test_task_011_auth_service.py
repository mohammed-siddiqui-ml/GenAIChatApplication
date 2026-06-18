"""
Tests for Authentication Service with JWT (Task-011)

This test module validates:
- Password hashing with bcrypt cost factor 12
- JWT token generation and validation
- User authentication flow
- Token blacklist functionality in Redis
- HTTP-only cookie management
- Admin role-based access control
"""

import pytest
import pytest_asyncio
from datetime import timedelta
from jose import jwt as jose_jwt

from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token,
    get_token_expiration,
)
from core.config import settings
from services.auth_service import AuthService, AuthenticationError
from middleware.auth import (
    get_token_from_request,
    set_auth_cookie,
    clear_auth_cookie,
    COOKIE_NAME,
)
from models.user import User, UserRole


# ========== Test Data ==========

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "TestPass123!"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "AdminPass123!"
INACTIVE_EMAIL = "inactive@example.com"
INACTIVE_PASSWORD = "InactivePass123!"


# ========== Password Hashing Tests ==========

def test_hash_password_bcrypt_cost_factor_12():
    """TC-001: Verify bcrypt cost factor 12 is used for password hashing."""
    password = "TestPassword123!"
    hashed = hash_password(password)

    # Verify hash starts with $2b$12$ (bcrypt identifier + cost factor 12)
    assert hashed.startswith("$2b$12$"), "Password hash should use bcrypt cost factor 12"

    # Verify hash length (bcrypt hashes are ~60 characters)
    assert len(hashed) == 60, "Bcrypt hash should be 60 characters"

    # Verify hash is different from plain password
    assert hashed != password, "Hash should not equal plain password"

    # Verify different hashes for same password (random salt)
    hashed2 = hash_password(password)
    assert hashed != hashed2, "Same password should produce different hashes (salted)"


def test_verify_password_success():
    """TC-002: Verify correct password against hash."""
    password = "TestPassword123!"
    hashed = hash_password(password)

    # Verify password matches
    assert verify_password(password, hashed) is True, "Correct password should verify successfully"


def test_verify_password_failure():
    """TC-003: Reject incorrect password."""
    correct_password = "TestPassword123!"
    wrong_password = "WrongPassword!"
    hashed = hash_password(correct_password)

    # Verify wrong password fails
    assert verify_password(wrong_password, hashed) is False, "Wrong password should fail verification"


# ========== JWT Token Creation Tests ==========

def test_create_access_token_24_hour_expiry():
    """TC-004: Create access token with 24-hour expiry."""
    user_data = {"sub": "user123"}
    token = create_access_token(user_data)

    # Decode token without verification to inspect claims
    payload = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    # Verify token type
    assert payload.get("typ") == "access", "Token type should be 'access'"

    # Verify subject
    assert payload.get("sub") == "user123", "Token should contain correct user ID"

    # Verify expiration is ~24 hours (allow 1-minute tolerance)
    exp_timestamp = payload.get("exp")
    iat_timestamp = payload.get("iat")
    assert exp_timestamp is not None, "Token should have expiration claim"
    assert iat_timestamp is not None, "Token should have issued-at claim"

    duration = exp_timestamp - iat_timestamp
    assert 86400 - 60 <= duration <= 86400 + 60, "Access token should expire in ~24 hours (86400 seconds)"


def test_create_refresh_token_7_day_expiry():
    """TC-005: Create refresh token with 7-day expiry."""
    user_data = {"sub": "user123"}
    token = create_refresh_token(user_data)

    # Decode token without verification
    payload = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    # Verify token type
    assert payload.get("typ") == "refresh", "Token type should be 'refresh'"

    # Verify expiration is ~7 days (604800 seconds, allow 1-minute tolerance)
    exp_timestamp = payload.get("exp")
    iat_timestamp = payload.get("iat")
    duration = exp_timestamp - iat_timestamp
    assert 604800 - 60 <= duration <= 604800 + 60, "Refresh token should expire in ~7 days (604800 seconds)"


# ========== JWT Token Validation Tests ==========

def test_decode_valid_token():
    """TC-006: Decode valid token successfully."""
    user_data = {"sub": "user123", "email": "test@example.com"}
    token = create_access_token(user_data)

    # Decode token
    payload = decode_token(token)

    assert payload is not None, "Valid token should decode successfully"
    assert payload.get("sub") == "user123", "Payload should contain correct user ID"
    assert payload.get("email") == "test@example.com", "Payload should contain email"
    assert payload.get("typ") == "access", "Payload should contain token type"
    assert "exp" in payload, "Payload should contain expiration"
    assert "iat" in payload, "Payload should contain issued-at"


def test_reject_expired_token():
    """TC-007: Reject expired token."""
    from jose import JWTError

    user_data = {"sub": "user123"}
    # Create token with -1 hour expiry (already expired)
    token = create_access_token(user_data, expires_delta=timedelta(hours=-1))

    # Attempt to decode expired token should raise JWTError
    with pytest.raises(JWTError):
        decode_token(token)


def test_reject_invalid_signature():
    """TC-008: Reject token with tampered signature."""
    from jose import JWTError

    user_data = {"sub": "user123"}
    token = create_access_token(user_data)

    # Corrupt the signature (change last character)
    corrupted_token = token[:-1] + ("X" if token[-1] != "X" else "Y")

    # Attempt to decode corrupted token should raise JWTError
    with pytest.raises(JWTError):
        decode_token(corrupted_token)


def test_verify_token_valid():
    """Test verify_token returns True for valid token."""
    user_data = {"sub": "user123"}
    token = create_access_token(user_data)

    assert verify_token(token) is True, "Valid token should verify successfully"


def test_verify_token_invalid():
    """Test verify_token returns False for invalid token."""
    assert verify_token("invalid.token.here") is False, "Invalid token should fail verification"


def test_get_token_expiration():
    """Test extracting expiration timestamp from token."""
    from datetime import datetime

    user_data = {"sub": "user123"}
    token = create_access_token(user_data)

    exp_datetime = get_token_expiration(token)

    assert exp_datetime is not None, "Should extract expiration datetime"
    assert exp_datetime > datetime.utcnow(), "Expiration should be in the future"


# ========== Database Fixtures ==========

@pytest_asyncio.fixture(scope='function')
async def test_user(db_session, clean_redis):
    """Create a test user in the database."""
    from models.user import User, UserRole

    # Create test user
    user = User(
        email=TEST_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.USER,
        is_active=True
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture(scope='function')
async def admin_user(db_session, clean_redis):
    """Create an admin user in the database."""
    from models.user import User, UserRole

    # Create admin user
    user = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture(scope='function')
async def inactive_user(db_session, clean_redis):
    """Create an inactive user in the database."""
    from models.user import User, UserRole

    # Create inactive user
    user = User(
        email=INACTIVE_EMAIL,
        password_hash=hash_password(INACTIVE_PASSWORD),
        role=UserRole.USER,
        is_active=False
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


# ========== Authentication Service Tests ==========

@pytest.mark.asyncio
async def test_login_with_valid_credentials(db_session, test_user):
    """TC-009: User login with valid credentials."""
    auth_service = AuthService(db_session)

    # Perform login
    result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)

    # Verify response structure
    assert "access_token" in result, "Response should contain access_token"
    assert "refresh_token" in result, "Response should contain refresh_token"
    assert "token_type" in result, "Response should contain token_type"
    assert "user" in result, "Response should contain user data"

    # Verify token type
    assert result["token_type"] == "bearer", "Token type should be 'bearer'"

    # Verify user data
    assert result["user"]["email"] == TEST_EMAIL, "User email should match"
    assert result["user"]["id"] == test_user.id, "User ID should match"
    assert result["user"]["role"] == "user", "User role should be 'user'"

    # Verify tokens are valid
    access_payload = decode_token(result["access_token"])
    assert access_payload.get("typ") == "access", "Access token should have type 'access'"

    refresh_payload = decode_token(result["refresh_token"])
    assert refresh_payload.get("typ") == "refresh", "Refresh token should have type 'refresh'"


@pytest.mark.asyncio
async def test_login_with_invalid_email(db_session):
    """TC-010: Login with invalid email."""
    auth_service = AuthService(db_session)

    # Attempt login with non-existent email
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await auth_service.login("nonexistent@example.com", "AnyPassword")


@pytest.mark.asyncio
async def test_login_with_invalid_password(db_session, test_user):
    """TC-011: Login with invalid password."""
    auth_service = AuthService(db_session)

    # Attempt login with wrong password
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await auth_service.login(TEST_EMAIL, "WrongPassword")



@pytest.mark.asyncio
async def test_login_with_inactive_user(db_session, inactive_user):
    """TC-012: Login rejected for inactive user."""
    auth_service = AuthService(db_session)

    # Attempt login with inactive user
    with pytest.raises(AuthenticationError, match="inactive"):
        await auth_service.login(INACTIVE_EMAIL, INACTIVE_PASSWORD)


# ========== Token Blacklist Tests ==========

@pytest.mark.asyncio
async def test_logout_adds_token_to_blacklist(db_session, test_user):
    """TC-013: Logout adds token to Redis blacklist."""
    auth_service = AuthService(db_session)

    # Login to get a token
    login_result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)
    access_token = login_result["access_token"]

    # Logout (blacklist the token)
    result = await auth_service.logout(access_token)

    assert result is True, "Logout should succeed"

    # Verify token is blacklisted
    is_blacklisted = await auth_service.is_token_blacklisted(access_token)
    assert is_blacklisted is True, "Token should be in blacklist after logout"


@pytest.mark.asyncio
async def test_blacklisted_token_rejected(db_session, test_user):
    """TC-014: Blacklisted token rejected on validation."""
    auth_service = AuthService(db_session)

    # Login to get a token
    login_result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)
    access_token = login_result["access_token"]

    # Logout (blacklist the token)
    await auth_service.logout(access_token)

    # Attempt to validate blacklisted token
    payload = await auth_service.validate_token(access_token)

    assert payload is None, "Blacklisted token should fail validation"


# ========== Token Refresh Tests ==========

@pytest.mark.asyncio
async def test_refresh_access_token_with_valid_refresh_token(db_session, test_user):
    """TC-015: Refresh access token with valid refresh token."""
    auth_service = AuthService(db_session)

    # Login to get tokens
    login_result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)
    refresh_token = login_result["refresh_token"]

    # Refresh access token
    new_access_token = await auth_service.refresh_access_token(refresh_token)

    assert new_access_token is not None, "Should generate new access token"
    assert new_access_token != refresh_token, "New token should be different from refresh token"

    # Verify new token is valid and has correct type
    payload = decode_token(new_access_token)
    assert payload.get("typ") == "access", "New token should be access type"
    assert payload.get("sub") == TEST_EMAIL, "New token should contain same user data"


@pytest.mark.asyncio
async def test_reject_refresh_with_access_token(db_session, test_user):
    """TC-016: Reject refresh with access token instead of refresh token."""
    auth_service = AuthService(db_session)

    # Login to get tokens
    login_result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)
    access_token = login_result["access_token"]

    # Attempt to refresh with access token (wrong type)
    new_token = await auth_service.refresh_access_token(access_token)

    assert new_token is None, "Should reject access token for refresh operation"


# ========== HTTP Cookie Tests ==========

def test_set_auth_cookie():
    """TC-023: Set auth cookie with security flags."""
    from fastapi import Response

    response = Response()
    token = "test.jwt.token"

    set_auth_cookie(response, token)

    # Verify cookie is set (check in raw headers)
    cookie_header = response.headers.get("set-cookie", "")

    assert COOKIE_NAME in cookie_header, "Cookie should be set with correct name"
    assert "HttpOnly" in cookie_header, "Cookie should have HttpOnly flag"
    assert "SameSite=lax" in cookie_header, "Cookie should have SameSite=lax"
    assert "Max-Age" in cookie_header, "Cookie should have Max-Age"


def test_clear_auth_cookie():
    """TC-024: Clear auth cookie on logout."""
    from fastapi import Response

    response = Response()

    clear_auth_cookie(response)

    # Verify cookie is cleared (check in raw headers)
    cookie_header = response.headers.get("set-cookie", "")

    assert COOKIE_NAME in cookie_header, "Cookie should be referenced for deletion"
    # Cookie deletion is indicated by Max-Age=0 or expires in the past


# ========== Middleware Tests ==========

@pytest.mark.asyncio
async def test_get_current_user_from_valid_token(db_session, test_user):
    """TC-019: Get current user from valid token."""
    auth_service = AuthService(db_session)

    # Login to get a token
    login_result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)
    access_token = login_result["access_token"]

    # Get current user from token
    user = await auth_service.get_current_user(access_token)

    assert user is not None, "Should return user for valid token"
    assert user.email == TEST_EMAIL, "User email should match"
    assert user.id == test_user.id, "User ID should match"
    assert user.is_active is True, "User should be active"


@pytest.mark.asyncio
async def test_get_current_user_with_invalid_token(db_session):
    """TC-020: Return None for invalid token."""
    auth_service = AuthService(db_session)

    # Attempt to get user with invalid token
    user = await auth_service.get_current_user("invalid.token.here")

    assert user is None, "Should return None for invalid token"


@pytest.mark.asyncio
async def test_admin_user_has_admin_role(admin_user):
    """TC-021: Verify admin user has admin role."""
    assert admin_user.role == UserRole.ADMIN, "Admin user should have ADMIN role"
    assert admin_user.is_admin() is True, "is_admin() should return True for admin user"


@pytest.mark.asyncio
async def test_regular_user_not_admin(test_user):
    """TC-022: Verify regular user is not admin."""
    assert test_user.role == UserRole.USER, "Regular user should have USER role"
    assert test_user.is_admin() is False, "is_admin() should return False for regular user"


# ========== Integration Tests ==========

@pytest.mark.asyncio
async def test_full_authentication_flow(db_session, test_user):
    """Test complete authentication flow: login -> validate -> logout."""
    auth_service = AuthService(db_session)

    # Step 1: Login
    login_result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)
    access_token = login_result["access_token"]

    # Step 2: Validate token
    payload = await auth_service.validate_token(access_token)
    assert payload is not None, "Token should be valid after login"

    # Step 3: Get current user
    user = await auth_service.get_current_user(access_token)
    assert user.email == TEST_EMAIL, "Should retrieve correct user"

    # Step 4: Logout
    logout_result = await auth_service.logout(access_token)
    assert logout_result is True, "Logout should succeed"

    # Step 5: Validate token again (should fail)
    payload_after_logout = await auth_service.validate_token(access_token)
    assert payload_after_logout is None, "Token should be invalid after logout"


@pytest.mark.asyncio
async def test_token_refresh_flow(db_session, test_user):
    """Test token refresh flow: login -> refresh -> validate new token."""
    import asyncio
    auth_service = AuthService(db_session)

    # Step 1: Login
    login_result = await auth_service.login(TEST_EMAIL, TEST_PASSWORD)
    refresh_token = login_result["refresh_token"]
    old_access_token = login_result["access_token"]

    # Wait 1 second to ensure different timestamp
    await asyncio.sleep(1)

    # Step 2: Refresh access token
    new_access_token = await auth_service.refresh_access_token(refresh_token)
    assert new_access_token is not None, "Should generate new access token"
    assert new_access_token != old_access_token, "New token should be different"

    # Step 3: Validate new token
    payload = await auth_service.validate_token(new_access_token)
    assert payload is not None, "New token should be valid"
    assert payload.get("sub") == TEST_EMAIL, "New token should contain correct user"

