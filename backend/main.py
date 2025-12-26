from fastapi import FastAPI, WebSocket, Depends
from fastapi.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .database import init_db
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .websocket_manager import ConnectionManager
from .routers import auth, projects, tasks, organizations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# WebSocket manager
ws_manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Enterprise Unified Platform")
    await init_db()
    logger.info("✅ Database initialized")
    yield
    # Shutdown
    logger.info("💤 Shutting down")

# Create FastAPI app
app = FastAPI(
    title="Enterprise Unified Platform",
    description="Comprehensive enterprise management system",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(organizations.router)

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_connections": ws_manager.get_connection_count()
    }

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Enterprise Unified Platform",
        "version": "1.0.0",
        "documentation": "/docs"
    }

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            # Broadcast to all clients
            await ws_manager.broadcast(
                f"Client {client_id}: {data}"
            )
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        ws_manager.disconnect(websocket)