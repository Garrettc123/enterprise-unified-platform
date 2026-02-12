"""Application monitoring and metrics collection for the Enterprise Unified Platform."""

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ApplicationMetrics:
    """Thread-safe application metrics collector.

    Tracks request counts, error rates, response times, and per-endpoint statistics.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self.start_time: datetime = datetime.now(timezone.utc)
        self.total_requests: int = 0
        self.total_errors: int = 0
        self.active_requests: int = 0
        self.status_code_counts: Dict[int, int] = defaultdict(int)
        self.endpoint_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "errors": 0,
                "total_duration_ms": 0.0,
                "min_duration_ms": float("inf"),
                "max_duration_ms": 0.0,
            }
        )
        self.recent_errors: List[Dict[str, Any]] = []
        self._max_recent_errors: int = 50

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record metrics for a completed request.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: Request path.
            status_code: HTTP response status code.
            duration_ms: Request processing duration in milliseconds.
        """
        endpoint_key = f"{method} {path}"
        is_error = status_code >= 400

        with self._lock:
            self.total_requests += 1
            self.status_code_counts[status_code] += 1

            if is_error:
                self.total_errors += 1
                self.recent_errors.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                })
                if len(self.recent_errors) > self._max_recent_errors:
                    self.recent_errors = self.recent_errors[-self._max_recent_errors:]

            stats = self.endpoint_stats[endpoint_key]
            stats["count"] += 1
            if is_error:
                stats["errors"] += 1
            stats["total_duration_ms"] += duration_ms
            if duration_ms < stats["min_duration_ms"]:
                stats["min_duration_ms"] = duration_ms
            if duration_ms > stats["max_duration_ms"]:
                stats["max_duration_ms"] = duration_ms

    def increment_active(self) -> None:
        """Increment active request count."""
        with self._lock:
            self.active_requests += 1

    def decrement_active(self) -> None:
        """Decrement active request count."""
        with self._lock:
            self.active_requests = max(0, self.active_requests - 1)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot.

        Returns:
            Dictionary containing all collected metrics.
        """
        with self._lock:
            uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            error_rate = (
                (self.total_errors / self.total_requests * 100)
                if self.total_requests > 0
                else 0.0
            )

            endpoint_data = {}
            for key, stats in self.endpoint_stats.items():
                avg_duration = (
                    stats["total_duration_ms"] / stats["count"]
                    if stats["count"] > 0
                    else 0.0
                )
                endpoint_data[key] = {
                    "count": stats["count"],
                    "errors": stats["errors"],
                    "avg_duration_ms": round(avg_duration, 2),
                    "min_duration_ms": round(stats["min_duration_ms"], 2)
                    if stats["min_duration_ms"] != float("inf")
                    else 0.0,
                    "max_duration_ms": round(stats["max_duration_ms"], 2),
                }

            return {
                "uptime_seconds": round(uptime_seconds, 1),
                "start_time": self.start_time.isoformat(),
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "error_rate_percent": round(error_rate, 2),
                "active_requests": self.active_requests,
                "status_codes": dict(self.status_code_counts),
                "endpoints": endpoint_data,
            }

    def get_health(self) -> Dict[str, Any]:
        """Get application health status.

        Returns:
            Dictionary with health status and key indicators.
        """
        with self._lock:
            error_rate = (
                (self.total_errors / self.total_requests * 100)
                if self.total_requests > 0
                else 0.0
            )

            if error_rate > 50:
                status = "unhealthy"
            elif error_rate > 10:
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "uptime_seconds": round(
                    (datetime.now(timezone.utc) - self.start_time).total_seconds(), 1
                ),
                "total_requests": self.total_requests,
                "error_rate_percent": round(error_rate, 2),
                "active_requests": self.active_requests,
            }

    def get_recent_errors(self) -> List[Dict[str, Any]]:
        """Get recent error entries.

        Returns:
            List of recent error dictionaries.
        """
        with self._lock:
            return list(self.recent_errors)

    def reset(self) -> None:
        """Reset all metrics. Primarily used for testing."""
        with self._lock:
            self.start_time = datetime.now(timezone.utc)
            self.total_requests = 0
            self.total_errors = 0
            self.active_requests = 0
            self.status_code_counts.clear()
            self.endpoint_stats.clear()
            self.recent_errors.clear()


# Global application metrics instance
app_metrics = ApplicationMetrics()
