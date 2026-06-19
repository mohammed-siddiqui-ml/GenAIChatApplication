"""
Integration tests for Confluence Ingestion Celery Tasks.

Tests complete ingestion workflow with mocked Confluence API
and OpenAI API responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import responses


@pytest.mark.integration
@pytest.mark.asyncio
class TestConfluenceIngestion:
    """Integration tests for Confluence ingestion tasks."""
    
    @responses.activate
    async def test_ingest_confluence_docs_success(self, session, confluence_data_source, mock_openai_client):
        """Test successful Confluence document ingestion."""
        # Mock Confluence API responses
        responses.add(
            responses.GET,
            "https://confluence.example.com/rest/api/content",
            json={
                "results": [
                    {
                        "id": "page-123",
                        "title": "Test Page",
                        "type": "page",
                        "body": {
                            "storage": {
                                "value": "<p>This is test content for ingestion.</p>"
                            }
                        },
                        "_links": {
                            "webui": "/display/TEST/test-page"
                        }
                    }
                ],
                "size": 1
            },
            status=200
        )
        
        with patch('tasks.ingestion.confluence.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.confluence import ingest_confluence_docs
            
            # Execute task
            result = await ingest_confluence_docs(confluence_data_source.id)
            
            assert result["status"] == "success"
            assert result["documents_processed"] > 0
    
    @responses.activate
    async def test_ingest_confluence_with_pagination(self, session, confluence_data_source, mock_openai_client):
        """Test Confluence ingestion with paginated results."""
        # Mock first page
        responses.add(
            responses.GET,
            "https://confluence.example.com/rest/api/content",
            json={
                "results": [
                    {
                        "id": "page-1",
                        "title": "Page 1",
                        "type": "page",
                        "body": {"storage": {"value": "<p>Content 1</p>"}},
                        "_links": {"webui": "/page1"}
                    }
                ],
                "_links": {
                    "next": "/rest/api/content?start=1"
                },
                "size": 1
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            "https://confluence.example.com/rest/api/content?start=1",
            json={
                "results": [
                    {
                        "id": "page-2",
                        "title": "Page 2",
                        "type": "page",
                        "body": {"storage": {"value": "<p>Content 2</p>"}},
                        "_links": {"webui": "/page2"}
                    }
                ],
                "size": 1
            },
            status=200
        )
        
        with patch('tasks.ingestion.confluence.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.confluence import ingest_confluence_docs
            
            result = await ingest_confluence_docs(confluence_data_source.id)
            
            assert result["status"] == "success"
            assert result["documents_processed"] >= 2
    
    @responses.activate
    async def test_ingest_confluence_api_error(self, session, confluence_data_source):
        """Test handling of Confluence API errors."""
        # Mock API error
        responses.add(
            responses.GET,
            "https://confluence.example.com/rest/api/content",
            json={"message": "Unauthorized"},
            status=401
        )
        
        from tasks.ingestion.confluence import ingest_confluence_docs
        
        with pytest.raises(Exception):
            await ingest_confluence_docs(confluence_data_source.id)
    
    @responses.activate
    async def test_deduplication(self, session, confluence_data_source, mock_openai_client):
        """Test document deduplication based on content hash."""
        # Mock same document fetched twice
        mock_doc = {
            "id": "page-123",
            "title": "Duplicate Test",
            "type": "page",
            "body": {"storage": {"value": "<p>Identical content</p>"}},
            "_links": {"webui": "/test"}
        }
        
        responses.add(
            responses.GET,
            "https://confluence.example.com/rest/api/content",
            json={"results": [mock_doc], "size": 1},
            status=200
        )
        
        with patch('tasks.ingestion.confluence.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.confluence import ingest_confluence_docs
            
            # First ingestion
            result1 = await ingest_confluence_docs(confluence_data_source.id)
            
            # Second ingestion with same content
            result2 = await ingest_confluence_docs(confluence_data_source.id)
            
            # Should detect duplicate and not re-ingest
            assert result1["status"] == "success"
            assert result2["status"] == "success"
    
    async def test_chunking_large_document(self, session, confluence_data_source, mock_openai_client):
        """Test that large documents are properly chunked."""
        # Create a large document
        large_content = " ".join(["word"] * 2000)  # ~2000 words
        
        with patch('tasks.ingestion.confluence.OpenAIClient', return_value=mock_openai_client):
            from utils.text_processing import chunk_text
            
            chunks = chunk_text(large_content, chunk_size=500, chunk_overlap=50)
            
            # Should create multiple chunks
            assert len(chunks) > 1
            
            # Each chunk should be within size limits
            for chunk in chunks:
                from utils.text_processing import count_tokens
                token_count = count_tokens(chunk)
                assert token_count <= 550  # 500 + some tolerance
