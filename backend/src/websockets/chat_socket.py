"""
Socket.IO WebSocket Handlers for Real-Time Chat

This module implements Socket.IO event handlers for bidirectional real-time
communication between the client and server. It provides streaming chat responses,
source citations, and error handling.

Events:
    - chat:query: Client sends a query to the server
    - chat:chunk: Server streams response chunks to the client
    - chat:sources: Server sends source citations to the client
    - chat:done: Server sends completion metadata to the client
    - chat:error: Server sends error messages to the client
"""

import logging
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

import socketio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.security import decode_token
from services.chat_service import ChatService, ChatSessionError
from services.rag_service import RAGEngine, RAGError
from models.chat import ChatMessage, MessageRole

# Logger
logger = logging.getLogger(__name__)

# Create Socket.IO server instance
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # Configure based on settings in production
    logger=True,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
)


async def get_db_session() -> AsyncSession:
    """
    Get a database session from the session factory.

    Returns:
        AsyncSession: Database session
    """
    session_factory = get_session_factory()
    return session_factory()


@sio.event
async def connect(sid: str, environ: Dict[str, Any], auth: Optional[Dict[str, Any]] = None):
    """
    Handle client connection to Socket.IO server.

    Authenticates the client using session token from auth data.
    Stores session information in the Socket.IO session.

    Args:
        sid: Socket.IO session ID
        environ: ASGI environment dictionary
        auth: Authentication data containing token and sessionId

    Returns:
        True to accept connection, False to reject
    """
    try:
        logger.info(f"Client connecting: {sid}")

        # Extract authentication data
        if not auth:
            logger.warning(f"Connection rejected for {sid}: No auth data provided")
            return False

        session_token = auth.get('token')
        session_id = auth.get('sessionId')

        if not session_token or not session_id:
            logger.warning(f"Connection rejected for {sid}: Missing token or sessionId")
            return False

        # Validate session token using database
        db = await get_db_session()
        try:
            chat_service = ChatService(db)
            session = await chat_service.validate_session(session_token)

            if not session:
                logger.warning(f"Connection rejected for {sid}: Invalid session token")
                return False

            # Store session information in Socket.IO session
            async with sio.session(sid) as socket_session:
                socket_session['session_token'] = session_token
                socket_session['session_id'] = str(session.id)
                socket_session['user_id'] = session.user_id

            logger.info(f"Client connected successfully: {sid}, session: {session.id}")
            return True

        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Connection error for {sid}: {str(e)}")
        return False


@sio.event
async def disconnect(sid: str):
    """
    Handle client disconnection from Socket.IO server.

    Args:
        sid: Socket.IO session ID
    """
    try:
        logger.info(f"Client disconnected: {sid}")
    except Exception as e:
        logger.error(f"Disconnect error for {sid}: {str(e)}")


