from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .database import init_db
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .websocket_manager import ConnectionManager
from .routers import auth, projects, tasks, organizations, analytics, notifications, files, search, export, audit, revenue

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

# OpenAPI tag descriptions for Swagger documentation
tags_metadata = [
    {
        "name": "auth",
        "description": "Authentication and authorization. Register users, login to obtain JWT tokens, manage API keys, and retrieve user profiles.",
    },
    {
        "name": "projects",
        "description": "Project management. Create, read, update, and archive projects within organizations.",
    },
    {
        "name": "tasks",
        "description": "Task tracking. Create, manage, and track tasks within projects. Includes task comments and assignments.",
    },
    {
        "name": "organizations",
        "description": "Organization management. Create organizations, manage members and roles.",
    },
    {
        "name": "analytics",
        "description": "Analytics and reporting. Dashboard metrics, project status breakdowns, task trends, and team workload analysis.",
    },
    {
        "name": "notifications",
        "description": "User notifications. View, mark as read, and manage notifications.",
    },
    {
        "name": "files",
        "description": "File management. Upload, download, and delete file attachments on tasks.",
    },
    {
        "name": "search",
        "description": "Advanced search. Global search across projects, tasks, and users within an organization.",
    },
    {
        "name": "export",
        "description": "Data export. Export projects and tasks in CSV or JSON format.",
    },
    {
        "name": "audit",
        "description": "Audit logging. View audit trails, user activity logs, and summary statistics.",
    },
]

# Create FastAPI app
app = FastAPI(
    title="Enterprise Unified Platform",
    description="""
## Overview

A comprehensive enterprise management system providing project management, task tracking,
analytics, and real-time collaboration capabilities.

### Features

* **Authentication & Security** — JWT-based auth with API key support
* **Project Management** — Full CRUD for projects within organizations
* **Task Tracking** — Create, assign, and track tasks with comments
* **Team Collaboration** — Organization and member management
* **Analytics & Reporting** — Dashboard metrics, trends, and workload analysis
* **File Management** — Upload and manage file attachments
* **Advanced Search** — Global search across all entities
* **Data Export** — Export data in CSV and JSON formats
* **Audit Logging** — Complete audit trail of all operations
* **Real-time Updates** — WebSocket support for live notifications

### Authentication

Most endpoints require a Bearer token obtained via the `/login` endpoint:

```
Authorization: Bearer <access_token>
```
""",
    version="1.0.0",
    openapi_tags=tags_metadata,
    contact={
        "name": "Enterprise Platform Support",
        "email": "support@enterprise-platform.io",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
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
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(organizations.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(files.router)
app.include_router(search.router)
app.include_router(export.router)
app.include_router(audit.router)
app.include_router(revenue.router)

# Health check
@app.get("/health", tags=["health"], summary="Health check")
async def health_check():
    """Check the health of the API service.

    Returns the service status, version, and number of active WebSocket
    connections.
    """
    return {
        "status": "healthy",
        "service": "Enterprise Unified Platform",
        "version": "1.0.0",
        "active_connections": ws_manager.get_connection_count()
    }

# Root endpoint
@app.get("/", tags=["health"], summary="API root")
async def root():
    """API root returning service information, documentation link, and available features."""
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
            "API Key Management",
            "Revenue Management"
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
    logger.info("✅ Revenue Management")
    logger.info("="*60 + "\n")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Enterprise Unified Platform...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)