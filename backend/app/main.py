"""
Main FastAPI application entry point with Socket.IO support
"""
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import socketio
import time
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global request queue to prevent concurrent Ollama requests
ollama_request_queue = asyncio.Queue()
ollama_processing = False

# Create Socket.IO server instance
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # Allow all origins in development
    logger=True,
    engineio_logger=False,
)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="GenAI-powered chat-based knowledge retrieval system"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],  # Specific origins when using credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to start queue worker and folder watcher
@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    asyncio.create_task(ollama_queue_worker())
    print("🚀 Ollama queue worker started")

    # Start folder watcher if enabled
    if settings.FOLDER_WATCH_ENABLED:
        try:
            from services.folder_watcher import FolderWatcherService
            watcher = FolderWatcherService(
                watch_path=settings.FOLDER_WATCH_PATH,
                data_source_id=settings.FOLDER_WATCH_DATA_SOURCE_ID
            )
            watcher.start()
            app.state.folder_watcher = watcher
            print(f"📁 Folder watcher started: {settings.FOLDER_WATCH_PATH}")
        except Exception as e:
            print(f"❌ Failed to start folder watcher: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop background tasks"""
    if hasattr(app.state, 'folder_watcher'):
        app.state.folder_watcher.stop()
        print("🛑 Folder watcher stopped")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GenAI Knowledge Retrieval System API",
        "version": settings.APP_VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

# Include API v1 router
from api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")

# Session Management Endpoints
@app.options("/api/v1/chat/sessions")
async def options_chat_session():
    """Handle CORS preflight for session creation"""
    from fastapi.responses import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "http://localhost:3000",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Session-Token",
        }
    )

@app.post("/api/v1/chat/sessions", status_code=201)
async def create_chat_session():
    """Create a new chat session"""
    from core.database import get_session_factory
    from services.chat_service import ChatService
    from datetime import datetime
    from fastapi.responses import JSONResponse

    try:
        SessionFactory = get_session_factory()
        async with SessionFactory() as db:
            chat_service = ChatService(db)
            session = await chat_service.create_session()
            await db.commit()

            logger.info(f"Created new chat session: {session.id}")

            response_data = {
                "session_id": str(session.id),
                "session_token": session.session_token,
                "created_at": session.started_at.isoformat()
            }

            # Return with explicit CORS headers
            return JSONResponse(
                content=response_data,
                status_code=201,
                headers={
                    "Access-Control-Allow-Origin": "http://localhost:3000",
                    "Access-Control-Allow-Credentials": "true",
                }
            )
    except Exception as e:
        logger.error(f"Session creation error: {str(e)}", exc_info=True)
        return JSONResponse(
            content={
                "error": "Failed to create chat session",
                "details": str(e)
            },
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
            }
        )

# Socket.IO event handlers
# Import RAG-enabled chat handler
import sys
from pathlib import Path
src_websockets = Path(__file__).parent.parent / "src" / "websockets"
if str(src_websockets) not in sys.path:
    sys.path.insert(0, str(src_websockets.parent))

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger_instance = logging.getLogger(__name__)
    logger_instance.info(f"Client connected: {sid}")
    return True  # Accept all connections in development

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger_instance = logging.getLogger(__name__)
    logger_instance.info(f"Client disconnected: {sid}")

