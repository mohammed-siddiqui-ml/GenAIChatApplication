"""
API v1 Router

Central router for all v1 API endpoints.
"""

from fastapi import APIRouter
from api.v1 import auth

# Create main API router
api_router = APIRouter()

# Include authentication endpoints
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Import and include routers from different modules
# Example:
# from api.v1.endpoints import chat, admin, health
# api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
# api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
