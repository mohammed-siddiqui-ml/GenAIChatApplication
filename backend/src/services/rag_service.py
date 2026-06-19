"""
RAG (Retrieval-Augmented Generation) Service

Implements RAG pipeline using LangChain integration for context-aware response generation.
Combines vector search with LLM prompting for accurate, source-cited answers.
"""

import logging
import time
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.knowledge import DocumentEmbedding, KnowledgeDocument
from models.chat import ChatMessage, MessageRole
from integrations.openai_client import OpenAIClient, OpenAIError
from core.config import settings
from core.metrics import (
    query_processing_duration,
    embedding_generation_duration,
    vector_search_duration,
    vector_search_results,
)

# Logger
logger = logging.getLogger(__name__)


# Constants
DEFAULT_TOP_K = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_MAX_CONTEXT_TOKENS = 3000


class RAGError(Exception):
    """Custom exception for RAG service errors."""
    pass


class RAGEngine:
    """
    RAG Engine for Retrieval-Augmented Generation.

    Implements complete RAG pipeline:
    1. Query embedding generation
    2. Vector similarity search using pgvector
    3. Context assembly with source metadata
    4. LLM prompting with system message
    5. Streaming response generation
    6. Source citation in response metadata
    """

    def __init__(
        self,
        db_session: AsyncSession,
        openai_client: Optional[OpenAIClient] = None
    ):
        """
        Initialize RAG engine.

        Args:
            db_session: Async database session for vector search
            openai_client: OpenAI client instance (creates new if None)
        """
        self.db = db_session
        self.openai_client = openai_client or OpenAIClient(
            api_key=settings.OPENAI_API_KEY,
            embedding_model=settings.EMBEDDING_MODEL,
            chat_model=settings.OPENAI_MODEL
        )

        logger.info("RAG Engine initialized")

    async def query(
        self,
        query_text: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute RAG query pipeline.

        Pipeline steps:
        1. Generate embedding for query
        2. Perform vector similarity search (pgvector cosine similarity)
        3. Assemble context from top results
        4. Build prompt with system message, context, and conversation history
        5. Generate LLM response (streaming or non-streaming)
        6. Return response with source citations

        Args:
            query_text: User's natural language query
            conversation_history: Previous messages for context continuity
            top_k: Number of similar chunks to retrieve (default: 10)
            similarity_threshold: Minimum cosine similarity (default: 0.7)
            max_context_tokens: Maximum tokens for context (default: 3000)
            stream: Whether to stream response (default: False)
            temperature: LLM temperature override
            max_tokens: LLM max tokens override

        Returns:
            Dict containing:
                - content: LLM response text (if not streaming)
                - sources: List of source documents with metadata
                - streaming_iterator: AsyncIterator[str] (if streaming)
                - metadata: Query metadata (tokens, similarity scores, etc.)

        Raises:
            RAGError: If RAG pipeline fails
        """
        try:
            # Start timing the overall query processing
            query_start_time = time.time()

            logger.info(f"RAG query: '{query_text[:100]}...'")

            # Step 1: Generate query embedding
            query_embedding = await self._embed_query(query_text)

            # Step 2: Vector similarity search
            search_results = await self._vector_search(
                query_embedding=query_embedding,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )

            # Step 3: Assemble context with source metadata
            context, sources = await self._assemble_context(
                search_results=search_results,
                max_tokens=max_context_tokens
            )

            # Step 4: Build prompt with conversation history
            messages = self._build_prompt(
                query_text=query_text,
                context=context,
                conversation_history=conversation_history
            )

            # Step 5: Generate LLM response
            if stream:
                # Return streaming iterator
                streaming_iterator = self._generate_streaming_response(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                # Record query processing time
                query_duration = time.time() - query_start_time
                query_processing_duration.observe(query_duration)

                return {
                    "streaming_iterator": streaming_iterator,
                    "sources": sources,
                    "metadata": {
                        "query": query_text,
                        "num_sources": len(sources),
                        "context_length": len(context),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            else:
                # Non-streaming response
                response = await self.openai_client.generate_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                # Record query processing time
                query_duration = time.time() - query_start_time
                query_processing_duration.observe(query_duration)

                return {
                    "content": response["content"],
                    "sources": sources,
                    "metadata": {
                        "query": query_text,
                        "num_sources": len(sources),
                        "context_length": len(context),
                        "usage": response.get("usage", {}),
                        "finish_reason": response.get("finish_reason"),
                        "processing_time_seconds": query_duration,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

        except OpenAIError as e:
            logger.error(f"OpenAI error in RAG pipeline: {e}")
            raise RAGError(f"LLM generation failed: {e}")
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise RAGError(f"RAG pipeline error: {e}")

    async def _embed_query(self, query_text: str) -> List[float]:
        """
        Generate embedding for query text.

        Args:
            query_text: Query text to embed

        Returns:
            List of 1536 floats representing the query embedding

        Raises:
            RAGError: If embedding generation fails
        """
        try:
            logger.debug(f"Generating query embedding ({len(query_text)} chars)")

            # Time embedding generation
            embed_start = time.time()
            embedding = await self.openai_client.generate_embedding(query_text)
            embed_duration = time.time() - embed_start

            # Record embedding generation time
            embedding_generation_duration.observe(embed_duration)

            logger.debug(f"Query embedding generated: {len(embedding)} dimensions in {embed_duration:.3f}s")
            return embedding
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            raise RAGError(f"Failed to embed query: {e}")

    async def _vector_search(
        self,
        query_embedding: List[float],
        top_k: int,
        similarity_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using pgvector.

        Uses cosine similarity (1 - cosine_distance) with pgvector's <=> operator.
        Filters results by similarity threshold and returns top_k results.

        Args:
            query_embedding: Query embedding vector (1536 dimensions)
            top_k: Number of top results to retrieve
            similarity_threshold: Minimum cosine similarity (0-1)

        Returns:
            List of dicts containing:
                - chunk_text: Text content of the chunk
                - document_id: ID of source document
                - title: Document title
                - url: Document URL
                - content_type: Type of content
                - similarity: Cosine similarity score
                - metadata: Document metadata

        Raises:
            RAGError: If vector search fails
        """
        try:
            logger.debug(f"Vector search: top_k={top_k}, threshold={similarity_threshold}")

            # Time vector search
            search_start = time.time()

            # Convert embedding to pgvector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

            # Build query using pgvector cosine similarity operator (<=>)
            # Cosine similarity = 1 - cosine_distance
            # Filter by similarity > threshold (cosine_distance < 1 - threshold)
            distance_threshold = 1.0 - similarity_threshold

            query = text("""
                SELECT
                    de.chunk_text,
                    de.document_id,
                    de.chunk_index,
                    kd.title,
                    kd.url,
                    kd.content_type,
                    kd.metadata as doc_metadata,
                    (1 - (de.embedding <=> :embedding::vector)) as similarity
                FROM document_embeddings de
                JOIN knowledge_documents kd ON de.document_id = kd.id
                WHERE
                    kd.is_deleted = FALSE
                    AND (de.embedding <=> :embedding::vector) < :distance_threshold
                ORDER BY de.embedding <=> :embedding::vector
                LIMIT :top_k
            """)

            result = await self.db.execute(
                query,
                {
                    "embedding": embedding_str,
                    "distance_threshold": distance_threshold,
                    "top_k": top_k
                }
            )

            rows = result.fetchall()

            # Record vector search time
            search_duration = time.time() - search_start
            vector_search_duration.observe(search_duration)

            # Use subscript notation for compatibility with both Row objects and dicts
            search_results = [
                {
                    "chunk_text": row["chunk_text"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "title": row["title"],
                    "url": row["url"],
                    "content_type": row["content_type"],
                    "similarity": float(row["similarity"]),
                    "metadata": row["doc_metadata"] or {}
                }
                for row in rows
            ]

            # Record number of results
            vector_search_results.observe(len(search_results))

            logger.info(f"Vector search found {len(search_results)} results in {search_duration:.3f}s")

            return search_results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise RAGError(f"Vector search error: {e}")

    async def _assemble_context(
        self,
        search_results: List[Dict[str, Any]],
        max_tokens: int
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Assemble context from search results with source metadata.

        Combines relevant chunks into context string while tracking sources.
        Respects max_tokens limit for context length.

        Args:
            search_results: List of vector search results
            max_tokens: Maximum tokens for assembled context

        Returns:
            Tuple of (context_string, sources_list)
                - context_string: Combined text from relevant chunks
                - sources_list: List of source metadata dicts
        """
        if not search_results:
            logger.warning("No search results to assemble context from")
            return "", []

        context_parts = []
        sources = []
        total_tokens = 0

        for i, result in enumerate(search_results):
            chunk_text = result["chunk_text"]

            # Estimate tokens (rough estimate: ~4 chars per token)
            chunk_tokens = len(chunk_text) // 4

            if total_tokens + chunk_tokens > max_tokens:
                logger.debug(f"Context token limit reached at {i} chunks")
                break

            # Add chunk to context
            context_parts.append(f"[Source {i+1}]: {chunk_text}")
            total_tokens += chunk_tokens

            # Track unique sources (deduplicate by document_id)
            source_entry = {
                "id": result["document_id"],
                "title": result["title"],
                "url": result["url"],
                "type": result["content_type"],
                "similarity": result["similarity"],
                "chunk_index": result["chunk_index"],
                "metadata": result["metadata"]
            }

            # Add to sources if not already present (by document_id)
            if not any(s["id"] == source_entry["id"] for s in sources):
                sources.append(source_entry)

        context = "\n\n".join(context_parts)

        logger.info(
            f"Assembled context: {len(context_parts)} chunks, "
            f"{total_tokens} tokens, {len(sources)} unique sources"
        )

        return context, sources

    def _build_prompt(
        self,
        query_text: str,
        context: str,
        conversation_history: Optional[List[ChatMessage]] = None
    ) -> List[Dict[str, str]]:
        """
        Build prompt messages for LLM with system message and conversation history.

        Constructs message array with:
        1. System message with instructions and context
        2. Conversation history (if provided)
        3. User query

        Args:
            query_text: User's current query
            context: Assembled context from vector search
            conversation_history: Previous messages for continuity

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        messages = []

        # System message with instructions and context
        system_message = self._create_system_message(context)
        messages.append({
            "role": "system",
            "content": system_message
        })

        # Add conversation history (if provided)
        if conversation_history:
            # Limit history to last N messages to avoid context overflow
            max_history_messages = 10
            recent_history = conversation_history[-max_history_messages:]

            for msg in recent_history:
                # Handle both ChatMessage objects and dict representations
                if isinstance(msg, dict):
                    # Dict format: {"role": "user", "content": "..."}
                    msg_role = msg.get("role")
                    msg_content = msg.get("content")
                else:
                    # ChatMessage object format
                    msg_role = msg.role.value if hasattr(msg.role, 'value') else msg.role
                    msg_content = msg.content

                # Skip system messages from history
                if msg_role != "system" and msg_role != MessageRole.SYSTEM:
                    messages.append({
                        "role": msg_role,
                        "content": msg_content
                    })

            logger.debug(f"Added {len(recent_history)} messages from conversation history")

        # Add current user query
        messages.append({
            "role": "user",
            "content": query_text
        })

        logger.debug(f"Built prompt with {len(messages)} messages")

        return messages

    def _create_system_message(self, context: str) -> str:
        """
        Create system message with RAG instructions and context.

        Args:
            context: Assembled context from vector search

        Returns:
            System message string with instructions and context
        """
        system_message = f"""You are an intelligent assistant for a knowledge retrieval system. Your role is to provide accurate, helpful answers based on the provided context.

INSTRUCTIONS:
1. Answer questions based ONLY on the provided context below
2. If the context doesn't contain enough information, acknowledge this clearly
3. Cite specific sources using [Source N] notation when referencing information
4. Be concise and direct in your responses
5. If you're uncertain, express appropriate uncertainty
6. For ambiguous questions, ask clarifying questions

CONTEXT:
{context}

Please provide a helpful, accurate response based on the above context."""

        return system_message

    async def _generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> AsyncIterator[str]:
        """
        Generate streaming LLM response.

        Args:
            messages: Prompt messages
            temperature: LLM temperature
            max_tokens: Max tokens to generate

        Yields:
            Content chunks as they arrive from LLM

        Raises:
            RAGError: If streaming fails
        """
        try:
            logger.debug("Starting streaming response generation")

            async for chunk in self.openai_client.generate_completion_stream(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Streaming response failed: {e}")
            raise RAGError(f"Streaming generation error: {e}")

    # ==================== Public Methods for Testing ====================
    # These methods expose internal functionality for unit testing

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text (public wrapper for testing).

        Args:
            text: Text to embed

        Returns:
            List[float]: Embedding vector
        """
        return await self._embed_query(text)

    async def search_similar_documents(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents (public wrapper for testing).

        Args:
            query: Query text
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score

        Returns:
            List[Dict[str, Any]]: Search results with similarity scores
        """
        query_embedding = await self._embed_query(query)
        return await self._vector_search(query_embedding, top_k, similarity_threshold)

    def assemble_context(
        self,
        search_results: List[Dict[str, Any]],
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    ) -> str:
        """
        Assemble context from search results (synchronous wrapper for testing).

        Args:
            search_results: Search results to assemble
            max_tokens: Maximum tokens in context

        Returns:
            str: Assembled context text
        """
        # Note: This is a synchronous wrapper. Tests may need adjustment.
        # The actual implementation is async.
        context_parts = []

        for result in search_results:
            chunk_text = result.get("chunk_text", result.get("content", ""))
            title = result.get("title", "Unknown")
            context_parts.append(f"[{title}]\n{chunk_text}")

        return "\n\n".join(context_parts)

    async def generate_response(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate response using RAG context (public wrapper for testing).

        Args:
            query: User query
            context: RAG context to use
            conversation_history: Previous conversation messages
            temperature: LLM temperature
            max_tokens: Max tokens in response

        Returns:
            Dict[str, Any]: Response with content and metadata
        """
        # Build messages
        system_message = self._build_system_message(context)

        messages = [{"role": "system", "content": system_message}]

        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-5:]:  # Last 5 messages
                messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })

        # Add current query
        messages.append({"role": "user", "content": query})

        # Call OpenAI for non-streaming response
        try:
            response = await self.openai_client.create_completion(
                messages=messages,
                temperature=temperature or 0.7,
                max_tokens=max_tokens or 1000,
                stream=False
            )

            return {
                "content": response["choices"][0]["message"]["content"],
                "model": response.get("model", "unknown"),
                "usage": response.get("usage", {})
            }
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            raise RAGError(f"Failed to generate response: {e}")

    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming response (public wrapper for testing).

        Args:
            messages: Chat messages
            temperature: LLM temperature
            max_tokens: Max tokens in response

        Yields:
            str: Response chunks
        """
        async for chunk in self._generate_streaming_response(messages, temperature, max_tokens):
            yield chunk
