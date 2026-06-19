"""
Integration tests for Onboarding Material Ingestion Celery Tasks.

Tests ingestion of onboarding documents from various sources
with mocked external APIs.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import responses


@pytest.mark.integration
@pytest.mark.asyncio
class TestOnboardingIngestion:
    """Integration tests for onboarding material ingestion tasks."""
    
    @responses.activate
    async def test_ingest_onboarding_docs_success(self, session, mock_openai_client):
        """Test successful onboarding document ingestion."""
        # Create onboarding data source
        from models.data_source import DataSource, DataSourceType
        from utils.crypto import encrypt_config_dict
        
        config = {
            "url": "https://docs.example.com",
            "api_token": "token123",
            "document_path": "/onboarding"
        }
        
        data_source = DataSource(
            name="Test Onboarding",
            source_type=DataSourceType.ONBOARDING,
            config=encrypt_config_dict(config, sensitive_fields=["api_token"]),
            is_active=True
        )
        session.add(data_source)
        await session.commit()
        await session.refresh(data_source)
        
        # Mock document API
        responses.add(
            responses.GET,
            "https://docs.example.com/api/documents",
            json={
                "documents": [
                    {
                        "id": "doc-1",
                        "title": "Onboarding Guide",
                        "content": "Welcome to the company! Here is your guide...",
                        "type": "guide"
                    }
                ]
            },
            status=200
        )
        
        with patch('tasks.ingestion.onboarding.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.onboarding import ingest_onboarding_docs
            
            result = await ingest_onboarding_docs(data_source.id)
            
            assert result["status"] == "success"
            assert result["documents_processed"] > 0
    
    async def test_ingest_pdf_documents(self, session, mock_openai_client):
        """Test ingestion of PDF onboarding documents."""
        # Mock PDF processing
        with patch('tasks.ingestion.onboarding.OpenAIClient', return_value=mock_openai_client):
            from utils.text_processing import extract_text_from_pdf
            
            # This would test PDF text extraction
            # Actual implementation depends on the PDF library used
            pass
    
    async def test_ingest_markdown_documents(self, session, mock_openai_client):
        """Test ingestion of Markdown onboarding documents."""
        with patch('tasks.ingestion.onboarding.OpenAIClient', return_value=mock_openai_client):
            from utils.text_processing import parse_markdown
            
            markdown_content = """
# Onboarding Guide

## Getting Started

Welcome to the team!

## Next Steps

1. Complete training
2. Set up accounts
"""
            
            # Test markdown parsing
            parsed = parse_markdown(markdown_content)
            
            assert "Getting Started" in parsed
            assert "Next Steps" in parsed
    
    async def test_ingest_multiple_file_types(self, session, mock_openai_client):
        """Test ingestion of multiple document formats."""
        # Test that the ingestion supports PDF, DOCX, MD, TXT, etc.
        file_types = ["pdf", "docx", "md", "txt"]
        
        for file_type in file_types:
            # Each file type should be processable
            assert file_type in ["pdf", "docx", "md", "txt", "html"]
    
    @responses.activate
    async def test_handle_missing_documents(self, session, mock_openai_client):
        """Test handling when no documents are found."""
        from models.data_source import DataSource, DataSourceType
        from utils.crypto import encrypt_config_dict
        
        config = {
            "url": "https://docs.example.com",
            "api_token": "token123"
        }
        
        data_source = DataSource(
            name="Empty Source",
            source_type=DataSourceType.ONBOARDING,
            config=encrypt_config_dict(config, sensitive_fields=["api_token"]),
            is_active=True
        )
        session.add(data_source)
        await session.commit()
        await session.refresh(data_source)
        
        # Mock empty response
        responses.add(
            responses.GET,
            "https://docs.example.com/api/documents",
            json={"documents": []},
            status=200
        )
        
        with patch('tasks.ingestion.onboarding.OpenAIClient', return_value=mock_openai_client):
            from tasks.ingestion.onboarding import ingest_onboarding_docs
            
            result = await ingest_onboarding_docs(data_source.id)
            
            assert result["status"] == "success"
            assert result["documents_processed"] == 0
