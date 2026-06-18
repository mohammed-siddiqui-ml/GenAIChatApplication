"""
Tests for Chat Session Management Service (Task 014)

Test scenarios:
- Session token generation (uniqueness, format, security)
- Session creation (anonymous/authenticated users)
- Session validation (cache hit/miss, activity updates)
- Session history retrieval
- Session termination
- Activity timestamp tracking
"""

import pytest
import pytest_asyncio
import asyncio
import json
from datetime import datetime, timedelta
from uuid import UUID

from services.chat_service import ChatService, ChatSessionError
from models.chat import ChatSession, ChatMessage, MessageRole


# ==================== Session Token Generation Tests ====================

@pytest.mark.asyncio
async def test_generate_unique_tokens(db_session):
    """TC-A1: Generate 1000 unique session tokens."""
    service = ChatService(db_session)
    
    # Generate 1000 tokens
    tokens = [service.generate_session_token() for _ in range(1000)]
    
    # Verify all tokens are unique
    unique_tokens = set(tokens)
    assert len(unique_tokens) == 1000, "All tokens should be unique"


@pytest.mark.asyncio
async def test_token_format_validation(db_session):
    """TC-A2: Validate token format (URL-safe base64)."""
    service = ChatService(db_session)
    
    token = service.generate_session_token()
    
    # Check token is string
    assert isinstance(token, str), "Token should be a string"
    
    # Check token length (32 bytes = 43 chars in URL-safe base64)
    assert len(token) == 43, f"Expected 43 chars, got {len(token)}"
    
    # Check URL-safe characters only [A-Za-z0-9_-]
    import re
    assert re.match(r'^[A-Za-z0-9_-]+$', token), "Token should be URL-safe base64"


# ==================== Session Creation Tests ====================

@pytest.mark.asyncio
async def test_create_anonymous_session(db_session, clean_redis):
    """TC-B1: Create session for anonymous user."""
    service = ChatService(db_session)
    
    # Create session
    session = await service.create_session(
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0 Chrome/91.0",
        user_id=None
    )
    
    # Verify session properties
    assert session is not None
    assert session.session_token is not None
    assert len(session.session_token) == 43
    assert session.user_id is None
    assert session.ip_address == "192.168.1.1"
    assert session.user_agent == "Mozilla/5.0 Chrome/91.0"
    assert session.started_at is not None
    assert session.last_activity_at is not None
    assert session.ended_at is None
    
    # Verify session is in database
    await db_session.commit()
    await db_session.refresh(session)
    assert session.id is not None


@pytest.mark.asyncio
async def test_create_authenticated_session(db_session, clean_redis, regular_user):
    """TC-B2: Create session for authenticated user."""
    service = ChatService(db_session)
    
    # Create session with user_id
    session = await service.create_session(
        ip_address="10.0.0.1",
        user_agent="Safari/14.0",
        user_id=regular_user.id
    )
    
    # Verify session has user_id
    assert session.user_id == regular_user.id
    assert session.ip_address == "10.0.0.1"
    assert session.user_agent == "Safari/14.0"
    
    # Verify persistence
    await db_session.commit()
    await db_session.refresh(session)
    assert session.id is not None


# ==================== Session Validation Tests ====================

@pytest.mark.asyncio
async def test_validate_session_from_cache(db_session, clean_redis):
    """TC-C1: Validate session from Redis cache (cache hit)."""
    service = ChatService(db_session)
    
    # Create session
    session = await service.create_session(
        ip_address="192.168.1.100",
        user_agent="Chrome/91.0"
    )
    await db_session.commit()
    
    original_activity = session.last_activity_at
    
    # Wait a moment to ensure timestamp difference
    await asyncio.sleep(0.1)
    
    # Validate session (should hit cache)
    validated_session = await service.validate_session(session.session_token)
    
    # Verify session returned
    assert validated_session is not None
    assert validated_session.id == session.id
    assert validated_session.session_token == session.session_token
    
    # Verify activity timestamp was updated
    await db_session.refresh(validated_session)
    assert validated_session.last_activity_at > original_activity


@pytest.mark.asyncio
async def test_validate_session_from_database(db_session, clean_redis):
    """TC-C2: Validate session from database when cache miss."""
    service = ChatService(db_session)
    
    # Create session
    session = await service.create_session(
        ip_address="10.0.0.50",
        user_agent="Firefox/89.0"
    )
    await db_session.commit()
    
    # Delete from Redis to simulate cache miss
    await clean_redis.delete(f"session:{session.session_token}")

    # Wait a moment
    await asyncio.sleep(0.1)

    # Validate session (should fetch from database)
    validated_session = await service.validate_session(session.session_token)

    # Verify session returned from database
    assert validated_session is not None
    assert validated_session.id == session.id


@pytest.mark.asyncio
async def test_validate_invalid_session_token(db_session, clean_redis):
    """TC-C3: Reject invalid session token."""
    service = ChatService(db_session)

    # Try to validate non-existent token
    result = await service.validate_session("invalid-token-12345")

    # Verify None is returned
    assert result is None


@pytest.mark.asyncio
async def test_filter_ended_sessions(db_session, clean_redis):
    """TC-C4: Validation fails for sessions with ended_at set."""
    service = ChatService(db_session)

    # Create session
    session = await service.create_session(
        ip_address="192.168.1.200",
        user_agent="Chrome/91.0"
    )
    await db_session.commit()

    # End the session
    ended = await service.end_session(session.session_token)
    assert ended is True
    await db_session.commit()

    # Try to validate ended session
    result = await service.validate_session(session.session_token)

    # Verify None is returned for ended session
    assert result is None


