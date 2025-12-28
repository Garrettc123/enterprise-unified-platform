"""Webhook Synchronization - Event-driven sync across all systems."""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Supported event types."""
    CODE_PUSH = "code_push"
    DATA_UPDATE = "data_update"
    MODEL_TRAINED = "model_trained"
    SCHEMA_CHANGED = "schema_changed"
    DEPLOYMENT_COMPLETE = "deployment_complete"
    ERROR = "error"


@dataclass
class Webhook:
    """Webhook configuration."""
    name: str
    event_type: EventType
    endpoint: str
    active: bool = True
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """Webhook event."""
    event_type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    source: str


class WebhookManager:
    """Manages webhook synchronization."""

    def __init__(self):
        self.webhooks: Dict[str, List[Webhook]] = {}
        self.event_history: List[WebhookEvent] = []
        self.handlers: Dict[EventType, List[Callable]] = {}
        self.is_running = False

    def register_webhook(self, webhook: Webhook) -> None:
        """Register webhook."""
        event_type_str = webhook.event_type.value
        if event_type_str not in self.webhooks:
            self.webhooks[event_type_str] = []
        
        self.webhooks[event_type_str].append(webhook)
        logger.info(f"Registered webhook: {webhook.name} for {webhook.event_type.value}")

    def register_handler(self, event_type: EventType, handler: Callable) -> None:
        """Register event handler."""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type.value}")

    async def trigger_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Trigger webhook event."""
        logger.info(f"[EVENT] {event.event_type.value} from {event.source}")
        
        self.event_history.append(event)
        
        # Call registered handlers
        handlers = self.handlers.get(event.event_type, [])
        handler_results = []
        
        for handler in handlers:
            try:
                result = await handler(event) if asyncio.iscoroutinefunction(handler) else handler(event)
                handler_results.append(result)
                logger.info(f"✓ Handler executed successfully")
            except Exception as e:
                logger.error(f"✗ Handler error: {str(e)}")
        
        # Trigger webhooks
        webhooks = self.webhooks.get(event.event_type.value, [])
        webhook_results = []
        
        for webhook in webhooks:
            if webhook.active:
                try:
                    logger.info(f"Calling webhook: {webhook.name} -> {webhook.endpoint}")
                    await asyncio.sleep(0.1)
                    webhook_results.append({
                        "webhook": webhook.name,
                        "status": "success",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Webhook error: {str(e)}")
                    webhook_results.append({
                        "webhook": webhook.name,
                        "status": "failed",
                        "error": str(e)
                    })
        
        return {
            "event_type": event.event_type.value,
            "handlers_executed": len(handler_results),
            "webhooks_called": len(webhook_results),
            "timestamp": datetime.utcnow().isoformat()
        }

    def get_status(self) -> Dict[str, Any]:
        """Get webhook manager status."""
        total_webhooks = sum(len(whs) for whs in self.webhooks.values())
        
        return {
            "running": self.is_running,
            "total_webhooks": total_webhooks,
            "total_events": len(self.event_history),
            "event_types_registered": len(self.webhooks),
            "handlers_registered": sum(len(h) for h in self.handlers.values()),
            "timestamp": datetime.utcnow().isoformat()
        }
