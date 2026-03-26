from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

from .database import init_db
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .websocket_manager import ConnectionManager
from .routers import auth, projects, tasks, organizations, analytics, notifications, files, search, export, audit, revenue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ws_manager = ConnectionManager()

_CORS_ORIGINS = [
    "https://garcarenterprise.com",
    "https://ueep.vercel.app",
    "https://www.garcarenterprise.com",
]
if extra := os.environ.get("CORS_EXTRA_ORIGINS", ""):
    _CORS_ORIGINS += [o.strip() for o in extra.split(",") if o.strip()]
if os.environ.get("ENVIRONMENT", "production") != "production":
    _CORS_ORIGINS += ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Enterprise Unified Platform")
    await init_db()
    logger.info("✅ Database initialized")
    logger.info("💰 MoneyEngine ready — Stripe + GENESIS active")
    logger.info("🔐 Authentication system active")
    logger.info("📊 Analytics system ready")
    logger.info("👥 Team collaboration features enabled")
    yield
    logger.info("💤 Shutting down Enterprise Unified Platform")


app = FastAPI(
    title="Enterprise Unified Platform",
    description="Autonomous revenue + enterprise management system — Garcar Enterprise",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "stripe-signature", "X-Request-ID"],
)

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


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Enterprise Unified Platform",
        "version": "2.0.0",
        "active_ws_connections": ws_manager.get_connection_count(),
    }


@app.get("/")
async def root():
    return {
        "message": "Enterprise Unified Platform — Garcar Enterprise",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "revenue": "/revenue/health",
    }


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.broadcast_json({
                "type": "message",
                "client_id": client_id,
                "data": data,
                "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            })
    except Exception as e:
        logger.error("WebSocket error for client %s: %s", client_id, e)
    finally:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
