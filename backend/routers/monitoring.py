"""Monitoring API router for exposing application metrics and health data."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

from ..monitoring import app_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get application metrics including request counts, error rates, and response times."""
    return app_metrics.get_metrics()


@router.get("/health")
async def get_health() -> Dict[str, Any]:
    """Get application health status based on current metrics."""
    return app_metrics.get_health()


@router.get("/errors")
async def get_recent_errors() -> List[Dict[str, Any]]:
    """Get recent error entries for debugging and monitoring."""
    return app_metrics.get_recent_errors()
