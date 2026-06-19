"""
Chat Session Management Service

This module provides chat session services including session creation, validation,
token generation, Redis caching, and session history retrieval for anonymous users.
"""

import logging
import secrets
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.redis import session_set, session_get, session_extend
from models.chat import ChatSession, ChatMessage, MessageRole

# Logger
logger = logging.getLogger(__name__)

# Session configuration constants
SESSION_TOKEN_BYTES = 32  # 32 bytes = 256 bits for secure random token
SESSION_TTL_SECONDS = 24 * 60 * 60  # 24 hours in seconds


class ChatSessionError(Exception):
    """Custom exception for chat session errors."""
    pass


class ChatService:
    """
    Chat session management service for anonymous and authenticated users.
    
    This service handles:
    - Session creation with secure token generation
    - Session validation and Redis caching
    - Activity timestamp updates
    - Session history retrieval
    - Session data persistence in PostgreSQL and Redis
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the chat service.
        
        Args:
            db_session: Async database session for chat session queries
        """
        self.db = db_session
    
    def generate_session_token(self) -> str:
        """
        Generate a secure session token using cryptographically secure random bytes.
        
        The token is URL-safe and uses 32 random bytes (256 bits) for security.
        
        Returns:
            str: URL-safe session token (base64-encoded)
        """
        # Generate 32 random bytes and encode as URL-safe base64 string
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        logger.debug(f"Generated session token: {token[:10]}...")
        return token
    
    async def create_session(
        self,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> ChatSession:
        """
        Create a new chat session for anonymous or authenticated users.

        Creates a session record in the database and caches the session token
        in Redis with a 24-hour TTL.

        Args:
            ip_address: Client IP address (optional)
            user_agent: Browser user agent string (optional)
            user_id: User ID for authenticated users (optional, None for anonymous)

        Returns:
            ChatSession: The created session object

        Raises:
            ChatSessionError: If session creation fails
        """
        try:
            # Generate secure session token
            session_token = self.generate_session_token()

            # Create session object
            session = ChatSession(
                session_token=session_token,
                ip_address=ip_address,
                user_agent=user_agent,
                user_id=user_id
            )

            # Add to database
            self.db.add(session)
            await self.db.flush()  # Flush to get the session ID
            await self.db.refresh(session)  # Refresh to get server defaults

            # Cache session in Redis with 24-hour TTL
            session_data = json.dumps({
                "session_id": str(session.id),
                "user_id": user_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": session.started_at.isoformat()
            })

            await session_set(
                session_token=session_token,
                session_data=session_data,
                expire_seconds=SESSION_TTL_SECONDS
            )

            logger.info(
                f"Chat session created: session_id={session.id}, "
                f"user_id={user_id or 'anonymous'}, ip={ip_address}"
            )

            return session

        except Exception as e:
            logger.error(f"Failed to create chat session: {str(e)}")
            raise ChatSessionError(f"Session creation failed: {str(e)}")

    async def get_session(self, session_token: str) -> ChatSession:
        """
        Retrieve a session by token.

        First checks Redis cache for performance, then falls back to database.
        Updates the last_activity_at timestamp.

        Args:
            session_token: Session token to retrieve

        Returns:
            ChatSession object if found

        Raises:
            ChatSessionError: If session not found or expired
        """
        try:
            # Try to get session from Redis cache first
            cached_data = await session_get(session_token)

            if cached_data:
                # Parse cached data to get session_id
                session_info = json.loads(cached_data)
                session_id = UUID(session_info["session_id"])

                # Need to check if session has ended (cache doesn't store ended_at)
                # Query database to verify session is still active
                result = await self.db.execute(
                    select(ChatSession)
                    .where(ChatSession.id == session_id)
                    .where(ChatSession.ended_at.is_(None))  # Only active sessions
                )
                session = result.scalar_one_or_none()

                if not session:
                    # Session has ended
                    logger.warning(f"Session has ended: {session_token[:10]}...")
                    raise ChatSessionError("Session not found or expired")

                # Session found in cache and still active - extend TTL
                await session_extend(session_token, expire_seconds=SESSION_TTL_SECONDS)
                logger.debug(f"Session retrieved from cache: {session_token[:10]}...")
            else:
                # Session not in cache - query database
                logger.debug(f"Session not in cache, querying database: {session_token[:10]}...")

                result = await self.db.execute(
                    select(ChatSession)
                    .where(ChatSession.session_token == session_token)
                    .where(ChatSession.ended_at.is_(None))  # Only active sessions
                )
                session = result.scalar_one_or_none()

                if not session:
                    logger.warning(f"Invalid or expired session token: {session_token[:10]}...")
                    raise ChatSessionError("Session not found or expired")

                session_id = session.id

                # Re-cache the session
                session_data = json.dumps({
                    "session_id": str(session.id),
                    "user_id": session.user_id,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "created_at": session.started_at.isoformat()
                })

                await session_set(
                    session_token=session_token,
                    session_data=session_data,
                    expire_seconds=SESSION_TTL_SECONDS
                )

            # Update last_activity_at timestamp
            await self.db.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(last_activity_at=datetime.utcnow())
            )
            await self.db.flush()

            # Retrieve the updated session
            result = await self.db.execute(
                select(ChatSession)
                .where(ChatSession.id == session_id)
                .options(selectinload(ChatSession.messages))
            )
            session = result.scalar_one()

            logger.info(f"Session retrieved and activity updated: session_id={session_id}")
            return session

        except ChatSessionError:
            raise
        except Exception as e:
            logger.error(f"Session retrieval error: {str(e)}")
            raise ChatSessionError(f"Session retrieval failed: {str(e)}")

    async def validate_session(self, session_token: str) -> Optional[ChatSession]:
        """
        Validate a session token and return the session object.

        First checks Redis cache for performance, then falls back to database.
        Updates the last_activity_at timestamp on successful validation.

        Args:
            session_token: Session token to validate

        Returns:
            ChatSession object if valid, None if invalid or expired

        Raises:
            ChatSessionError: If validation fails due to database error
        """
        try:
            # Try to get session from Redis cache first
            cached_data = await session_get(session_token)

            if cached_data:
                # Parse cached data to get session_id
                session_info = json.loads(cached_data)
                session_id = UUID(session_info["session_id"])

                # Need to check if session has ended (cache doesn't store ended_at)
                # Query database to verify session is still active
                result = await self.db.execute(
                    select(ChatSession)
                    .where(ChatSession.id == session_id)
                    .where(ChatSession.ended_at.is_(None))  # Only active sessions
                )
                session = result.scalar_one_or_none()

                if not session:
                    # Session has ended - return None
                    logger.warning(f"Session has ended: {session_token[:10]}...")
                    return None

                # Session found in cache and still active - extend TTL
                await session_extend(session_token, expire_seconds=SESSION_TTL_SECONDS)
                logger.debug(f"Session validated from cache: {session_token[:10]}...")
            else:
                # Session not in cache - query database
                logger.debug(f"Session not in cache, querying database: {session_token[:10]}...")

                result = await self.db.execute(
                    select(ChatSession)
                    .where(ChatSession.session_token == session_token)
                    .where(ChatSession.ended_at.is_(None))  # Only active sessions
                )
                session = result.scalar_one_or_none()

                if not session:
                    logger.warning(f"Invalid or expired session token: {session_token[:10]}...")
                    return None

                # Re-cache the session
                session_data = json.dumps({
                    "session_id": str(session.id),
                    "user_id": session.user_id,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "created_at": session.started_at.isoformat()
                })

                await session_set(
                    session_token=session_token,
                    session_data=session_data,
                    expire_seconds=SESSION_TTL_SECONDS
                )

            # Update last_activity_at timestamp
            await self.db.execute(
                update(ChatSession)
                .where(ChatSession.id == session.id)
                .values(last_activity_at=datetime.utcnow())
            )
            await self.db.flush()

            logger.info(f"Session validated and activity updated: session_id={session.id}")
            return session

        except Exception as e:
            logger.error(f"Session validation error: {str(e)}")
            # Return None instead of raising exception for validation
            return None

    async def get_session_history(
        self,
        session_token: str,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """
        Retrieve chat message history for a session.

        Args:
            session_token: Session token to retrieve history for
            limit: Maximum number of messages to retrieve (optional)

        Returns:
            List of ChatMessage objects ordered by creation time

        Raises:
            ChatSessionError: If session is invalid or retrieval fails
        """
        try:
            # Get session first
            session = await self.get_session(session_token)

            # Query messages for this session
            query = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.asc())
            )

            if limit:
                query = query.limit(limit)

            result = await self.db.execute(query)
            messages = result.scalars().all()

            logger.info(
                f"Retrieved {len(messages)} messages for session {session.id}"
            )

            return list(messages)

        except ChatSessionError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve session history: {str(e)}")
            raise ChatSessionError(f"History retrieval failed: {str(e)}")

    async def add_message(
        self,
        session_token: str,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None
    ) -> ChatMessage:
        """
        Add a message to a chat session.

        Args:
            session_token: Session token
            role: Message role (user, assistant, or system)
            content: Message content
            metadata: Optional metadata (sources, tokens, etc.)

        Returns:
            ChatMessage: Created message object

        Raises:
            ChatSessionError: If session is invalid or message creation fails
        """
        try:
            # Get session first
            session = await self.get_session(session_token)

            # Create message
            message = ChatMessage(
                session_id=session.id,
                role=role,
                content=content,
                message_metadata=metadata
            )

            # Add to database
            self.db.add(message)
            await self.db.flush()
            await self.db.refresh(message)

            logger.info(
                f"Message added to session {session.id}: role={role.value}, "
                f"content_length={len(content)}"
            )

            return message

        except ChatSessionError:
            raise
        except Exception as e:
            logger.error(f"Failed to add message: {str(e)}")
            raise ChatSessionError(f"Message creation failed: {str(e)}")

    async def end_session(self, session_token: str) -> bool:
        """
        End a chat session by setting the ended_at timestamp.

        Args:
            session_token: Session token to end

        Returns:
            bool: True if session was ended, False if session not found

        Raises:
            ChatSessionError: If session termination fails
        """
        try:
            # Update session to mark as ended
            result = await self.db.execute(
                update(ChatSession)
                .where(ChatSession.session_token == session_token)
                .where(ChatSession.ended_at.is_(None))
                .values(ended_at=datetime.utcnow())
            )

            rows_updated = result.rowcount

            if rows_updated > 0:
                logger.info(f"Session ended: {session_token[:10]}...")
                return True
            else:
                logger.warning(f"Session not found or already ended: {session_token[:10]}...")
                return False

        except Exception as e:
            logger.error(f"Failed to end session: {str(e)}")
            raise ChatSessionError(f"Session termination failed: {str(e)}")
