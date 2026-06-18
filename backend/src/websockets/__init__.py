"""
WebSocket handlers for real-time communication.

This module provides Socket.IO event handlers for chat functionality.
"""

from .chat_socket import sio, setup_socketio

__all__ = ["sio", "setup_socketio"]