async def process_ollama_request(sid, content):
    """Process a single Ollama request (called from queue worker)"""
    import httpx
    import traceback

    try:
        ollama_url = settings.OLLAMA_BASE_URL
        model = settings.OLLAMA_CHAT_MODEL

        print(f"🔄 Processing queued request for {sid[:8]}...")

        # Create a single client with connection pooling
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=10.0),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1)
        ) as client:
            print(f"📤 Sending to Ollama: {model}")

            response = await client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "stream": False,
                    "options": {
                        "temperature": settings.OLLAMA_TEMPERATURE,
                        "num_predict": settings.OLLAMA_MAX_TOKENS
                    },
                    "keep_alive": "5m"  # Keep model loaded for 5 minutes
                }
            )

            print(f"📥 Received: Status {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                message = result.get('message', {})
                llm_response = message.get('content', result.get('response', 'No response'))

                print(f"✅ Response ({len(llm_response)} chars): {llm_response[:100]}...")

                # Send response
                await sio.emit('message', {
                    'id': str(int(time.time())),
                    'content': llm_response,
                    'role': 'assistant',
                    'timestamp': int(time.time())
                }, room=sid)

                # Turn off typing indicator
                await sio.emit('typing', False, room=sid)
            else:
                error_msg = f"Ollama error: {response.status_code}"
                print(f"❌ {error_msg}")

                # Send error message
                await sio.emit('message', {
                    'id': str(int(time.time())),
                    'content': error_msg,
                    'role': 'assistant',
                    'timestamp': int(time.time())
                }, room=sid)

                # Turn off typing indicator
                await sio.emit('typing', False, room=sid)

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        print(f"Traceback:\n{error_trace}")

        await sio.emit('message', {
            'id': str(int(time.time())),
            'content': f"Error: {str(e)}",
            'role': 'assistant',
            'timestamp': int(time.time())
        }, room=sid)

        # Turn off typing indicator
        await sio.emit('typing', False, room=sid)


async def ollama_queue_worker():
    """Background worker that processes Ollama requests one at a time"""
    global ollama_processing

    while True:
        try:
            # Wait for next request
            sid, content = await ollama_request_queue.get()

            ollama_processing = True
            print(f"\n{'='*60}")
            print(f"🎯 Processing request {ollama_request_queue.qsize() + 1} from queue")
            print(f"{'='*60}\n")

            # Process the request
            await process_ollama_request(sid, content)

            ollama_processing = False
            ollama_request_queue.task_done()

            print(f"\n✅ Request completed. Queue size: {ollama_request_queue.qsize()}\n")

        except Exception as e:
            print(f"❌ Queue worker error: {e}")
            ollama_processing = False


@sio.on('send_message')
async def handle_send_message(sid, data):
    """Handle send_message event with RAG support"""
    from datetime import datetime
    from core.database import get_session_factory
    from services.rag_service import RAGEngine

    content = data.get('content', '')
    session_id_str = data.get('sessionId', '')

    logger.info(f"\n=== NEW MESSAGE (RAG-enabled) ===")
    logger.info(f"SID: {sid[:8]}...")
    logger.info(f"Content: {content[:50]}...")
    logger.info(f"Session ID: {session_id_str}")
    logger.info(f"==================\n")

    try:
        # Send typing indicator
        await sio.emit('typing', True, room=sid)

        # Get database session
        SessionFactory = get_session_factory()
        async with SessionFactory() as db:
            # Initialize RAG engine
            rag_engine = RAGEngine(db)

            # Execute RAG query with streaming
            rag_result = await rag_engine.query(
                query_text=content,
                conversation_history=[],  # Can add history later
                top_k=5,
                stream=True,
                temperature=0.7
            )

            # Extract streaming iterator and metadata
            streaming_iterator = rag_result.get('streaming_iterator')
            sources = rag_result.get('sources', [])

            logger.info(f"RAG query returned {len(sources)} sources")

            # Collect full response
            full_response = ""
            if streaming_iterator:
                async for chunk in streaming_iterator:
                    if chunk:
                        full_response += chunk

            # Send the complete message back (old format for compatibility)
            message_response = {
                'id': str(int(time.time())),
                'content': full_response,
                'role': 'assistant',
                'timestamp': int(time.time()),
                'sessionId': session_id_str,
                'sources': [
                    {
                        'id': source.get('id'),
                        'title': source.get('title', 'Unknown'),
                        'url': source.get('url'),
                        'type': source.get('type', 'unknown'),
                        'relevanceScore': source.get('similarity', 0.0),
                        'similarity': source.get('similarity', 0.0),
                    }
                    for source in sources
                ]
            }

            await sio.emit('message', message_response, room=sid)

            # Turn off typing indicator
            await sio.emit('typing', False, room=sid)

            logger.info(f"✅ Message sent with {len(sources)} sources")

    except Exception as e:
        logger.error(f"Error in send_message handler: {str(e)}", exc_info=True)
        await sio.emit('message', {
            'id': str(int(time.time())),
            'content': f"Sorry, I encountered an error: {str(e)}",
            'role': 'system',
            'timestamp': int(time.time())
        }, room=sid)
        await sio.emit('typing', False, room=sid)

@sio.on('chat:query')
async def handle_chat_query(sid: str, data: dict):
    """
    Handle chat:query event from client with RAG support

    This handler uses the RAG engine to retrieve relevant context
    and stream responses with source citations.
    """
    from datetime import datetime
    from core.database import get_session_factory
    from services.chat_service import ChatService
    from services.rag_service import RAGEngine
    from models.chat import ChatMessage, MessageRole

    try:
        start_time = time.time()

        # Extract query parameters
        query_text = data.get('query', '')
        session_token = data.get('sessionToken', '')
        top_k = data.get('top_k', 5)
        temperature = data.get('temperature', 0.7)

        logger.info(f"Received chat query from {sid}: {query_text[:50]}...")

        # Get database session
        SessionFactory = get_session_factory()
        async with SessionFactory() as db:
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

            logger.info(f"RAG query returned {len(sources)} sources")

            # Send sources to client
            await sio.emit('chat:sources', {
                'sources': [
                    {
                        'id': source.get('id'),
                        'title': source.get('title', 'Unknown'),
                        'url': source.get('url', ''),
                        'type': source.get('type', 'unknown'),
                        'similarity': source.get('similarity', 0.0),
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

            logger.info(f"Query processed successfully for {sid} in {duration_ms}ms with {len(sources)} sources")

    except Exception as e:
        logger.error(f"Error handling chat query: {str(e)}", exc_info=True)
        await sio.emit('chat:error', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)

# Wrap FastAPI app with Socket.IO
app = socketio.ASGIApp(
    socketio_server=sio,
    other_asgi_app=app,
    socketio_path='/socket.io'
)
