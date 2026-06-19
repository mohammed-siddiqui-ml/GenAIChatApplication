"""
FastAPI Main Application Entry Point

GenAI Intelligent Chat-Based Knowledge Retrieval System
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from core.config import settings
from core.logging import setup_logging
from core.database import init_db, close_db, check_db_health
from core.redis import init_redis, close_redis, check_redis_health

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

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Initialize Redis
    try:
        await init_redis()
        logger.info("Redis initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise

    yield

    # Shutdown logic
    logger.info("Shutting down application...")

    # Close Redis connections
    try:
        await close_redis()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis connections: {e}")

    # Close database connections
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


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

# Configure Logging Middleware for request context and structured logging
from middleware.logging_middleware import LoggingMiddleware
app.add_middleware(LoggingMiddleware)

# Configure Prometheus metrics instrumentation
# This automatically collects HTTP request metrics (count, duration, error rate)
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=False,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/ready"],  # Exclude health checks from metrics
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

# Add default metrics (request count, duration with percentiles)
instrumentator.instrument(app)

# Expose metrics endpoint at /api/v1/metrics
# This will be scraped by Prometheus
instrumentator.expose(app, endpoint=f"{settings.API_V1_PREFIX}/metrics", include_in_schema=True)

logger.info(f"Prometheus metrics enabled at {settings.API_V1_PREFIX}/metrics")


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


@app.get("/ready")
async def readiness_check() -> JSONResponse:
    """
    Readiness check endpoint for Kubernetes/Docker health probes.

    Verifies that the application is ready to serve traffic by checking:
    - Database connectivity
    - Redis connectivity
    - Connection pool availability
    """
    db_healthy = await check_db_health()
    redis_healthy = await check_redis_health()

    if db_healthy and redis_healthy:
        return JSONResponse(
            content={
                "status": "ready",
                "database": "connected",
                "redis": "connected",
            }
        )
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not ready",
                "database": "connected" if db_healthy else "disconnected",
                "redis": "connected" if redis_healthy else "disconnected",
            }
        )


# API Router registration
from api.v1.router import api_router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Socket.IO integration
from websockets.chat_socket import setup_socketio

# Create combined ASGI app with Socket.IO support
# This wraps the FastAPI app to handle both HTTP and WebSocket traffic
app_with_socketio = setup_socketio(app)


if __name__ == "__main__":
    import uvicorn

    # Run the combined app with Socket.IO support
    uvicorn.run(
        "main:app_with_socketio",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    )
