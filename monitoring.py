"""Comprehensive Monitoring and Observability Layer."""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthMetric:
    """Health metric for a component."""
    component: str
    status: HealthStatus
    last_check: datetime
    response_time_ms: float
    success_rate: float
    error_count: int = 0
    warning_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "last_check": self.last_check.isoformat(),
            "response_time_ms": self.response_time_ms,
            "success_rate": self.success_rate,
            "error_count": self.error_count,
            "warning_count": self.warning_count
        }


class MonitoringSystem:
    """Centralized monitoring and observability."""

    def __init__(self):
        self.health_metrics: Dict[str, HealthMetric] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.is_running = False
        self.start_time: Optional[datetime] = None

    def record_health(self, component: str, metric: HealthMetric) -> None:
        """Record health metric."""
        self.health_metrics[component] = metric
        
        if metric.status == HealthStatus.UNHEALTHY:
            self.record_alert(component, f"Component unhealthy: {metric.error_count} errors")
        elif metric.status == HealthStatus.DEGRADED:
            self.record_alert(component, f"Component degraded: {metric.success_rate*100:.1f}% success")

    def record_alert(self, component: str, message: str) -> None:
        """Record an alert."""
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "component": component,
            "message": message,
            "severity": "warning" if "degraded" in message.lower() else "critical"
        }
        self.alerts.append(alert)
        logger.warning(f"[ALERT] {component}: {message}")

    def record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Record an event."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data
        }
        self.events.append(event)
        logger.info(f"[EVENT] {event_type}: {data}")

    def get_overall_health(self) -> HealthStatus:
        """Get overall system health."""
        if not self.health_metrics:
            return HealthStatus.HEALTHY
        
        statuses = [m.status for m in self.health_metrics.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        total_components = len(self.health_metrics)
        healthy = sum(1 for m in self.health_metrics.values() if m.status == HealthStatus.HEALTHY)
        degraded = sum(1 for m in self.health_metrics.values() if m.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for m in self.health_metrics.values() if m.status == HealthStatus.UNHEALTHY)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": self.get_overall_health().value,
            "total_components": total_components,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "alerts_count": len(self.alerts),
            "events_count": len(self.events),
            "avg_response_time_ms": (
                sum(m.response_time_ms for m in self.health_metrics.values()) / total_components
                if total_components > 0 else 0
            ),
            "avg_success_rate": (
                sum(m.success_rate for m in self.health_metrics.values()) / total_components
                if total_components > 0 else 0
            )
        }

    def get_detailed_report(self, limit: int = 20) -> Dict[str, Any]:
        """Get detailed monitoring report."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": self.get_metrics_summary(),
            "component_health": [
                metric.to_dict()
                for metric in sorted(
                    self.health_metrics.values(),
                    key=lambda m: (m.status.value, -m.success_rate)
                )[:limit]
            ],
            "recent_alerts": self.alerts[-10:],
            "recent_events": self.events[-10:]
        }

    async def run_monitoring(self, check_interval: int = 10) -> None:
        """Run continuous monitoring."""
        self.is_running = True
        self.start_time = datetime.utcnow()
        logger.info("\n" + "="*80)
        logger.info("MONITORING SYSTEM STARTED")
        logger.info("="*80 + "\n")

        try:
            while self.is_running:
                # Generate periodic health report
                logger.info("\n" + "-"*80)
                logger.info("HEALTH CHECK REPORT")
                logger.info("-"*80)
                
                summary = self.get_metrics_summary()
                logger.info(f"Overall Status: {summary['overall_status'].upper()}")
                logger.info(f"Components: {summary['healthy']} healthy, "
                           f"{summary['degraded']} degraded, "
                           f"{summary['unhealthy']} unhealthy")
                logger.info(f"Avg Response Time: {summary['avg_response_time_ms']:.1f}ms")
                logger.info(f"Avg Success Rate: {summary['avg_success_rate']*100:.1f}%")
                
                if summary['alerts_count'] > 0:
                    logger.warning(f"⚠️  Active Alerts: {summary['alerts_count']}")
                
                logger.info("-"*80)
                
                await asyncio.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped.")
        finally:
            self.is_running = False
            logger.info("Monitoring System Stopped")
