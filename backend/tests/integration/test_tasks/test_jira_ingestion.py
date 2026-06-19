"""
Integration tests for JIRA Ingestion Celery Tasks.

Tests JIRA issue ingestion with mocked JIRA API and OpenAI API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import responses


@pytest.mark.integration
@pytest.mark.asyncio
class TestJiraIngestion:
    """Integration tests for JIRA ingestion tasks."""
    
    @responses.activate
    async def test_ingest_jira_issues_success(self, session, jira_data_source, mock_openai_client):
        """Test successful JIRA issue ingestion."""
        # Mock JIRA API response
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/search",
            json={
                "issues": [
                    {
                        "id": "10001",
                        "key": "PROJ-123",
                        "fields": {
                            "summary": "Test Issue",
                            "description": "This is a test issue description",
                            "status": {"name": "Done"},
                            "priority": {"name": "High"},
                            "created": "2024-01-01T00:00:00.000Z",
                            "updated": "2024-01-02T00:00:00.000Z"
                        }
                    }
                ],
                "total": 1,
                "maxResults": 50
            },
            status=200
        )
        
        with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.jira import ingest_jira_issues
            
            result = await ingest_jira_issues(jira_data_source.id)
            
            assert result["status"] == "success"
            assert result["issues_processed"] > 0
    
    @responses.activate
    async def test_ingest_open_and_closed_issues(self, session, jira_data_source, mock_openai_client):
        """Test ingestion of both open and closed issues."""
        # Mock response with mixed statuses
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/search",
            json={
                "issues": [
                    {
                        "id": "10001",
                        "key": "PROJ-1",
                        "fields": {
                            "summary": "Open Issue",
                            "description": "Still open",
                            "status": {"name": "In Progress"}
                        }
                    },
                    {
                        "id": "10002",
                        "key": "PROJ-2",
                        "fields": {
                            "summary": "Closed Issue",
                            "description": "Already resolved",
                            "status": {"name": "Done"}
                        }
                    }
                ],
                "total": 2
            },
            status=200
        )
        
        with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.jira import ingest_jira_issues
            
            result = await ingest_jira_issues(jira_data_source.id)
            
            assert result["status"] == "success"
            assert result["issues_processed"] >= 2
    
    @responses.activate
    async def test_jira_api_error(self, session, jira_data_source):
        """Test handling of JIRA API errors."""
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/search",
            json={"errorMessages": ["Authentication failed"]},
            status=401
        )
        
        from tasks.ingestion.jira import ingest_jira_issues
        
        with pytest.raises(Exception):
            await ingest_jira_issues(jira_data_source.id)
    
    @responses.activate
    async def test_jira_pagination(self, session, jira_data_source, mock_openai_client):
        """Test JIRA ingestion with pagination."""
        # First page
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/search",
            json={
                "issues": [
                    {
                        "id": "1",
                        "key": "PROJ-1",
                        "fields": {"summary": "Issue 1", "description": "Desc 1"}
                    }
                ],
                "total": 2,
                "startAt": 0,
                "maxResults": 1
            },
            status=200
        )
        
        # Second page
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/search",
            json={
                "issues": [
                    {
                        "id": "2",
                        "key": "PROJ-2",
                        "fields": {"summary": "Issue 2", "description": "Desc 2"}
                    }
                ],
                "total": 2,
                "startAt": 1,
                "maxResults": 1
            },
            status=200
        )
        
        with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.jira import ingest_jira_issues
            
            result = await ingest_jira_issues(jira_data_source.id)
            
            assert result["issues_processed"] >= 2
    
    async def test_issue_with_comments(self, session, jira_data_source, mock_openai_client):
        """Test ingestion of issues with comments."""
        # This would test that comments are included in the document content
        with patch('tasks.ingestion.jira.OpenAIClient', return_value=mock_openai_client):
            # Mock issue with comments
            mock_issue = {
                "id": "10001",
                "key": "PROJ-1",
                "fields": {
                    "summary": "Issue with comments",
                    "description": "Main description",
                    "comment": {
                        "comments": [
                            {"body": "Comment 1"},
                            {"body": "Comment 2"}
                        ]
                    }
                }
            }
            
            from tasks.ingestion.jira import format_issue_content
            
            # Test content formatting includes comments
            content = format_issue_content(mock_issue)
            
            assert "Comment 1" in content
            assert "Comment 2" in content
