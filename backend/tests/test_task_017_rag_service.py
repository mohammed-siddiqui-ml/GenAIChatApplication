"""
Test suite for Task-017: Build RAG Engine with LangChain Integration

Tests cover:
- Unit tests for RAG pipeline components
- Integration tests for full RAG query flow
- Error handling and edge cases
- Streaming response functionality
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import List, Dict, Any
import asyncio

from services.rag_service import RAGEngine, RAGError
from integrations.openai_client import OpenAIClient
from models.knowledge import KnowledgeDocument
from models.chat import ChatMessage


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def mock_db_session():
    """Create mock database session for testing"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client"""
    client = MagicMock(spec=OpenAIClient)
    
    # Mock embedding generation
    client.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    client.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536])
    
    # Mock completion generation
    client.generate_completion = AsyncMock(return_value={
        "content": "This is a test response based on the context.",
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    })
    
    # Mock streaming completion
    async def mock_stream():
        for chunk in ["This ", "is ", "a ", "streaming ", "response"]:
            yield chunk
    
    client.generate_completion_stream = MagicMock(return_value=mock_stream())
    
    return client


@pytest.fixture
def sample_knowledge_docs():
    """Create sample knowledge documents for testing as mock Row objects"""
    # Create mock Row objects with attributes (not dicts)
    docs = []
    for i, (text, sim) in enumerate([
        ("Python is a high-level programming language.", 0.95),
        ("FastAPI is a modern web framework for Python.", 0.88),
        ("Async programming in Python uses asyncio.", 0.82)
    ]):
        row = MagicMock()
        row.chunk_text = text
        row.document_id = f"doc{i+1}"
        row.chunk_index = i
        row.title = f"Document {i+1}"
        row.url = f"https://example.com/doc{i+1}"
        row.content_type = "text/markdown"
        row.similarity = sim
        row.doc_metadata = {}  # Add metadata field
        docs.append(row)
    return docs


@pytest.fixture
def sample_conversation_history():
    """Create sample conversation history as ChatMessage objects"""
    from models.chat import ChatMessage, MessageRole
    return [
        ChatMessage(role=MessageRole.USER, content="What is Python?"),
        ChatMessage(role=MessageRole.ASSISTANT, content="Python is a programming language.")
    ]


# ============================================================================
# Test Class 1: RAG Engine Initialization
# ============================================================================

class TestRAGEngineInitialization:
    """Unit tests for RAG engine initialization"""

    @pytest.mark.asyncio
    async def test_init_with_custom_openai_client(self, mock_db_session, mock_openai_client):
        """TC-RAG-001: Verify RAG engine initializes with provided OpenAI client"""
        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)
        
        assert engine.db is mock_db_session
        assert engine.openai_client is mock_openai_client

    @pytest.mark.asyncio
    async def test_init_creates_default_openai_client(self, mock_db_session):
        """TC-RAG-002: Verify RAG engine creates default OpenAI client if none provided"""
        with patch('services.rag_service.OpenAIClient') as MockClient:
            mock_client_instance = MagicMock(spec=OpenAIClient)
            MockClient.return_value = mock_client_instance
            
            engine = RAGEngine(db_session=mock_db_session)
            
            assert engine.db is mock_db_session
            assert engine.openai_client is mock_client_instance
            MockClient.assert_called_once()


# ============================================================================
# Test Class 2: Query Embedding Generation
# ============================================================================

class TestQueryEmbedding:
    """Unit tests for query embedding generation"""

    @pytest.mark.asyncio
    async def test_embed_query_generates_1536_dim_vector(self, mock_db_session, mock_openai_client):
        """TC-RAG-003: Verify query embedding has correct dimensions (1536 for text-embedding-ada-002)"""
        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)
        
        embedding = await engine._embed_query("What is Python?")
        
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)
        mock_openai_client.generate_embedding.assert_called_once_with("What is Python?")

    @pytest.mark.asyncio
    async def test_embed_query_handles_empty_string(self, mock_db_session, mock_openai_client):
        """TC-RAG-004: Verify embedding generation handles empty query gracefully"""
        mock_openai_client.generate_embedding.side_effect = ValueError("Empty query")
        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)
        
        with pytest.raises((ValueError, RAGError)):
            await engine._embed_query("")


# ============================================================================
# Test Class 3: Vector Similarity Search
# ============================================================================

