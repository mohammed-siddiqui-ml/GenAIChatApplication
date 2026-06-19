"""
Socket.IO WebSocket Handlers for Real-Time Ingestion Job Updates

This module implements Socket.IO event handlers for broadcasting real-time
ingestion job status updates to admin clients.

Events:
    - ingestion:subscribe: Admin subscribes to job updates for a specific job
    - ingestion:unsubscribe: Admin unsubscribes from job updates
    - ingestion:status: Server broadcasts job status updates
    - ingestion:progress: Server broadcasts job progress updates
    - ingestion:complete: Server broadcasts job completion
    - ingestion:error: Server broadcasts job errors
"""

import logging
from typing import Dict, Any
from datetime import datetime

from websockets.chat_socket import sio
from core.security import decode_token

# Logger
logger = logging.getLogger(__name__)


@sio.on('ingestion:subscribe')
async def handle_ingestion_subscribe(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle admin subscription to ingestion job updates.
    
    Admins can subscribe to specific job IDs to receive real-time updates.
    
    Args:
        sid: Socket.IO session ID
        data: Dictionary with 'job_id' and optional 'token' for authentication
        
    Emits:
        - ingestion:subscribed: Confirmation of subscription
        - ingestion:error: Error message if subscription fails
    """
    try:
        job_id = data.get('job_id')
        token = data.get('token')
        
        if not job_id:
            await sio.emit('ingestion:error', {
                'error': 'job_id is required',
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            return
        
        # Validate admin token (optional but recommended for production)
        # if token:
        #     payload = decode_token(token)
        #     if not payload or payload.get('role') != 'admin':
        #         await sio.emit('ingestion:error', {
        #             'error': 'Admin access required',
        #             'timestamp': datetime.utcnow().isoformat()
        #         }, room=sid)
        #         return
        
        # Join room for this specific job
        room_name = f"ingestion_job_{job_id}"
        await sio.enter_room(sid, room_name)
        
        logger.info(f"Admin {sid} subscribed to ingestion job {job_id}")
        
        await sio.emit('ingestion:subscribed', {
            'job_id': job_id,
            'message': f'Subscribed to updates for job {job_id}',
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)
        
    except Exception as e:
        logger.error(f"Error in ingestion subscribe: {e}", exc_info=True)
        await sio.emit('ingestion:error', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)


@sio.on('ingestion:unsubscribe')
async def handle_ingestion_unsubscribe(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle admin unsubscription from ingestion job updates.
    
    Args:
        sid: Socket.IO session ID
        data: Dictionary with 'job_id'
        
    Emits:
        - ingestion:unsubscribed: Confirmation of unsubscription
        - ingestion:error: Error message if unsubscription fails
    """
    try:
        job_id = data.get('job_id')
        
        if not job_id:
            await sio.emit('ingestion:error', {
                'error': 'job_id is required',
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            return
        
        # Leave room for this specific job
        room_name = f"ingestion_job_{job_id}"
        await sio.leave_room(sid, room_name)
        
        logger.info(f"Admin {sid} unsubscribed from ingestion job {job_id}")
        
        await sio.emit('ingestion:unsubscribed', {
            'job_id': job_id,
            'message': f'Unsubscribed from updates for job {job_id}',
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)
        
    except Exception as e:
        logger.error(f"Error in ingestion unsubscribe: {e}", exc_info=True)
        await sio.emit('ingestion:error', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)


# Helper functions to broadcast job updates from Celery tasks
async def broadcast_job_status(
    job_id: int,
    status: str,
    metadata: Dict[str, Any] = None
) -> None:
    """
    Broadcast job status update to subscribed clients.
    
    This function should be called from Celery tasks to push updates.
    
    Args:
        job_id: ID of the ingestion job
        status: New status (pending, running, success, failed)
        metadata: Additional metadata to include
    """
    room_name = f"ingestion_job_{job_id}"
    await sio.emit('ingestion:status', {
        'job_id': job_id,
        'status': status,
        'metadata': metadata or {},
        'timestamp': datetime.utcnow().isoformat()
    }, room=room_name)
    logger.debug(f"Broadcast status update for job {job_id}: {status}")
