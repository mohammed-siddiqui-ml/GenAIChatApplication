"""
WebSocket handlers for real-time communication.

This module provides Socket.IO event handlers for chat functionality
and ingestion job status updates.
"""

from .chat_socket import sio, setup_socketio
# Import ingestion socket to register event handlers
from . import ingestion_socket

__all__ = ["sio", "setup_socketio", "ingestion_socket"]