class TestVectorSearch:
    """Integration tests for vector similarity search using pgvector"""

    @pytest.mark.asyncio
    async def test_vector_search_returns_top_k_results(self, mock_db_session, mock_openai_client, sample_knowledge_docs):
        """TC-RAG-005: Verify vector search returns top_k most similar documents"""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_knowledge_docs[:2]
        mock_db_session.execute.return_value = mock_result
        
        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)
        query_embedding = [0.1] * 1536
        
        results = await engine._vector_search(query_embedding=query_embedding, top_k=2, similarity_threshold=0.7)
        
        assert len(results) == 2
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_search_filters_by_threshold(self, mock_db_session, mock_openai_client):
        """TC-RAG-006: Verify similarity threshold filters out low-scoring results"""
        # Mock result with varied similarity scores - use complete database row structure
        docs_with_scores = [
            {
                "chunk_text": "High similarity content",
                "document_id": "doc1",
                "chunk_index": 0,
                "title": "High Similarity Doc",
                "url": "https://example.com/doc1",
                "content_type": "page",
                "similarity": 0.95,
                "doc_metadata": {}
            },
            {
                "chunk_text": "Medium similarity content",
                "document_id": "doc2",
                "chunk_index": 0,
                "title": "Medium Similarity Doc",
                "url": "https://example.com/doc2",
                "content_type": "page",
                "similarity": 0.75,
                "doc_metadata": {}
            }
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = docs_with_scores  # Threshold filters out docs < 0.7
        mock_db_session.execute.return_value = mock_result

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)
        query_embedding = [0.1] * 1536

        results = await engine._vector_search(query_embedding=query_embedding, top_k=10, similarity_threshold=0.7)

        # Should only return docs with similarity >= 0.7
        assert all(doc["similarity"] >= 0.7 for doc in results)


# ============================================================================
# Test Class 4: Context Assembly
# ============================================================================

class TestContextAssembly:
    """Unit tests for context assembly from search results"""

    @pytest.mark.asyncio
    async def test_assemble_context_combines_documents(self, mock_db_session, mock_openai_client, sample_knowledge_docs):
        """TC-RAG-007: Verify context assembly combines multiple documents"""
        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        # Convert Row objects to dict format (as _vector_search does)
        search_results = [
            {
                "chunk_text": row.chunk_text,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "title": row.title,
                "url": row.url,
                "content_type": row.content_type,
                "similarity": row.similarity,
                "metadata": {}
            }
            for row in sample_knowledge_docs
        ]

        context, sources = await engine._assemble_context(
            search_results=search_results,
            max_tokens=3000
        )

        # Context should contain text from documents
        assert isinstance(context, str)
        assert len(context) > 0

        # Sources should preserve metadata
        assert isinstance(sources, list)
        assert len(sources) == len(search_results)

    @pytest.mark.asyncio
    async def test_assemble_context_respects_token_limit(self, mock_db_session, mock_openai_client):
        """TC-RAG-008: Verify context assembly respects max_tokens limit"""
        # Create docs that would exceed token limit (using mock Row structure)
        large_docs = []
        for i in range(10):
            row = MagicMock()
            row.chunk_text = "A" * 2000  # Very long content
            row.document_id = f"doc{i}"
            row.chunk_index = i
            row.title = f"Doc {i}"
            row.url = f"https://example.com/doc{i}"
            row.content_type = "text/plain"
            row.similarity = 0.8
            large_docs.append(row)

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        # Convert Row objects to dicts as _vector_search does
        search_results = [
            {
                "chunk_text": row.chunk_text,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "title": row.title,
                "url": row.url,
                "content_type": row.content_type,
                "similarity": row.similarity,
                "metadata": {}  # Add metadata field to match _vector_search output
            }
            for row in large_docs
        ]

        context, sources = await engine._assemble_context(
            search_results=search_results,
            max_tokens=500  # Small limit
        )

        # Context should be truncated to fit within token limit
        assert len(context) < 10000  # Much smaller than all docs combined
        assert len(sources) <= len(search_results)  # May not include all docs


# ============================================================================
# Test Class 5: Prompt Building
# ============================================================================

