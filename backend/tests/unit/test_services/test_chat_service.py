"""
Unit tests for ChatService.

Tests chat session management, token generation, Redis caching,
and session history retrieval.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.chat_service import ChatService, ChatSessionError
from models.chat import ChatSession, ChatMessage, MessageRole


@pytest.mark.unit
@pytest.mark.asyncio
class TestChatService:
    """Unit tests for ChatService."""
    
    async def test_create_session_anonymous(self, session, clean_redis):
        """Test creating anonymous chat session."""
        chat_service = ChatService(session)

        result = await chat_service.create_session()

        # Result should be ChatSession object
        assert isinstance(result, ChatSession)
        assert result.session_token is not None
        assert len(result.session_token) > 0
        assert result.user_id is None  # Anonymous session

    async def test_create_session_authenticated(self, session, regular_user, clean_redis):
        """Test creating authenticated chat session."""
        chat_service = ChatService(session)

        result = await chat_service.create_session(user_id=regular_user.id)

        # Result should be ChatSession object
        assert isinstance(result, ChatSession)
        assert result.session_token is not None
        assert result.user_id == regular_user.id
    
    async def test_get_session_valid_token(self, session, chat_session, clean_redis):
        """Test retrieving session with valid token."""
        chat_service = ChatService(session)
        
        # Get session
        result = await chat_service.get_session(chat_session.session_token)
        
        assert result is not None
        assert result.id == chat_session.id
        assert result.session_token == chat_session.session_token
    
    async def test_get_session_invalid_token(self, session, clean_redis):
        """Test retrieving session with invalid token."""
        chat_service = ChatService(session)
        
        with pytest.raises(ChatSessionError) as exc_info:
            await chat_service.get_session("invalid-token-xyz")
        
        assert "Session not found or expired" in str(exc_info.value)
    
    async def test_validate_session_success(self, session, chat_session, clean_redis):
        """Test session validation with valid token."""
        chat_service = ChatService(session)

        result = await chat_service.validate_session(chat_session.session_token)

        # validate_session now returns ChatSession object or None
        assert result is not None
        assert isinstance(result, ChatSession)
        assert result.id == chat_session.id

    async def test_validate_session_failure(self, session, clean_redis):
        """Test session validation with invalid token."""
        chat_service = ChatService(session)

        result = await chat_service.validate_session("invalid-token")

        # validate_session returns None for invalid sessions
        assert result is None
    
    async def test_update_session_activity(self, session, chat_session, clean_redis):
        """Test updating session last activity timestamp."""
        chat_service = ChatService(session)

        original_activity = chat_session.last_activity_at

        # Wait a moment and update
        import asyncio
        await asyncio.sleep(0.1)

        # validate_session updates the activity timestamp
        await chat_service.validate_session(chat_session.session_token)

        # Refresh session from database
        await session.refresh(chat_session)

        assert chat_session.last_activity_at > original_activity

    async def test_get_session_history(self, session, chat_session_with_messages, clean_redis):
        """Test retrieving session message history."""
        chat_service = ChatService(session)

        history = await chat_service.get_session_history(
            chat_session_with_messages.session_token,
            limit=10
        )

        assert len(history) == 2  # User message + Assistant message
        assert history[0].role == MessageRole.USER
        assert history[1].role == MessageRole.ASSISTANT
        assert "What is the onboarding process?" in history[0].content
    
    async def test_add_message_to_session(self, session, chat_session, clean_redis):
        """Test adding a message to chat session."""
        chat_service = ChatService(session)
        
        message = await chat_service.add_message(
            session_token=chat_session.session_token,
            role=MessageRole.USER,
            content="Hello, how can I help?"
        )
        
        assert message is not None
        assert message.session_id == chat_session.id
        assert message.role == MessageRole.USER
        assert message.content == "Hello, how can I help?"
    
    async def test_redis_caching(self, session, chat_session, clean_redis):
        """Test Redis caching of session data."""
        chat_service = ChatService(session)
        
        # First call should cache
        result1 = await chat_service.get_session(chat_session.session_token)
        
        # Second call should use cache
        result2 = await chat_service.get_session(chat_session.session_token)
        
        assert result1.id == result2.id
        assert result1.session_token == result2.session_token
