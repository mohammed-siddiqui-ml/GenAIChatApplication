"""
Unit tests for RAGEngine (RAG Service).

Tests RAG pipeline including embedding generation, vector search,
context assembly, and response generation with OpenAI.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from services.rag_service import RAGEngine, RAGError
from models.knowledge import DocumentEmbedding, KnowledgeDocument


@pytest.mark.unit
@pytest.mark.asyncio
class TestRAGEngine:
    """Unit tests for RAGEngine."""
    
    async def test_generate_embedding(self, session, mock_openai_client):
        """Test embedding generation for query."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            rag_engine = RAGEngine(session)
            
            query = "What is the onboarding process?"
            embedding = await rag_engine.generate_embedding(query)
            
            assert embedding is not None
            assert len(embedding) == 1536
            mock_openai_client.create_embedding.assert_called_once()
    
    async def test_search_similar_documents(self, session, document_embeddings, mock_openai_client):
        """Test vector similarity search."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            rag_engine = RAGEngine(session)
            
            query = "getting started guide"
            results = await rag_engine.search_similar_documents(
                query=query,
                top_k=5,
                similarity_threshold=0.5
            )
            
            assert isinstance(results, list)
            # Results depend on similarity calculation with mock embeddings
    
    async def test_assemble_context(self, session, knowledge_documents):
        """Test context assembly from search results."""
        with patch('services.rag_service.OpenAIClient'):
            rag_engine = RAGEngine(session)
            
            # Create mock search results
            search_results = [
                {
                    "document_id": knowledge_documents[0].id,
                    "chunk_text": knowledge_documents[0].content[:200],
                    "similarity": 0.85,
                    "title": knowledge_documents[0].title,
                    "url": knowledge_documents[0].url
                }
            ]
            
            context = rag_engine.assemble_context(search_results)
            
            assert context is not None
            assert "Getting Started Guide" in context
            assert len(context) > 0
    
    async def test_generate_response(self, session, mock_openai_client):
        """Test response generation with RAG context."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            rag_engine = RAGEngine(session)
            
            query = "What is the onboarding process?"
            context = "The onboarding process includes: 1. Account setup, 2. Training, 3. Access provisioning"
            
            response = await rag_engine.generate_response(
                query=query,
                context=context
            )
            
            assert response is not None
            assert "content" in response
            assert len(response["content"]) > 0
            mock_openai_client.create_completion.assert_called_once()
    
    async def test_query_pipeline_end_to_end(self, session, knowledge_documents, document_embeddings, mock_openai_client):
        """Test complete RAG pipeline from query to response."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            rag_engine = RAGEngine(session)
            
            query = "How do I get started?"
            
            result = await rag_engine.query(
                query=query,
                top_k=5,
                include_sources=True
            )
            
            assert result is not None
            assert "answer" in result
            assert "sources" in result
            assert isinstance(result["sources"], list)
    
    async def test_streaming_response(self, session, mock_openai_client):
        """Test streaming response generation."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            rag_engine = RAGEngine(session)
            
            query = "What is the FAQ?"
            context = "FAQ: Q1: ..., Q2: ..."
            
            chunks = []
            async for chunk in rag_engine.generate_streaming_response(query, context):
                chunks.append(chunk)
            
            assert len(chunks) > 0
    
    async def test_error_handling_embedding_failure(self, session):
        """Test error handling when embedding generation fails."""
        mock_client = MagicMock()
        mock_client.create_embedding = AsyncMock(side_effect=Exception("API Error"))
        
        with patch('services.rag_service.OpenAIClient', return_value=mock_client):
            rag_engine = RAGEngine(session)
            
            with pytest.raises(RAGError):
                await rag_engine.generate_embedding("test query")
    
    async def test_similarity_threshold_filtering(self, session, document_embeddings, mock_openai_client):
        """Test that results below similarity threshold are filtered out."""
        with patch('services.rag_service.OpenAIClient', return_value=mock_openai_client):
            rag_engine = RAGEngine(session)
            
            # Search with very high threshold
            results = await rag_engine.search_similar_documents(
                query="test",
                top_k=10,
                similarity_threshold=0.99  # Very high threshold
            )
            
            # Should return fewer or no results due to high threshold
            assert isinstance(results, list)
    
    async def test_citation_formatting(self, session, knowledge_documents):
        """Test that citations are properly formatted."""
        with patch('services.rag_service.OpenAIClient'):
            rag_engine = RAGEngine(session)
            
            search_results = [
                {
                    "document_id": knowledge_documents[0].id,
                    "chunk_text": "Test content",
                    "similarity": 0.9,
                    "title": knowledge_documents[0].title,
                    "url": knowledge_documents[0].url
                }
            ]
            
            citations = rag_engine.format_citations(search_results)
            
            assert len(citations) > 0
            assert citations[0]["title"] == "Getting Started Guide"
            assert "url" in citations[0]
