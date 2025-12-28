"""Service Integration Layer - Orchestrates all sync operations."""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sync_engine import AutonomousSyncEngine, SyncConfig
from database_sync import DatabaseSyncManager, DatabaseConfig, DatabaseType, SyncDirection

logger = logging.getLogger(__name__)


class ServiceHealthStatus(Enum):
    """Health status of services."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceStatus:
    """Status of a service."""
    name: str
    health: ServiceHealthStatus
    last_check: str
    uptime_percent: float


class ServiceIntegrationOrchestrator:
    """Orchestrates all autonomous sync operations across cloud and database layers."""

    def __init__(self):
        self.sync_engine = AutonomousSyncEngine()
        self.db_sync_manager = DatabaseSyncManager()
        self.service_statuses: Dict[str, ServiceStatus] = {}
        self.is_running = False
        self.start_time: Optional[datetime] = None

    def configure_cloud_sync(self) -> None:
        """Configure cloud provider sync."""
        configs = [
            SyncConfig(
                name="aws-production",
                provider="aws",
                api_endpoint="https://api.aws.amazon.com",
                credentials_key="AWS_CREDENTIALS"
            ),
            SyncConfig(
                name="gcp-production",
                provider="gcp",
                api_endpoint="https://api.gcp.google.com",
                credentials_key="GCP_CREDENTIALS"
            ),
            SyncConfig(
                name="azure-production",
                provider="azure",
                api_endpoint="https://api.azure.microsoft.com",
                credentials_key="AZURE_CREDENTIALS"
            ),
            SyncConfig(
                name="render-deployment",
                provider="render",
                api_endpoint="https://api.render.com",
                credentials_key="RENDER_API_KEY"
            ),
            SyncConfig(
                name="vercel-deployment",
                provider="vercel",
                api_endpoint="https://api.vercel.com",
                credentials_key="VERCEL_TOKEN"
            ),
        ]

        for config in configs:
            self.sync_engine.register_provider(config)
        logger.info(f"Configured {len(configs)} cloud providers")

    def configure_database_sync(self) -> None:
        """Configure database sync."""
        configs = [
            DatabaseConfig(
                name="prod-postgres",
                db_type=DatabaseType.POSTGRESQL,
                connection_string="postgresql://user:pass@prod-db.com:5432/main"
            ),
            DatabaseConfig(
                name="backup-postgres",
                db_type=DatabaseType.POSTGRESQL,
                connection_string="postgresql://user:pass@backup-db.com:5432/main"
            ),
            DatabaseConfig(
                name="analytics-mongo",
                db_type=DatabaseType.MONGODB,
                connection_string="mongodb://user:pass@analytics.mongodb.com/data"
            ),
            DatabaseConfig(
                name="cache-dynamodb",
                db_type=DatabaseType.DYNAMODB,
                connection_string="dynamodb://aws-region/table-name"
            ),
            DatabaseConfig(
                name="search-elasticsearch",
                db_type=DatabaseType.ELASTICSEARCH,
                connection_string="elasticsearch://user:pass@search.elastic.co"
            ),
        ]

        for config in configs:
            self.db_sync_manager.register_database(config)

        # Configure sync pairs
        self.db_sync_manager.add_sync_pair(
            "prod-postgres",
            "backup-postgres",
            SyncDirection.SOURCE_TO_TARGET
        )
        self.db_sync_manager.add_sync_pair(
            "prod-postgres",
            "analytics-mongo",
            SyncDirection.SOURCE_TO_TARGET
        )
        self.db_sync_manager.add_sync_pair(
            "prod-postgres",
            "cache-dynamodb",
            SyncDirection.BIDIRECTIONAL
        )
        self.db_sync_manager.add_sync_pair(
            "prod-postgres",
            "search-elasticsearch",
            SyncDirection.SOURCE_TO_TARGET
        )
        logger.info(f"Configured {len(configs)} databases with {len(self.db_sync_manager.sync_pairs)} sync pairs")

    async def _monitor_services(self) -> None:
        """Monitor health of all services."""
        while self.is_running:
            # Check cloud sync engine
            cloud_status = self.sync_engine.get_status()
            self.service_statuses["cloud-sync"] = ServiceStatus(
                name="cloud-sync",
                health=ServiceHealthStatus.HEALTHY if cloud_status["running"] else ServiceHealthStatus.UNHEALTHY,
                last_check=datetime.utcnow().isoformat(),
                uptime_percent=100.0 if cloud_status["running"] else 0.0
            )

            # Check database sync manager
            db_status = self.db_sync_manager.get_status()
            self.service_statuses["database-sync"] = ServiceStatus(
                name="database-sync",
                health=ServiceHealthStatus.HEALTHY if db_status["running"] else ServiceHealthStatus.UNHEALTHY,
                last_check=datetime.utcnow().isoformat(),
                uptime_percent=100.0 if db_status["running"] else 0.0
            )

            await asyncio.sleep(30)  # Check every 30 seconds

    async def run_full_autonomous_sync(self) -> None:
        """Run complete autonomous sync orchestration."""
        self.is_running = True
        self.start_time = datetime.utcnow()

        logger.info("\n" + "#"*80)
        logger.info("# FULL AUTONOMOUS SYNC ORCHESTRATION STARTED")
        logger.info("#"*80)
        logger.info(f"Start Time: {self.start_time.isoformat()}")
        logger.info(f"Cloud Providers: {len(self.sync_engine.providers)}")
        logger.info(f"Databases: {len(self.db_sync_manager.connectors)}")
        logger.info(f"Sync Pairs: {len(self.db_sync_manager.sync_pairs)}")
        logger.info("#"*80 + "\n")

        try:
            # Create tasks for cloud sync, database sync, and monitoring
            tasks = [
                self.sync_engine.run_continuous_sync(check_interval=60),
                self.db_sync_manager.run_continuous_sync(check_interval=30),
                self._monitor_services()
            ]

            # Run all tasks concurrently
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            logger.info("\nOrchestrator stopped by user.")
        except Exception as e:
            logger.error(f"Orchestrator error: {str(e)}")
        finally:
            self.is_running = False
            logger.info("\n" + "#"*80)
            logger.info("# FULL AUTONOMOUS SYNC ORCHESTRATION STOPPED")
            logger.info("#"*80)

    def get_full_status(self) -> Dict[str, Any]:
        """Get complete status of all sync operations."""
        return {
            "orchestrator": {
                "running": self.is_running,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "uptime_seconds": (
                    (datetime.utcnow() - self.start_time).total_seconds()
                    if self.start_time else 0
                )
            },
            "cloud_sync": self.sync_engine.get_status(),
            "database_sync": self.db_sync_manager.get_status(),
            "service_statuses": {
                name: {
                    "health": status.health.value,
                    "last_check": status.last_check,
                    "uptime_percent": status.uptime_percent
                }
                for name, status in self.service_statuses.items()
            }
        }


async def main():
    """Initialize and run full orchestration."""
    orchestrator = ServiceIntegrationOrchestrator()

    # Configure all components
    orchestrator.configure_cloud_sync()
    orchestrator.configure_database_sync()

    # Run full autonomous sync
    await orchestrator.run_full_autonomous_sync()


if __name__ == "__main__":
    asyncio.run(main())
