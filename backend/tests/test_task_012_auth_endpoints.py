"""
Tests for Authentication API Endpoints (Task-012)

This test module validates:
- User registration endpoint with validation
- User login endpoint with JWT tokens and cookies
- User logout endpoint
- Get current user profile endpoint
- Password complexity requirements
- Email validation and uniqueness
- Authentication middleware integration
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from core.security import hash_password


# ========== Test Data ==========

VALID_EMAIL = "testuser@example.com"
VALID_PASSWORD = "SecurePass123!"
DUPLICATE_EMAIL = "duplicate@example.com"
INACTIVE_EMAIL = "inactive@example.com"
ADMIN_EMAIL = "admin@example.com"


# ========== Fixtures ==========

@pytest_asyncio.fixture
async def async_client(app, db_session):
    """Create async HTTP client for API testing."""
    # Patch get_db to return our test session
    from core.database import get_db

    async def override_get_db():
        yield db_session

    from main import app as main_app
    main_app.dependency_overrides[get_db] = override_get_db

    # Use ASGITransport to wrap the FastAPI app
    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup
    main_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession):
    """Create an active user in the database for testing."""
    user = User(
        email=DUPLICATE_EMAIL,
        password_hash=hash_password(VALID_PASSWORD),
        role=UserRole.USER,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession):
    """Create an inactive user in the database for testing."""
    user = User(
        email=INACTIVE_EMAIL,
        password_hash=hash_password(VALID_PASSWORD),
        role=UserRole.USER,
        is_active=False
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Create an admin user in the database for testing."""
    user = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(VALID_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ========== Registration Tests ==========

@pytest.mark.asyncio
async def test_register_valid_credentials(async_client: AsyncClient, db_session: AsyncSession):
    """TC-001: Register with valid credentials."""
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": VALID_EMAIL,
            "password": VALID_PASSWORD,
            "role": "user"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == VALID_EMAIL
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_invalid_email(async_client: AsyncClient):
    """TC-002: Register with invalid email formats."""
    invalid_emails = [
        "invalid-email",
        "invalid@",
        "@example.com",
        ""
    ]
    
    for email in invalid_emails:
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": VALID_PASSWORD,
                "role": "user"
            }
        )
        assert response.status_code == 422, f"Expected 422 for email: {email}"


@pytest.mark.asyncio
async def test_register_weak_password(async_client: AsyncClient):
    """TC-003: Register with weak passwords."""
    weak_passwords = [
        ("short1!", "too short"),
        ("nouppercase1!", "no uppercase"),
        ("NOLOWERCASE1!", "no lowercase"),
        ("NoDigits!!", "no digit"),
        ("NoSpecial123", "no special char"),
    ]

    for password, reason in weak_passwords:
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "weakpass@example.com",
                "password": password,
                "role": "user"
            }
        )
        assert response.status_code == 422, f"Expected 422 for {reason}: {password}"


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient, existing_user: User):
    """TC-004: Register with duplicate email."""
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": DUPLICATE_EMAIL,
            "password": VALID_PASSWORD,
            "role": "user"
        }
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


# ========== Login Tests ==========

@pytest.mark.asyncio
async def test_login_valid_credentials(async_client: AsyncClient, existing_user: User):
    """TC-005: Login with valid credentials."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": DUPLICATE_EMAIL,
            "password": VALID_PASSWORD
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Verify cookie is set
    assert "auth_token" in response.cookies or "set-cookie" in response.headers


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient, existing_user: User):
    """TC-006: Login with invalid password."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": DUPLICATE_EMAIL,
            "password": "WrongPassword123!"
        }
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    """TC-006: Login with non-existent email."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": VALID_PASSWORD
        }
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_account(async_client: AsyncClient, inactive_user: User):
    """TC-007: Login with inactive account."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": INACTIVE_EMAIL,
            "password": VALID_PASSWORD
        }
    )

    # Implementation returns 401 for inactive accounts (via AuthenticationError)
    assert response.status_code == 401
    assert "inactive" in response.json()["detail"].lower()


# ========== Logout Tests ==========

@pytest.mark.asyncio
async def test_logout_success(async_client: AsyncClient, existing_user: User):
    """TC-008: Logout successfully."""
    # First login to get token
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": DUPLICATE_EMAIL,
            "password": VALID_PASSWORD
        }
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Now logout
    response = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "message" in data or "detail" in data


@pytest.mark.asyncio
async def test_logout_without_authentication(async_client: AsyncClient):
    """TC-009: Logout without authentication."""
    response = await async_client.post("/api/v1/auth/logout")

    assert response.status_code == 401


# ========== Get Current User Tests ==========

@pytest.mark.asyncio
async def test_get_current_user_success(async_client: AsyncClient, existing_user: User):
    """TC-010: Get current user profile."""
    # First login to get token
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": DUPLICATE_EMAIL,
            "password": VALID_PASSWORD
        }
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Get profile
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == DUPLICATE_EMAIL
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_get_profile_without_authentication(async_client: AsyncClient):
    """TC-011: Get profile without authentication."""
    response = await async_client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_invalid_token(async_client: AsyncClient):
    """TC-012: Get profile with invalid token."""
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token_string"}
    )

    assert response.status_code == 401


# ========== Password Complexity Tests ==========

@pytest.mark.asyncio
async def test_password_complexity_validation(async_client: AsyncClient):
    """TC-013: Test each password complexity requirement individually."""
    password_tests = [
        ("lowercase123!", "no uppercase"),
        ("UPPERCASE123!", "no lowercase"),
        ("NoDigits!!", "no digit"),
        ("NoSpecial123", "no special char"),
        ("Short1!", "too short"),
    ]

    for password, violation in password_tests:
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": f"test_{violation.replace(' ', '_')}@example.com",
                "password": password,
                "role": "user"
            }
        )
        assert response.status_code == 422, f"Expected 422 for violation: {violation}"


# ========== Email Case Sensitivity Tests ==========

@pytest.mark.asyncio
async def test_email_case_sensitivity(async_client: AsyncClient, db_session: AsyncSession):
    """TC-014: Test email case sensitivity."""
    # Create user with mixed case email
    response1 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "Test@Example.com",
            "password": VALID_PASSWORD,
            "role": "user"
        }
    )
    assert response1.status_code == 201

    # Try to create another user with different case
    response2 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": VALID_PASSWORD,
            "role": "user"
        }
    )
    # Emails are case-sensitive, so this should succeed
    assert response2.status_code == 201


# ========== Role Validation Tests ==========

@pytest.mark.asyncio
async def test_role_validation(async_client: AsyncClient):
    """TC-015: Test role validation."""
    # Test admin role
    response1 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "newadmin@example.com",
            "password": VALID_PASSWORD,
            "role": "admin"
        }
    )
    assert response1.status_code == 201
    assert response1.json()["role"] == "admin"

    # Test user role
    response2 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": VALID_PASSWORD,
            "role": "user"
        }
    )
    assert response2.status_code == 201
    assert response2.json()["role"] == "user"

    # Test default role (when not specified)
    response3 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "defaultuser@example.com",
            "password": VALID_PASSWORD
        }
    )
    assert response3.status_code == 201
    # Should default to "user"
    assert response3.json()["role"] == "user"