# ==================== Session History Tests ====================

@pytest.mark.asyncio
async def test_retrieve_session_history(db_session, clean_redis):
    """TC-D1: Retrieve all messages for a session."""
    service = ChatService(db_session)

    # Create session
    session = await service.create_session(
        ip_address="10.0.0.100",
        user_agent="Safari/14.0"
    )
    await db_session.commit()

    # Create 5 messages
    messages_data = [
        (MessageRole.USER, "Hello"),
        (MessageRole.ASSISTANT, "Hi there!"),
        (MessageRole.USER, "How are you?"),
        (MessageRole.ASSISTANT, "I'm doing well, thanks!"),
        (MessageRole.USER, "Great!")
    ]

    for i, (role, content) in enumerate(messages_data):
        message = ChatMessage(
            session_id=session.id,
            role=role,
            content=content,
            created_at=datetime.utcnow() + timedelta(milliseconds=i*10)
        )
        db_session.add(message)
        await db_session.flush()  # Flush to generate ID immediately
        await asyncio.sleep(0.01)  # Ensure different timestamps

    await db_session.commit()

    # Retrieve history
    history = await service.get_session_history(session.session_token)

    # Verify all 5 messages returned
    assert len(history) == 5

    # Verify chronological order
    for i in range(len(history) - 1):
        assert history[i].created_at <= history[i + 1].created_at

    # Verify content matches
    assert history[0].content == "Hello"
    assert history[1].content == "Hi there!"


@pytest.mark.asyncio
async def test_retrieve_limited_history(db_session, clean_redis):
    """TC-D2: Retrieve limited number of messages."""
    service = ChatService(db_session)

    # Create session
    session = await service.create_session(
        ip_address="10.0.0.150",
        user_agent="Chrome/92.0"
    )
    await db_session.commit()

    # Create 10 messages
    for i in range(10):
        message = ChatMessage(
            session_id=session.id,
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content=f"Message {i}",
            created_at=datetime.utcnow() + timedelta(milliseconds=i*10)
        )
        db_session.add(message)
        await db_session.flush()  # Flush to generate ID immediately
        await asyncio.sleep(0.01)

    await db_session.commit()

    # Retrieve limited history
    history = await service.get_session_history(session.session_token, limit=3)

    # Verify exactly 3 messages returned
    assert len(history) == 3

    # Verify they are the first 3 messages (oldest)
    assert history[0].content == "Message 0"
    assert history[1].content == "Message 1"
    assert history[2].content == "Message 2"


@pytest.mark.asyncio
async def test_empty_session_history(db_session, clean_redis):
    """TC-D3: Handle empty message history."""
    service = ChatService(db_session)

    # Create session with no messages
    session = await service.create_session(
        ip_address="192.168.1.50",
        user_agent="Firefox/90.0"
    )
    await db_session.commit()

    # Retrieve history
    history = await service.get_session_history(session.session_token)

    # Verify empty list returned
    assert history == []
    assert len(history) == 0


@pytest.mark.asyncio
async def test_history_invalid_token(db_session, clean_redis):
    """TC-D5: Return error for invalid session token."""
    service = ChatService(db_session)

    # Try to get history for invalid token
    with pytest.raises(ChatSessionError):
        await service.get_session_history("invalid-token-xyz")


# ==================== Session Termination Tests ====================

@pytest.mark.asyncio
async def test_end_active_session(db_session, clean_redis):
    """TC-E1: Terminate an active session."""
    service = ChatService(db_session)

    # Create session
    session = await service.create_session(
        ip_address="10.0.0.200",
        user_agent="Safari/15.0"
    )
    await db_session.commit()

    # End the session
    before_end = datetime.utcnow()
    result = await service.end_session(session.session_token)
    after_end = datetime.utcnow()

    # Verify True returned
    assert result is True

    # Query database to confirm ended_at is set
    await db_session.commit()
    await db_session.refresh(session)

    assert session.ended_at is not None
    assert before_end <= session.ended_at <= after_end


@pytest.mark.asyncio
async def test_end_invalid_session(db_session, clean_redis):
    """TC-E4: Handle invalid session token."""
    service = ChatService(db_session)

    # Try to end non-existent session
    result = await service.end_session("invalid-token-abc")

    # Verify False returned
    assert result is False


# ==================== Activity Tracking Tests ====================

@pytest.mark.asyncio
async def test_activity_timestamp_updates(db_session, clean_redis):
    """TC-F1: Track activity across multiple validations."""
    service = ChatService(db_session)

    # Create session
    session = await service.create_session(
        ip_address="192.168.1.250",
        user_agent="Chrome/93.0"
    )
    await db_session.commit()

    initial_activity = session.last_activity_at

    # First validation
    await asyncio.sleep(0.2)
    validated1 = await service.validate_session(session.session_token)
    await db_session.refresh(validated1)
    activity1 = validated1.last_activity_at

    # Second validation
    await asyncio.sleep(0.2)
    validated2 = await service.validate_session(session.session_token)
    await db_session.refresh(validated2)
    activity2 = validated2.last_activity_at

    # Verify timestamps increase monotonically
    assert initial_activity < activity1
    assert activity1 < activity2
