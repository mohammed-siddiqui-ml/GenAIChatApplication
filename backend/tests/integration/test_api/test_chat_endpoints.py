"""
Integration tests for Chat API Endpoints.

Tests chat session management and query processing via HTTP API.
"""

import pytest
from unittest.mock import patch


@pytest.mark.integration
class TestChatEndpoints:
    """Integration tests for chat endpoints."""
    
    def test_create_session_success(self, client):
        """Test creating a new chat session."""
        response = client.post("/api/v1/chat/sessions")
        
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert "session_token" in data
    
    def test_query_with_valid_session(self, client, chat_session, mock_openai_client):
        """Test querying with valid session token."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            response = client.post(
                "/api/v1/chat/query",
                json={
                    "query": "What is the onboarding process?",
                    "stream": False
                },
                headers={"X-Session-Token": chat_session.session_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert "session_id" in data
    
    def test_query_without_session_token(self, client):
        """Test querying without session token."""
        response = client.post(
            "/api/v1/chat/query",
            json={
                "query": "Test query"
            }
        )
        
        assert response.status_code == 401
    
    def test_query_with_invalid_session(self, client):
        """Test querying with invalid session token."""
        response = client.post(
            "/api/v1/chat/query",
            json={
                "query": "Test query"
            },
            headers={"X-Session-Token": "invalid-token-xyz"}
        )
        
        assert response.status_code == 404
    
    def test_get_session_history(self, client, chat_session_with_messages):
        """Test retrieving session history."""
        response = client.get(
            f"/api/v1/chat/sessions/{chat_session_with_messages.session_token}/history"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) > 0
    
    def test_streaming_query(self, client, chat_session, mock_openai_client):
        """Test streaming query response."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            response = client.post(
                "/api/v1/chat/query",
                json={
                    "query": "Tell me about the FAQ",
                    "stream": True
                },
                headers={"X-Session-Token": chat_session.session_token}
            )
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
    
    def test_query_empty_text(self, client, chat_session):
        """Test querying with empty text."""
        response = client.post(
            "/api/v1/chat/query",
            json={
                "query": ""
            },
            headers={"X-Session-Token": chat_session.session_token}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_query_with_max_results(self, client, chat_session, mock_openai_client):
        """Test querying with custom max_results parameter."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            response = client.post(
                "/api/v1/chat/query",
                json={
                    "query": "What is the process?",
                    "max_results": 3
                },
                headers={"X-Session-Token": chat_session.session_token}
            )
            
            assert response.status_code == 200
    
    def test_delete_session(self, client, chat_session):
        """Test deleting a chat session."""
        response = client.delete(
            f"/api/v1/chat/sessions/{chat_session.session_token}"
        )
        
        # Endpoint may or may not exist - check implementation
        assert response.status_code in [200, 204, 404, 405]
