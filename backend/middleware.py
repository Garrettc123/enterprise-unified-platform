from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from .logging_config import set_correlation_id, get_correlation_id
from .monitoring import app_metrics

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all API requests with correlation ID tracking and metrics."""
    
    async def dispatch(self, request: Request, call_next):
        # Set correlation ID from header or generate new one
        incoming_id = request.headers.get("X-Correlation-ID")
        correlation_id = set_correlation_id(incoming_id)

        # Track active requests
        app_metrics.increment_active()

        # Log request
        start_time = time.time()
        logger.info(f"👉 {request.method} {request.url.path}")
        
        try:
            # Process request
            response = await call_next(request)
        except Exception:
            app_metrics.decrement_active()
            raise
        
        # Calculate duration
        process_time = time.time() - start_time
        duration_ms = process_time * 1000

        # Decrement active requests
        app_metrics.decrement_active()

        # Record metrics
        app_metrics.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Log response
        logger.info(
            f"👈 {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s"
        )
        
        # Add custom headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-API-Version"] = "1.0.0"
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/"]:
            return await call_next(request)
        
        # Clean old requests
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if req_time > cutoff
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"⚠️ Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": 60
                }
            )
        
        # Add current request
        self.requests[client_ip].append(now)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(self.requests[client_ip])
        )
        
        return response