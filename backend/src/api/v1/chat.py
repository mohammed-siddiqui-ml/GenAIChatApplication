"""
Chat API Endpoints

This module provides REST API endpoints for chat functionality including
session management, query processing with RAG, and streaming responses.
"""

import json
import logging
import time
from typing import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.chat import ChatMessage, MessageRole
from schemas.chat import QueryRequest, QueryResponse, SourceCitation
from services.chat_service import ChatService, ChatSessionError
from services.rag_service import RAGEngine, RAGError

# Logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    summary="Create new chat session",
    description="Create a new chat session for anonymous or authenticated users",
    responses={
        201: {
            "description": "Session created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "session_token": "abc123...",
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def create_session(
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new chat session.

    Creates a session record in the database and returns the session token
    for use in subsequent requests.

    Args:
        db: Database session

    Returns:
        Session data including session_id, session_token, and created_at

    Raises:
        HTTPException: If session creation fails
    """
    try:
        chat_service = ChatService(db)

        # Create new session (anonymous user)
        session = await chat_service.create_session()
        await db.commit()

        logger.info(f"Created new chat session: {session.id}")

        return {
            "session_id": str(session.id),
            "session_token": session.session_token,
            "created_at": session.started_at.isoformat()
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Session creation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat session"
        )


async def get_session_token(x_session_token: str = Header(..., description="Session token")) -> str:
    """
    Extract and validate session token from X-Session-Token header.
    
    Args:
        x_session_token: Session token from request header
        
    Returns:
        Validated session token string
        
    Raises:
        HTTPException: If session token is missing or invalid format
    """
    if not x_session_token or not x_session_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token is required in X-Session-Token header"
        )
    return x_session_token.strip()


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Process chat query with RAG",
    description="Process user query using RAG pipeline. Supports streaming via Server-Sent Events when stream=true.",
    responses={
        200: {
            "description": "Query processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "content": "To reset your password...",
                        "sources": [{"id": 123, "title": "Password Guide", "similarity": 0.92}],
                        "metadata": {"tokens_used": 450, "duration_ms": 1200},
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "message_id": 42
                    }
                }
            }
        },
        401: {"description": "Invalid or missing session token"},
        500: {"description": "Query processing failed"}
    }
)
async def query_chat(
    request: QueryRequest,
    session_token: str = Depends(get_session_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Process chat query with RAG pipeline.
    
    For streaming requests (stream=true), returns Server-Sent Events stream.
    For non-streaming requests (stream=false), returns JSON response.
    
    Args:
        request: Query request with query text and parameters
        session_token: Session token from X-Session-Token header
        db: Database session
        
    Returns:
        StreamingResponse with SSE events (if stream=true) or QueryResponse (if stream=false)
        
    Raises:
        HTTPException: If session validation or query processing fails
    """
    start_time = time.time()
    
    try:
        # Initialize chat service
        chat_service = ChatService(db)

        # Validate session FIRST (before expensive RAG initialization)
        session = await chat_service.validate_session(session_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token"
            )

        # Initialize RAG engine only after session validation
        rag_engine = RAGEngine(db)
        
        logger.info(f"Processing query for session {session.id}: '{request.query[:50]}...'")
        
        # Save user message to database
        user_message = ChatMessage(
            session_id=session.id,
            role=MessageRole.USER,
            content=request.query,
            message_metadata={"timestamp": datetime.utcnow().isoformat()}
        )
        db.add(user_message)
        await db.flush()
        
        # Get conversation history (last 10 messages for context)
        conversation_history = session.messages[-10:] if session.messages else []
        
        # Execute RAG query
        if request.stream:
            # Return streaming response
            return await _handle_streaming_query(
                request=request,
                session=session,
                conversation_history=conversation_history,
                rag_engine=rag_engine,
                db=db,
                start_time=start_time
            )
        else:
            # Non-streaming response
            return await _handle_non_streaming_query(
                request=request,
                session=session,
                conversation_history=conversation_history,
                rag_engine=rag_engine,
                db=db,
                start_time=start_time
            )
            
    except HTTPException:
        raise
    except ChatSessionError as e:
        logger.error(f"Session error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Session error: {str(e)}"
        )
    except RAGError as e:
        logger.error(f"RAG error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Query processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your query"
        )


async def _handle_non_streaming_query(
    request: QueryRequest,
    session,
    conversation_history,
    rag_engine: RAGEngine,
    db: AsyncSession,
    start_time: float
) -> QueryResponse:
    """
    Handle non-streaming query processing.

    Args:
        request: Query request
        session: Chat session
        conversation_history: Previous messages
        rag_engine: RAG engine instance
        db: Database session
        start_time: Query start timestamp

    Returns:
        QueryResponse with complete answer
    """
    # Execute RAG query (non-streaming)
    rag_result = await rag_engine.query(
        query_text=request.query,
        conversation_history=conversation_history,
        top_k=request.top_k,
        stream=False,
        temperature=request.temperature
    )

    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)

    # Save assistant response to database
    assistant_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.ASSISTANT,
        content=rag_result["content"],
        message_metadata={
            "sources": [
                {
                    "id": src["id"],
                    "title": src["title"],
                    "url": src.get("url"),
                    "similarity": src["similarity"]
                }
                for src in rag_result["sources"]
            ],
            "tokens_used": rag_result["metadata"].get("usage", {}).get("total_tokens", 0),
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    logger.info(f"Query completed in {duration_ms}ms, message_id={assistant_message.id}")

    # Build response
    return QueryResponse(
        content=rag_result["content"],
        sources=[
            SourceCitation(
                id=src["id"],
                title=src["title"],
                url=src.get("url"),
                type=src["type"],
                similarity=src["similarity"],
                chunk_index=src["chunk_index"],
                metadata=src.get("metadata", {})
            )
            for src in rag_result["sources"]
        ],
        metadata={
            "tokens_used": rag_result["metadata"].get("usage", {}).get("total_tokens", 0),
            "duration_ms": duration_ms,
            "num_sources": len(rag_result["sources"])
        },
        session_id=session.id,
        message_id=assistant_message.id
    )


async def _handle_streaming_query(
    request: QueryRequest,
    session,
    conversation_history,
    rag_engine: RAGEngine,
    db: AsyncSession,
    start_time: float
) -> StreamingResponse:
    """
    Handle streaming query processing with Server-Sent Events.

    Args:
        request: Query request
        session: Chat session
        conversation_history: Previous messages
        rag_engine: RAG engine instance
        db: Database session
        start_time: Query start timestamp

    Returns:
        StreamingResponse with SSE events
    """
    # Execute RAG query (streaming)
    rag_result = await rag_engine.query(
        query_text=request.query,
        conversation_history=conversation_history,
        top_k=request.top_k,
        stream=True,
        temperature=request.temperature
    )

    async def event_generator() -> AsyncIterator[str]:
        """
        Generate Server-Sent Events for streaming response.

        Yields SSE events in format:
        - data: {"type": "chunk", "content": "..."} - Response chunks
        - data: {"type": "sources", "sources": [...]} - Source citations
        - data: {"type": "done", "metadata": {...}} - Completion metadata
        """
        try:
            full_content = ""

            # Stream content chunks
            async for chunk in rag_result["streaming_iterator"]:
                full_content += chunk
                event_data = json.dumps({"type": "chunk", "content": chunk})
                yield f"data: {event_data}\n\n"

            # Send sources
            sources_data = json.dumps({
                "type": "sources",
                "sources": [
                    {
                        "id": src["id"],
                        "title": src["title"],
                        "url": src.get("url"),
                        "type": src["type"],
                        "similarity": src["similarity"],
                        "chunk_index": src["chunk_index"],
                        "metadata": src.get("metadata", {})
                    }
                    for src in rag_result["sources"]
                ]
            })
            yield f"data: {sources_data}\n\n"

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Save assistant response to database
            assistant_message = ChatMessage(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content=full_content,
                message_metadata={
                    "sources": [
                        {
                            "id": src["id"],
                            "title": src["title"],
                            "url": src.get("url"),
                            "similarity": src["similarity"]
                        }
                        for src in rag_result["sources"]
                    ],
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat(),
                    "streaming": True
                }
            )
            db.add(assistant_message)
            await db.commit()
            await db.refresh(assistant_message)

            # Send completion metadata
            done_data = json.dumps({
                "type": "done",
                "metadata": {
                    "duration_ms": duration_ms,
                    "num_sources": len(rag_result["sources"]),
                    "session_id": str(session.id),
                    "message_id": assistant_message.id
                }
            })
            yield f"data: {done_data}\n\n"

            logger.info(f"Streaming query completed in {duration_ms}ms, message_id={assistant_message.id}")

        except Exception as e:
            logger.error(f"Streaming error: {str(e)}", exc_info=True)
            error_data = json.dumps({
                "type": "error",
                "error": "An error occurred while processing your query"
            })
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
