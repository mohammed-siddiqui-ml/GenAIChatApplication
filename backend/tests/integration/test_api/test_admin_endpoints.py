"""
Integration tests for Admin API Endpoints.

Tests data source management endpoints including CRUD operations
for Confluence, JIRA, and onboarding data sources.
"""

import pytest


@pytest.mark.integration
class TestAdminEndpoints:
    """Integration tests for admin endpoints."""
    
    def test_create_data_source_authenticated(self, client, admin_user, clean_redis):
        """Test creating data source as admin."""
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Create data source
        response = client.post(
            "/api/v1/admin/data-sources",
            json={
                "name": "Test Source",
                "source_type": "confluence",
                "config": {
                    "url": "https://confluence.example.com",
                    "username": "test",
                    "api_token": "token123",
                    "space_key": "TEST"
                },
                "sync_schedule": "0 0 * * *"
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code in [200, 201]
    
    def test_create_data_source_unauthorized(self, client, regular_user, clean_redis):
        """Test creating data source as non-admin."""
        # Login as regular user
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "user@test.com",
                "password": "User123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Try to create data source
        response = client.post(
            "/api/v1/admin/data-sources",
            json={
                "name": "Test Source",
                "source_type": "confluence",
                "config": {},
                "sync_schedule": "0 0 * * *"
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 403
    
    def test_list_data_sources(self, client, admin_user, confluence_data_source, clean_redis):
        """Test listing all data sources."""
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # List data sources
        response = client.get(
            "/api/v1/admin/data-sources",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_data_source_by_id(self, client, admin_user, confluence_data_source, clean_redis):
        """Test retrieving a specific data source."""
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Get data source
        response = client.get(
            f"/api/v1/admin/data-sources/{confluence_data_source.id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == confluence_data_source.id
    
    def test_update_data_source(self, client, admin_user, confluence_data_source, clean_redis):
        """Test updating a data source."""
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Update data source
        response = client.put(
            f"/api/v1/admin/data-sources/{confluence_data_source.id}",
            json={
                "name": "Updated Source Name",
                "sync_schedule": "0 12 * * *"
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
    
    def test_delete_data_source(self, client, admin_user, confluence_data_source, clean_redis):
        """Test deleting a data source."""
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Delete data source
        response = client.delete(
            f"/api/v1/admin/data-sources/{confluence_data_source.id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code in [200, 204]
    
    def test_trigger_ingestion(self, client, admin_user, confluence_data_source, clean_redis):
        """Test manually triggering data ingestion."""
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!@#"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Trigger ingestion
        response = client.post(
            f"/api/v1/admin/data-sources/{confluence_data_source.id}/ingest",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Should return task ID or success message
        assert response.status_code in [200, 202]
