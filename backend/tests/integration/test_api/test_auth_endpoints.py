"""
Integration tests for Authentication API Endpoints.

Tests complete authentication flow including registration, login,
logout, and user profile retrieval via HTTP API.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestAuthEndpoints:
    """Integration tests for authentication endpoints."""
    
    def test_register_success(self, client, session):
        """Test successful user registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "NewUser123!@#",
                "role": "user"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
    
    def test_register_duplicate_email(self, client, session, admin_user):
        """Test registration with duplicate email."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin@test.com",  # Already exists
                "password": "Test123!@#",
                "role": "user"
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_invalid_email(self, client):
        """Test registration with invalid email format."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "Test123!@#",
                "role": "user"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_register_weak_password(self, client):
        """Test registration with weak password."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@test.com",
                "password": "weak",  # Too weak
                "role": "user"
            }
        )
        
        assert response.status_code == 422
    
    def test_login_success(self, client, admin_user, clean_redis):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self, client, clean_redis):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong@test.com",
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 401
    
    def test_login_inactive_account(self, client, inactive_user, clean_redis):
        """Test login with inactive account."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "inactive@test.com",
                "password": "Test123!@#"
            }
        )
        
        assert response.status_code == 403
    
    def test_logout_success(self, client, admin_user, clean_redis):
        """Test successful logout."""
        # First login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Then logout
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
    
    def test_get_profile_authenticated(self, client, admin_user, clean_redis):
        """Test retrieving user profile when authenticated."""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Get profile
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
    
    def test_get_profile_unauthenticated(self, client):
        """Test retrieving profile without authentication."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
