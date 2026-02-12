"""Structured logging configuration for the Enterprise Unified Platform."""

import logging
import json
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

# Context variable for correlation ID (request tracing)
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set a correlation ID in the current context.

    Args:
        correlation_id: Optional ID to set. If None, generates a new UUID.

    Returns:
        The correlation ID that was set.
    """
    cid = correlation_id or str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        cid = get_correlation_id()
        if cid:
            log_entry["correlation_id"] = cid

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key in ("status_code", "method", "path", "duration_ms", "client_ip"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry)


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure application logging.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, use JSON structured logging format.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Clear existing handlers on root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler()

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
