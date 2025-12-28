"""Main FastAPI application with autonomous sync orchestration integration."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio

from sync_engine import AutonomousSyncEngine, SyncConfig
from database_sync import DatabaseSyncManager, DatabaseConfig, DatabaseType, SyncDirection
from service_integration import ServiceIntegrationOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Enterprise Unified Platform API",
    description="$104M+ Multi-System Integration Hub with Autonomous Sync",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator: Optional[ServiceIntegrationOrchestrator] = None
orchestration_task: Optional[asyncio.Task] = None


# ============================================================================
# INITIALIZATION ENDPOINTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator on app startup."""
    global orchestrator
    logger.info("Initializing autonomous sync orchestration...")
    orchestrator = ServiceIntegrationOrchestrator()
    orchestrator.configure_cloud_sync()
    orchestrator.configure_database_sync()
    logger.info("Orchestrator initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global orchestrator, orchestration_task
    if orchestrator:
        orchestrator.is_running = False
    if orchestration_task:
        orchestration_task.cancel()
    logger.info("Application shutdown complete")


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint - Health check and API info."""
    return {
        "status": "healthy",
        "service": "Enterprise Unified Platform",
        "version": "1.0.0",
        "description": "$104M+ Multi-System Integration Hub with Autonomous Sync",
        "features": [
            "Real-time Code Deployment",
            "Multi-Cloud Synchronization",
            "Database Replication",
            "Health Monitoring",
            "Webhook Integration"
        ],
        "docs": "/docs",
        "redoc": "/redoc",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "enterprise-unified-platform",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/info")
async def api_info() -> Dict[str, Any]:
    """API information endpoint."""
    return {
        "name": "Enterprise Unified Platform",
        "description": "$104M+ Multi-System Integration Hub",
        "version": "1.0.0",
        "capabilities": [
            "Autonomous Sync Engine",
            "Multi-Cloud Deployment",
            "Database Replication",
            "Real-time Monitoring",
            "Webhook Triggers"
        ],
        "api_endpoints": {
            "orchestration": "/api/v1/orchestration/",
            "sync_engine": "/api/v1/sync/",
            "database": "/api/v1/database/"
        }
    }


# ============================================================================
# ORCHESTRATION CONTROL ENDPOINTS
# ============================================================================

@app.post("/api/v1/orchestration/start")
async def start_orchestration(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Start autonomous sync orchestration."""
    global orchestrator, orchestration_task

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    if orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Orchestration already running")

    logger.info("Starting autonomous sync orchestration...")
    orchestration_task = asyncio.create_task(orchestrator.run_full_autonomous_sync())

    return {
        "status": "started",
        "message": "Autonomous sync orchestration started",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/v1/orchestration/stop")
async def stop_orchestration() -> Dict[str, Any]:
    """Stop autonomous sync orchestration."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    if not orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Orchestration not running")

    orchestrator.is_running = False
    logger.info("Stopping orchestration...")

    return {
        "status": "stopped",
        "message": "Autonomous sync orchestration stopped",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# STATUS & MONITORING ENDPOINTS
# ============================================================================

@app.get("/api/v1/orchestration/status")
async def get_orchestration_status() -> Dict[str, Any]:
    """Get complete orchestration status."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    return orchestrator.get_full_status()


@app.get("/api/v1/sync/status")
async def get_sync_status() -> Dict[str, Any]:
    """Get cloud sync engine status."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    return {
        "component": "cloud-sync-engine",
        "status": orchestrator.sync_engine.get_status(),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/sync/history")
async def get_sync_history(limit: int = 10) -> Dict[str, Any]:
    """Get cloud sync history."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    return {
        "component": "cloud-sync-engine",
        "limit": limit,
        "history": orchestrator.sync_engine.get_sync_history(limit),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/database/status")
async def get_database_status() -> Dict[str, Any]:
    """Get database sync manager status."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    return {
        "component": "database-sync-manager",
        "status": orchestrator.db_sync_manager.get_status(),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/database/history")
async def get_database_history(limit: int = 10) -> Dict[str, Any]:
    """Get database sync history."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    return {
        "component": "database-sync-manager",
        "limit": limit,
        "history": orchestrator.db_sync_manager.get_sync_history(limit),
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# CLOUD PROVIDER ENDPOINTS
# ============================================================================

@app.get("/api/v1/providers")
async def list_providers() -> Dict[str, Any]:
    """List all registered cloud providers."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    providers = []
    for name, provider in orchestrator.sync_engine.providers.items():
        providers.append({
            "name": name,
            "type": provider.config.provider,
            "status": provider.sync_status,
            "endpoint": provider.config.api_endpoint,
            "last_sync": provider.last_sync.isoformat() if provider.last_sync else None
        })

    return {
        "component": "cloud-providers",
        "count": len(providers),
        "providers": providers,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/providers/{provider_name}")
async def get_provider_status(provider_name: str) -> Dict[str, Any]:
    """Get status of specific provider."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    provider = orchestrator.sync_engine.providers.get(provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    return {
        "name": provider_name,
        "type": provider.config.provider,
        "status": provider.sync_status,
        "endpoint": provider.config.api_endpoint,
        "enabled": provider.config.enabled,
        "last_sync": provider.last_sync.isoformat() if provider.last_sync else None,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# DATABASE ENDPOINTS
# ============================================================================

@app.get("/api/v1/databases")
async def list_databases() -> Dict[str, Any]:
    """List all registered databases."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    databases = []
    for name, connector in orchestrator.db_sync_manager.connectors.items():
        databases.append({
            "name": name,
            "type": connector.config.db_type.value,
            "connected": connector.connected,
            "endpoint": connector.config.connection_string.split('@')[1] if '@' in connector.config.connection_string else "***",
            "last_sync": connector.last_sync.isoformat() if connector.last_sync else None
        })

    return {
        "component": "databases",
        "count": len(databases),
        "databases": databases,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/sync-pairs")
async def list_sync_pairs() -> Dict[str, Any]:
    """List all database sync pairs."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    pairs = []
    for i, (source, target, direction) in enumerate(orchestrator.db_sync_manager.sync_pairs, 1):
        pairs.append({
            "id": i,
            "source": source,
            "target": target,
            "direction": direction.value
        })

    return {
        "component": "sync-pairs",
        "count": len(pairs),
        "pairs": pairs,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# ERROR HANDLING
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
