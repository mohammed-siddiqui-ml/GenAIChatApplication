"""
FastAPI Main Application Entry Point

GenAI Intelligent Chat-Based Knowledge Retrieval System
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.logging import setup_logging

# Initialize logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager for startup and shutdown events.
    
    This handles initialization and cleanup of resources like database
    connections, background tasks, and external service clients.
    """
    logger.info("Starting up GenAI Knowledge Retrieval System...")
    
    # Startup logic
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"API Version: {settings.API_VERSION}")
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down application...")


# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="GenAI-powered chat-based knowledge retrieval application",
    version=settings.API_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint providing basic API information."""
    return JSONResponse(
        content={
            "message": "GenAI Knowledge Retrieval System API",
            "version": settings.API_VERSION,
            "status": "running",
        }
    )


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse(
        content={
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
        }
    )


# API Router registration will be added here as routes are developed
# Example:
# from api.v1.router import api_router
# app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    )
