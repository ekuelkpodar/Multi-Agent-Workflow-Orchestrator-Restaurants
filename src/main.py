"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.state.manager import get_state_manager
from src.utils.logging import get_logger, setup_logging

# Setup logging first
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("application_starting")

    # Initialize state manager
    state_manager = await get_state_manager()
    logger.info("state_manager_initialized")

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await state_manager.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Multi-Agent Restaurant Orchestrator",
    description="Production-grade multi-agent AI system for restaurant operations",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "multi-agent-orchestrator"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Multi-Agent Restaurant Orchestrator API",
        "docs": "/docs",
        "health": "/health",
    }


# Import and include routers
from src.api.routes import router
from src.api.websocket import handle_websocket_conversation

app.include_router(router, prefix="/api/v1", tags=["api"])


# WebSocket endpoint
@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str) -> None:
    """WebSocket endpoint for real-time conversations."""
    from uuid import UUID

    try:
        conv_uuid = UUID(conversation_id)
        await handle_websocket_conversation(websocket, conv_uuid)
    except ValueError:
        await websocket.close(code=1003, reason="Invalid conversation ID")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
    )