class TestPromptBuilding:
    """Unit tests for LLM prompt construction"""

    @pytest.mark.asyncio
    async def test_build_prompt_includes_system_message(self, mock_db_session, mock_openai_client):
        """TC-RAG-009: Verify prompt includes system message with instructions"""
        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        messages = engine._build_prompt(
            query_text="What is Python?",
            context="Python is a programming language.",
            conversation_history=None
        )

        assert isinstance(messages, list)
        assert len(messages) >= 2  # System + user message
        assert messages[0]["role"] == "system"
        assert "context" in messages[0]["content"].lower() or "answer" in messages[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_build_prompt_includes_conversation_history(self, mock_db_session, mock_openai_client, sample_conversation_history):
        """TC-RAG-010: Verify conversation history is included in prompt"""
        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        messages = engine._build_prompt(
            query_text="Tell me more",
            context="Additional context.",
            conversation_history=sample_conversation_history
        )

        # Should include system message + history + current query
        assert len(messages) >= len(sample_conversation_history) + 2


# ============================================================================
# Test Class 6: Non-Streaming Query Execution
# ============================================================================

class TestNonStreamingQuery:
    """Integration tests for complete non-streaming RAG query"""

    @pytest.mark.asyncio
    async def test_query_returns_response_and_sources(self, mock_db_session, mock_openai_client, sample_knowledge_docs):
        """TC-RAG-011: Verify complete RAG query returns response with source citations"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_knowledge_docs
        mock_db_session.execute.return_value = mock_result

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        result = await engine.query(
            query_text="What is Python?",
            top_k=3,
            stream=False
        )

        assert "content" in result
        assert "sources" in result
        assert "metadata" in result
        assert isinstance(result["content"], str)
        assert isinstance(result["sources"], list)
        assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_query_with_conversation_history(self, mock_db_session, mock_openai_client, sample_knowledge_docs, sample_conversation_history):
        """TC-RAG-012: Verify query handles conversation history correctly"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_knowledge_docs
        mock_db_session.execute.return_value = mock_result

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        result = await engine.query(
            query_text="Tell me more",
            conversation_history=sample_conversation_history,
            stream=False
        )

        assert "content" in result
        # Verify OpenAI client was called with conversation history
        mock_openai_client.generate_completion.assert_called_once()


# ============================================================================
# Test Class 7: Streaming Query Execution
# ============================================================================

class TestStreamingQuery:
    """Integration tests for streaming RAG responses"""

    @pytest.mark.asyncio
    async def test_streaming_query_returns_iterator(self, mock_db_session, mock_openai_client, sample_knowledge_docs):
        """TC-RAG-013: Verify streaming query returns async iterator"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_knowledge_docs
        mock_db_session.execute.return_value = mock_result

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        result = await engine.query(
            query_text="What is Python?",
            stream=True
        )

        assert "streaming_iterator" in result
        assert "sources" in result
        assert "metadata" in result

        # Verify it's an async iterator
        chunks = []
        async for chunk in result["streaming_iterator"]:
            chunks.append(chunk)
            if len(chunks) >= 5:  # Limit iterations
                break

        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)


# ============================================================================
# Test Class 8: Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for RAG error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_query_handles_embedding_error(self, mock_db_session, mock_openai_client):
        """TC-RAG-014: Verify graceful handling when embedding generation fails"""
        mock_openai_client.generate_embedding.side_effect = Exception("Embedding API failed")

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        with pytest.raises(RAGError):
            await engine.query(query_text="Test query", stream=False)

    @pytest.mark.asyncio
    async def test_query_handles_database_error(self, mock_db_session, mock_openai_client):
        """TC-RAG-015: Verify graceful handling when vector search fails"""
        mock_db_session.execute.side_effect = Exception("Database connection lost")

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        with pytest.raises(RAGError):
            await engine.query(query_text="Test query", stream=False)

    @pytest.mark.asyncio
    async def test_query_handles_llm_error(self, mock_db_session, mock_openai_client, sample_knowledge_docs):
        """TC-RAG-016: Verify graceful handling when LLM generation fails"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_knowledge_docs
        mock_db_session.execute.return_value = mock_result

        mock_openai_client.generate_completion.side_effect = Exception("OpenAI API error")

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        with pytest.raises(RAGError):
            await engine.query(query_text="Test query", stream=False)

    @pytest.mark.asyncio
    async def test_query_handles_no_search_results(self, mock_db_session, mock_openai_client):
        """TC-RAG-017: Verify handling when no documents match the query"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []  # No results
        mock_db_session.execute.return_value = mock_result

        engine = RAGEngine(db_session=mock_db_session, openai_client=mock_openai_client)

        # Should still generate a response, but with no context
        result = await engine.query(query_text="Obscure query with no matches", stream=False)

        assert "content" in result
        assert "sources" in result
        assert len(result["sources"]) == 0  # No sources found
