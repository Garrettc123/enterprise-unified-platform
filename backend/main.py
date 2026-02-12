from fastapi import FastAPI, WebSocket, Depends
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import json

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

# WebSocket endpoint for real-time messaging
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time messaging

    Supported message types (send as JSON):
      - {"type": "message", "data": "..."} — broadcast to all clients
      - {"type": "direct", "target_client_id": "...", "data": "..."} — send to one client
      - {"type": "join_room", "room_id": "..."} — join a chat room
      - {"type": "leave_room", "room_id": "..."} — leave a chat room
      - {"type": "room_message", "room_id": "...", "data": "..."} — message to room members
      - {"type": "ping"} — server replies with pong
    """
    await ws_manager.connect(websocket, client_id)
    # Notify others about the new connection
    await ws_manager.broadcast_json({
        "type": "system",
        "event": "client_connected",
        "client_id": client_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Treat plain text as a broadcast message
                data = {"type": "message", "data": raw}

            msg_type = data.get("type", "message")
            timestamp = datetime.now(timezone.utc).isoformat()

            if msg_type == "message":
                await ws_manager.broadcast_json({
                    "type": "message",
                    "client_id": client_id,
                    "data": data.get("data", ""),
                    "timestamp": timestamp,
                })

            elif msg_type == "direct":
                target = data.get("target_client_id")
                if target:
                    payload = {
                        "type": "direct",
                        "client_id": client_id,
                        "data": data.get("data", ""),
                        "timestamp": timestamp,
                    }
                    await ws_manager.send_to_client(target, payload)
                    # Echo back to sender
                    await ws_manager.send_to_client(client_id, payload)

            elif msg_type == "join_room":
                room_id = data.get("room_id")
                if room_id:
                    ws_manager.join_room(room_id, client_id)
                    await ws_manager.broadcast_to_room(room_id, {
                        "type": "system",
                        "event": "room_joined",
                        "room_id": room_id,
                        "client_id": client_id,
                        "timestamp": timestamp,
                    })

            elif msg_type == "leave_room":
                room_id = data.get("room_id")
                if room_id:
                    ws_manager.leave_room(room_id, client_id)
                    await ws_manager.broadcast_to_room(room_id, {
                        "type": "system",
                        "event": "room_left",
                        "room_id": room_id,
                        "client_id": client_id,
                        "timestamp": timestamp,
                    })

            elif msg_type == "room_message":
                room_id = data.get("room_id")
                if room_id:
                    await ws_manager.broadcast_to_room(room_id, {
                        "type": "room_message",
                        "room_id": room_id,
                        "client_id": client_id,
                        "data": data.get("data", ""),
                        "timestamp": timestamp,
                    })

            elif msg_type == "ping":
                await ws_manager.send_to_client(client_id, {
                    "type": "pong",
                    "timestamp": timestamp,
                })

    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
    finally:
        ws_manager.disconnect(websocket, client_id)
        await ws_manager.broadcast_json({
            "type": "system",
            "event": "client_disconnected",
            "client_id": client_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

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