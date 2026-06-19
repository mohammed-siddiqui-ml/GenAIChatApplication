"""
API v1 Router

Central router for all v1 API endpoints.
"""

from fastapi import APIRouter
from api.v1 import auth, chat, admin

# Create main API router
api_router = APIRouter()

# Include authentication endpoints
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Include chat endpoints
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"]
)

# Include admin endpoints
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"]
)
