"""
Main FastAPI application entry point with Socket.IO support
"""
import socketio
import time
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

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
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to start queue worker
@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    asyncio.create_task(ollama_queue_worker())
    print("🚀 Ollama queue worker started")

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

# Socket.IO event handlers
@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    print(f"Client connected: {sid}")
    return True  # Accept all connections in development

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    print(f"Client disconnected: {sid}")

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
    """Handle send_message event - queue request for processing"""
    content = data.get('content', '')
    session_id = data.get('sessionId', '')

    print(f"\n=== NEW MESSAGE ===")
    print(f"SID: {sid[:8]}...")
    print(f"Content: {content[:50]}...")
    print(f"Queue size: {ollama_request_queue.qsize()}")
    print(f"Processing: {ollama_processing}")
    print(f"==================\n")

    # Add to queue
    await ollama_request_queue.put((sid, content))

    # ALWAYS send typing indicator to let user know we're processing
    await sio.emit('typing', True, room=sid)

    queue_position = ollama_request_queue.qsize()
    if queue_position > 1 or ollama_processing:
        # Notify user they're in queue
        await sio.emit('message', {
            'id': str(int(time.time())),
            'content': f"⏳ Your request is queued (position {queue_position}). Please wait...",
            'role': 'system',
            'timestamp': int(time.time())
        }, room=sid)

    print(f"✅ Added to queue. Position: {queue_position}")

@sio.on('chat:query')
async def handle_chat_query(sid, data):
    """Handle chat query from client"""
    query = data.get('query', '')
    print(f"Received query from {sid}: {query}")

    # Echo back a simple response for now
    await sio.emit('chat:chunk', {
        'content': f"Echo: {query}",
        'chunk_index': 0
    }, room=sid)

    await sio.emit('chat:done', {
        'total_chunks': 1,
        'success': True
    }, room=sid)

# Wrap FastAPI app with Socket.IO
app = socketio.ASGIApp(
    socketio_server=sio,
    other_asgi_app=app,
    socketio_path='/socket.io'
)
