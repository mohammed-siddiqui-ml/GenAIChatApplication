"""
API v1 Router

Central router for all v1 API endpoints.
"""

from fastapi import APIRouter

# Create main API router
api_router = APIRouter()

# Import and include routers from different modules
# Example:
# from api.v1.endpoints import chat, admin, health
# api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
# api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
