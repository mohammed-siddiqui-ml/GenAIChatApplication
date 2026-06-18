"""
Tests for Task 019: WebSocket Server with Socket.IO

Tests the real-time WebSocket implementation for chat queries,
including connection handling, streaming responses, error scenarios,
and message persistence.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import uuid

import socketio

from websockets.chat_socket import sio, setup_socketio
from models.chat import ChatSession, ChatMessage, MessageRole
from services.chat_service import ChatSessionError
from services.rag_service import RAGError


@pytest_asyncio.fixture
async def socket_client():
    """Create a Socket.IO test client."""
    client = socketio.AsyncClient()
    yield client
    if client.connected:
        await client.disconnect()


@pytest_asyncio.fixture
async def test_session(session):
    """Create a test chat session."""
    chat_session = ChatSession(
        id=uuid.uuid4(),
        session_token=f"test_token_{uuid.uuid4().hex}",
        user_id=None  # Anonymous session
    )
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


class TestConnectionHandling:
    """Test Socket.IO connection and authentication."""

    @pytest.mark.asyncio
    async def test_tc_001_successful_connection_with_valid_session(self, session, test_session, socket_client):
        """TC-001: Test successful connection with valid session token."""
        # Create mock environ
        environ = {}
        auth = {
            'token': test_session.session_token,
            'sessionId': str(test_session.id)
        }

        # Mock sio.session context manager
        mock_socket_session = {}

        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        # Mock the database session
        with patch('websockets.chat_socket.get_db_session') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.close = AsyncMock()
            mock_get_db.return_value = mock_db

            # Mock ChatService to return the test session
            with patch('websockets.chat_socket.ChatService') as mock_chat_service:
                mock_service = MagicMock()
                mock_service.validate_session = AsyncMock(return_value=test_session)
                mock_chat_service.return_value = mock_service

                # Mock sio.session
                with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
                    # Call connect handler directly
                    from websockets.chat_socket import connect
                    result = await connect('test_sid', environ, auth)

                    # Assertions
                    assert result is True, "Connection should be accepted"
                    mock_service.validate_session.assert_called_once_with(test_session.session_token)
                    # Verify session data was stored
                    assert mock_socket_session['session_token'] == test_session.session_token
                    assert mock_socket_session['session_id'] == str(test_session.id)


    @pytest.mark.asyncio
    async def test_tc_002_connection_rejection_with_invalid_session(self):
        """TC-002: Test connection rejection with invalid session token."""
        environ = {}
        auth = {
            'token': 'invalid_token',
            'sessionId': str(uuid.uuid4())
        }

        # Mock the database session
        with patch('websockets.chat_socket.get_db_session') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.close = AsyncMock()
            mock_get_db.return_value = mock_db

            # Mock ChatService to return None (invalid session)
            with patch('websockets.chat_socket.ChatService') as mock_chat_service:
                mock_service = MagicMock()
                mock_service.validate_session = AsyncMock(return_value=None)
                mock_chat_service.return_value = mock_service

                # Call connect handler
                from websockets.chat_socket import connect
                result = await connect('test_sid', environ, auth)

                # Assertions
                assert result is False, "Connection should be rejected for invalid session"


    @pytest.mark.asyncio
    async def test_tc_002b_connection_rejection_with_missing_auth(self):
        """TC-002b: Test connection rejection with no auth data."""
        environ = {}
        auth = None

        # Call connect handler
        from websockets.chat_socket import connect
        result = await connect('test_sid', environ, auth)

        # Assertions
        assert result is False, "Connection should be rejected when auth is None"


    @pytest.mark.asyncio
    async def test_tc_002c_connection_rejection_with_missing_token(self):
        """TC-002c: Test connection rejection with missing token."""
        environ = {}
        auth = {
            'sessionId': str(uuid.uuid4())
            # Missing 'token'
        }

        # Call connect handler
        from websockets.chat_socket import connect
        result = await connect('test_sid', environ, auth)

        # Assertions
        assert result is False, "Connection should be rejected when token is missing"


    @pytest.mark.asyncio
    async def test_tc_009_disconnection_cleanup(self):
        """TC-009: Test disconnection and cleanup."""
        # Call disconnect handler
        from websockets.chat_socket import disconnect

        # Should not raise any exceptions
        await disconnect('test_sid')
        # Just verify it completes without error


class TestQueryProcessing:
    """Test chat:query event handling and streaming."""

    @pytest.mark.asyncio
    async def test_tc_003_successful_query_with_streaming(self, session, test_session):
        """TC-003: Test successful query processing with streaming chunks."""
        from websockets.chat_socket import handle_chat_query

        # Mock sio session
        mock_socket_session = {
            'session_token': test_session.session_token,
            'session_id': str(test_session.id)
        }

        # Mock emitted events
        emitted_events = []

        async def mock_emit(event, data, room=None):
            emitted_events.append({'event': event, 'data': data, 'room': room})

        # Mock sio.session context manager
        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
            with patch('websockets.chat_socket.sio.emit', mock_emit):
                with patch('websockets.chat_socket.get_db_session') as mock_get_db:
                    mock_db = AsyncMock()
                    mock_db.close = AsyncMock()
                    mock_db.add = MagicMock()
                    mock_db.flush = AsyncMock()
                    mock_db.commit = AsyncMock()
                    mock_get_db.return_value = mock_db

                    # Mock ChatService
                    with patch('websockets.chat_socket.ChatService') as mock_chat_service:
                        mock_service = MagicMock()
                        mock_service.validate_session = AsyncMock(return_value=test_session)
                        mock_chat_service.return_value = mock_service

                        # Mock RAGEngine with streaming response
                        async def mock_streaming_iterator():
                            chunks = ["Hello", " world", "!"]
                            for chunk in chunks:
                                yield chunk

                        mock_sources = [
                            {
                                'chunk_id': 'chunk-1',
                                'title': 'Test Doc',
                                'url': 'http://example.com',
                                'source_type': 'confluence',
                                'similarity_score': 0.95,
                                'chunk_index': 0,
                                'metadata': {}
                            }
                        ]

                        with patch('websockets.chat_socket.RAGEngine') as mock_rag_engine:
                            mock_rag = MagicMock()
                            mock_rag.query = AsyncMock(return_value={
                                'streaming_iterator': mock_streaming_iterator(),
                                'sources': mock_sources,
                                'metadata': {}
                            })
                            mock_rag_engine.return_value = mock_rag

                            # Execute handler
                            query_data = {
                                'query': 'Test question?',
                                'top_k': 10,
                                'temperature': 0.7
                            }
                            await handle_chat_query('test_sid', query_data)

                            # Assertions
                            # Should emit: sources, 3 chunks, done
                            assert len(emitted_events) >= 4, "Should emit sources, chunks, and done events"

                            # Check sources event
                            sources_events = [e for e in emitted_events if e['event'] == 'chat:sources']
                            assert len(sources_events) == 1, "Should emit exactly one sources event"
                            assert len(sources_events[0]['data']['sources']) == 1

                            # Check chunk events
                            chunk_events = [e for e in emitted_events if e['event'] == 'chat:chunk']
                            assert len(chunk_events) == 3, "Should emit 3 chunks"
                            assert chunk_events[0]['data']['chunk'] == "Hello"
                            assert chunk_events[1]['data']['chunk'] == " world"
                            assert chunk_events[2]['data']['chunk'] == "!"

                            # Check done event
                            done_events = [e for e in emitted_events if e['event'] == 'chat:done']
                            assert len(done_events) == 1, "Should emit exactly one done event"
                            assert done_events[0]['data']['metadata']['chunk_count'] == 3


    @pytest.mark.asyncio
    async def test_tc_004_query_with_invalid_session_token(self, session):
        """TC-004: Test query with invalid/expired session token."""
        from websockets.chat_socket import handle_chat_query

        # Mock sio session with invalid token
        mock_socket_session = {
            'session_token': 'invalid_token',
            'session_id': str(uuid.uuid4())
        }

        # Mock emitted events
        emitted_events = []

        async def mock_emit(event, data, room=None):
            emitted_events.append({'event': event, 'data': data, 'room': room})

        # Mock sio.session context manager
        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
            with patch('websockets.chat_socket.sio.emit', mock_emit):
                with patch('websockets.chat_socket.get_db_session') as mock_get_db:
                    mock_db = AsyncMock()
                    mock_db.close = AsyncMock()
                    mock_get_db.return_value = mock_db

                    # Mock ChatService to return None (invalid session)
                    with patch('websockets.chat_socket.ChatService') as mock_chat_service:
                        mock_service = MagicMock()
                        mock_service.validate_session = AsyncMock(return_value=None)
                        mock_chat_service.return_value = mock_service

                        # Execute handler
                        query_data = {'query': 'Test query'}
                        await handle_chat_query('test_sid', query_data)

                        # Assertions
                        error_events = [e for e in emitted_events if e['event'] == 'chat:error']
                        assert len(error_events) == 1, "Should emit error event"
                        assert 'Invalid or expired session' in error_events[0]['data']['error']


    @pytest.mark.asyncio
    async def test_tc_005a_query_with_empty_query(self, session, test_session):
        """TC-005a: Test query with empty query string."""
        from websockets.chat_socket import handle_chat_query

        # Mock sio session
        mock_socket_session = {
            'session_token': test_session.session_token,
            'session_id': str(test_session.id)
        }

        # Mock emitted events
        emitted_events = []

        async def mock_emit(event, data, room=None):
            emitted_events.append({'event': event, 'data': data, 'room': room})

        # Mock sio.session context manager
        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
            with patch('websockets.chat_socket.sio.emit', mock_emit):
                # Execute handler with empty query
                query_data = {'query': '   '}  # Whitespace only
                await handle_chat_query('test_sid', query_data)

                # Assertions
                error_events = [e for e in emitted_events if e['event'] == 'chat:error']
                assert len(error_events) == 1, "Should emit error event for empty query"
                assert 'Query cannot be empty' in error_events[0]['data']['error']


    @pytest.mark.asyncio
    async def test_tc_005b_query_with_missing_session_data(self, session):
        """TC-005b: Test query when session data is missing from socket session."""
        from websockets.chat_socket import handle_chat_query

        # Mock sio session with missing token
        mock_socket_session = {}

        # Mock emitted events
        emitted_events = []

        async def mock_emit(event, data, room=None):
            emitted_events.append({'event': event, 'data': data, 'room': room})

        # Mock sio.session context manager
        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
            with patch('websockets.chat_socket.sio.emit', mock_emit):
                # Execute handler
                query_data = {'query': 'Test query'}
                await handle_chat_query('test_sid', query_data)

                # Assertions
                error_events = [e for e in emitted_events if e['event'] == 'chat:error']
                assert len(error_events) == 1, "Should emit error event"
                assert 'Session not authenticated' in error_events[0]['data']['error']


class TestErrorHandling:
    """Test error scenarios in WebSocket handlers."""

    @pytest.mark.asyncio
    async def test_tc_006_rag_engine_error_handling(self, session, test_session):
        """TC-006: Test RAG engine error handling."""
        from websockets.chat_socket import handle_chat_query

        # Mock sio session
        mock_socket_session = {
            'session_token': test_session.session_token,
            'session_id': str(test_session.id)
        }

        # Mock emitted events
        emitted_events = []

        async def mock_emit(event, data, room=None):
            emitted_events.append({'event': event, 'data': data, 'room': room})

        # Mock sio.session context manager
        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
            with patch('websockets.chat_socket.sio.emit', mock_emit):
                with patch('websockets.chat_socket.get_db_session') as mock_get_db:
                    mock_db = AsyncMock()
                    mock_db.close = AsyncMock()
                    mock_db.add = MagicMock()
                    mock_db.flush = AsyncMock()
                    mock_get_db.return_value = mock_db

                    # Mock ChatService
                    with patch('websockets.chat_socket.ChatService') as mock_chat_service:
                        mock_service = MagicMock()
                        mock_service.validate_session = AsyncMock(return_value=test_session)
                        mock_chat_service.return_value = mock_service

                        # Mock RAGEngine to raise RAGError
                        with patch('websockets.chat_socket.RAGEngine') as mock_rag_engine:
                            mock_rag = MagicMock()
                            mock_rag.query = AsyncMock(side_effect=RAGError("LLM service unavailable"))
                            mock_rag_engine.return_value = mock_rag

                            # Execute handler
                            query_data = {'query': 'Trigger RAG error'}
                            await handle_chat_query('test_sid', query_data)

                            # Assertions
                            error_events = [e for e in emitted_events if e['event'] == 'chat:error']
                            assert len(error_events) == 1, "Should emit error event"
                            assert error_events[0]['data']['type'] == 'rag_error'
                            assert 'LLM service unavailable' in error_events[0]['data']['error']


    @pytest.mark.asyncio
    async def test_tc_006b_generic_exception_handling(self, session, test_session):
        """TC-006b: Test generic exception handling."""
        from websockets.chat_socket import handle_chat_query

        # Mock sio session
        mock_socket_session = {
            'session_token': test_session.session_token,
            'session_id': str(test_session.id)
        }

        # Mock emitted events
        emitted_events = []

        async def mock_emit(event, data, room=None):
            emitted_events.append({'event': event, 'data': data, 'room': room})

        # Mock sio.session context manager
        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
            with patch('websockets.chat_socket.sio.emit', mock_emit):
                with patch('websockets.chat_socket.get_db_session') as mock_get_db:
                    # Simulate unexpected exception
                    mock_get_db.side_effect = Exception("Unexpected database error")

                    # Execute handler
                    query_data = {'query': 'Trigger exception'}
                    await handle_chat_query('test_sid', query_data)

                    # Assertions
                    error_events = [e for e in emitted_events if e['event'] == 'chat:error']
                    assert len(error_events) == 1, "Should emit error event"
                    assert error_events[0]['data']['type'] == 'server_error'


class TestMessagePersistence:
    """Test message persistence to database."""

    @pytest.mark.asyncio
    async def test_tc_007_message_persistence(self, session, test_session):
        """TC-007: Test that user and assistant messages are saved to database."""
        from websockets.chat_socket import handle_chat_query

        # Mock sio session
        mock_socket_session = {
            'session_token': test_session.session_token,
            'session_id': str(test_session.id)
        }

        # Mock emitted events
        emitted_events = []

        async def mock_emit(event, data, room=None):
            emitted_events.append({'event': event, 'data': data, 'room': room})

        # Track added messages
        added_messages = []

        # Mock sio.session context manager
        class MockSessionContext:
            async def __aenter__(self):
                return mock_socket_session
            async def __aexit__(self, *args):
                pass

        with patch('websockets.chat_socket.sio.session', return_value=MockSessionContext()):
            with patch('websockets.chat_socket.sio.emit', mock_emit):
                with patch('websockets.chat_socket.get_db_session') as mock_get_db:
                    mock_db = AsyncMock()
                    mock_db.close = AsyncMock()
                    mock_db.flush = AsyncMock()
                    mock_db.commit = AsyncMock()

                    # Track messages added to db
                    def track_add(msg):
                        added_messages.append(msg)

                    mock_db.add = track_add
                    mock_get_db.return_value = mock_db

                    # Mock ChatService
                    with patch('websockets.chat_socket.ChatService') as mock_chat_service:
                        mock_service = MagicMock()
                        mock_service.validate_session = AsyncMock(return_value=test_session)
                        mock_chat_service.return_value = mock_service

                        # Mock RAGEngine with streaming response
                        async def mock_streaming_iterator():
                            chunks = ["Response", " text"]
                            for chunk in chunks:
                                yield chunk

                        with patch('websockets.chat_socket.RAGEngine') as mock_rag_engine:
                            mock_rag = MagicMock()
                            mock_rag.query = AsyncMock(return_value={
                                'streaming_iterator': mock_streaming_iterator(),
                                'sources': [],
                                'metadata': {}
                            })
                            mock_rag_engine.return_value = mock_rag

                            # Execute handler
                            query_data = {'query': 'Persistence test'}
                            await handle_chat_query('test_sid', query_data)

                            # Assertions
                            assert len(added_messages) == 2, "Should save 2 messages (user + assistant)"

                            # Check user message
                            user_msg = added_messages[0]
                            assert user_msg.role == MessageRole.USER
                            assert user_msg.content == 'Persistence test'
                            assert user_msg.session_id == test_session.id

                            # Check assistant message
                            assistant_msg = added_messages[1]
                            assert assistant_msg.role == MessageRole.ASSISTANT
                            assert assistant_msg.content == "Response text"
                            assert assistant_msg.session_id == test_session.id
                            assert assistant_msg.message_metadata['chunk_count'] == 2


class TestSetup:
    """Test WebSocket setup and integration."""

    def test_setup_socketio_integration(self):
        """Test setup_socketio creates ASGI app correctly."""
        from fastapi import FastAPI
        from websockets.chat_socket import setup_socketio

        # Create FastAPI app
        app = FastAPI()

        # Setup Socket.IO
        combined_app = setup_socketio(app)

        # Assertions
        assert combined_app is not None
        assert isinstance(combined_app, socketio.ASGIApp)