@sio.on('chat:query')
async def handle_chat_query(sid: str, data: Dict[str, Any]):
    """
    Handle chat:query event from client.

    Receives a query from the client, validates the session,
    and streams the response using RAG engine.

    Args:
        sid: Socket.IO session ID
        data: Query data containing 'query', 'top_k', 'temperature'

    Emits:
        - chat:chunk: Response chunks as they are generated
        - chat:sources: Source citations for the response
        - chat:done: Completion metadata
        - chat:error: Error message if processing fails
    """
    db = None
    start_time = time.time()

    try:
        # Extract query data
        query_text = data.get('query', '').strip()
        top_k = data.get('top_k', 10)
        temperature = data.get('temperature', 0.7)

        # Validate query
        if not query_text:
            await sio.emit('chat:error', {
                'error': 'Query cannot be empty',
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            return

        logger.info(f"Processing query from {sid}: '{query_text[:50]}...'")

        # Get session information
        async with sio.session(sid) as socket_session:
            session_token = socket_session.get('session_token')
            session_id = socket_session.get('session_id')

        if not session_token or not session_id:
            await sio.emit('chat:error', {
                'error': 'Session not authenticated',
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            return

        # Initialize database session
        db = await get_db_session()

        # Validate session
        chat_service = ChatService(db)
        session = await chat_service.validate_session(session_token)

        if not session:
            await sio.emit('chat:error', {
                'error': 'Invalid or expired session',
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            return

        # Save user message to database
        user_message = ChatMessage(
            session_id=session.id,
            role=MessageRole.USER,
            content=query_text,
            message_metadata={"timestamp": datetime.utcnow().isoformat()}
        )
        db.add(user_message)
        await db.flush()

        # Get conversation history (last 10 messages for context)
        conversation_history = session.messages[-10:] if session.messages else []

        # Initialize RAG engine
        rag_engine = RAGEngine(db)

        # Execute RAG query with streaming
        rag_result = await rag_engine.query(
            query_text=query_text,
            conversation_history=conversation_history,
            top_k=top_k,
            stream=True,
            temperature=temperature
        )

        # Extract streaming iterator and metadata
        streaming_iterator = rag_result.get('streaming_iterator')
        sources = rag_result.get('sources', [])
        metadata = rag_result.get('metadata', {})

        # Send sources to client
        await sio.emit('chat:sources', {
            'sources': [
                {
                    'id': source.get('chunk_id'),
                    'title': source.get('title', 'Unknown'),
                    'url': source.get('url', ''),
                    'type': source.get('source_type', 'unknown'),
                    'similarity': source.get('similarity_score', 0.0),
                    'chunk_index': source.get('chunk_index', 0),
                    'metadata': source.get('metadata', {})
                }
                for source in sources
            ],
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)

        # Stream response chunks to client
        full_response = ""
        chunk_count = 0

        if streaming_iterator:
            async for chunk in streaming_iterator:
                if chunk:
                    full_response += chunk
                    chunk_count += 1

                    # Emit chunk to client
                    await sio.emit('chat:chunk', {
                        'chunk': chunk,
                        'chunk_index': chunk_count,
                        'timestamp': datetime.utcnow().isoformat()
                    }, room=sid)

        # Save assistant message to database
        assistant_message = ChatMessage(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            message_metadata={
                'sources': sources,
                'num_sources': len(sources),
                'chunk_count': chunk_count,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        db.add(assistant_message)
        await db.commit()

        # Calculate processing time
        duration_ms = int((time.time() - start_time) * 1000)

        # Send completion metadata to client
        await sio.emit('chat:done', {
            'message_id': assistant_message.id,
            'session_id': str(session.id),
            'metadata': {
                'duration_ms': duration_ms,
                'num_sources': len(sources),
                'chunk_count': chunk_count,
                'query_length': len(query_text),
                'response_length': len(full_response),
                'timestamp': datetime.utcnow().isoformat()
            }
        }, room=sid)

        logger.info(f"Query processed successfully for {sid} in {duration_ms}ms")

    except RAGError as e:
        logger.error(f"RAG error for {sid}: {str(e)}")
        await sio.emit('chat:error', {
            'error': f'Query processing failed: {str(e)}',
            'type': 'rag_error',
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)

    except ChatSessionError as e:
        logger.error(f"Session error for {sid}: {str(e)}")
        await sio.emit('chat:error', {
            'error': f'Session error: {str(e)}',
            'type': 'session_error',
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)

    except Exception as e:
        logger.error(f"Unexpected error processing query for {sid}: {str(e)}")
        await sio.emit('chat:error', {
            'error': 'An unexpected error occurred',
            'type': 'server_error',
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)

    finally:
        if db:
            await db.close()


def setup_socketio(app: FastAPI) -> socketio.ASGIApp:
    """
    Set up Socket.IO server with FastAPI application.

    Creates an ASGI app that combines FastAPI and Socket.IO,
    allowing both HTTP and WebSocket traffic on the same server.

    Args:
        app: FastAPI application instance

    Returns:
        socketio.ASGIApp: Combined ASGI application
    """
    logger.info("Setting up Socket.IO server")

    # Create combined ASGI app
    combined_asgi_app = socketio.ASGIApp(
        socketio_server=sio,
        other_asgi_app=app,
        socketio_path='/socket.io'
    )

    logger.info("Socket.IO server setup complete")
    return combined_asgi_app

