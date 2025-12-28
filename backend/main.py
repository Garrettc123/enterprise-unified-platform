from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .database import init_db
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .websocket_manager import ConnectionManager
from .routers import auth, projects, tasks, organizations, analytics, notifications, files, search, export, audit

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
    logger.info("📊 Analytics system ready")
    logger.info("🔐 Authentication system active")
    logger.info("👥 Team collaboration features enabled")
    yield
    # Shutdown
    logger.info("💤 Shutting down")

# Create FastAPI app
app = FastAPI(
    title="Enterprise Unified Platform",
    description="Comprehensive enterprise management system with project management, task tracking, analytics, and real-time collaboration",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
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
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Enterprise Unified Platform",
        "version": "1.0.0",
        "active_connections": ws_manager.get_connection_count()
    }

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Enterprise Unified Platform",
        "version": "1.0.0",
        "documentation": "/docs",
        "features": [
            "Project Management",
            "Task Tracking",
            "Team Collaboration",
            "Analytics & Reporting",
            "File Management",
            "Advanced Search",
            "Data Export",
            "Audit Logging",
            "Real-time Updates",
            "API Key Management"
        ]
    }

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            # Broadcast to all clients
            await ws_manager.broadcast_json({
                "type": "message",
                "client_id": client_id,
                "data": data,
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            })
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        ws_manager.disconnect(websocket)

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("\n" + "="*60)
    logger.info("Enterprise Unified Platform v1.0.0")
    logger.info("="*60)
    logger.info("✅ Authentication & Security")
    logger.info("✅ Project & Task Management")
    logger.info("✅ Team Collaboration")
    logger.info("✅ Analytics & Insights")
    logger.info("✅ File Management")
    logger.info("✅ Advanced Search")
    logger.info("✅ Data Export")
    logger.info("✅ Audit Logging")
    logger.info("✅ Real-time Updates")
    logger.info("="*60 + "\n")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Enterprise Unified Platform...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)