"""Database Sync Layer - Real-time data synchronization across services."""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Direction of data synchronization."""
    BIDIRECTIONAL = "bidirectional"
    SOURCE_TO_TARGET = "source_to_target"
    TARGET_TO_SOURCE = "target_to_source"


class DatabaseType(Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    DYNAMODB = "dynamodb"
    FIRESTORE = "firestore"
    ELASTICSEARCH = "elasticsearch"


@dataclass
class DatabaseConfig:
    """Configuration for database connection."""
    name: str
    db_type: DatabaseType
    connection_string: str
    sync_enabled: bool = True
    batch_size: int = 100
    check_interval: int = 30  # seconds


@dataclass
class SyncRecord:
    """Record of a database sync operation."""
    source: str
    target: str
    timestamp: str
    records_synced: int
    duration_ms: float
    status: str
    error: Optional[str] = None


class DatabaseConnector:
    """Abstract database connector."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connected = False
        self.last_sync: Optional[datetime] = None

    async def connect(self) -> bool:
        """Connect to database."""
        logger.info(f"[{self.config.name}] Connecting to {self.config.db_type.value}...")
        await asyncio.sleep(0.2)  # Simulate connection
        self.connected = True
        logger.info(f"[{self.config.name}] Connected successfully")
        return True

    async def disconnect(self) -> bool:
        """Disconnect from database."""
        self.connected = False
        logger.info(f"[{self.config.name}] Disconnected")
        return True

    async def fetch_changes(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch changes from database."""
        if not self.connected:
            raise Exception("Not connected to database")
        logger.info(f"[{self.config.name}] Fetching changes...")
        await asyncio.sleep(0.1)
        return []

    async def apply_changes(self, changes: List[Dict[str, Any]]) -> int:
        """Apply changes to database."""
        if not self.connected:
            raise Exception("Not connected to database")
        logger.info(f"[{self.config.name}] Applying {len(changes)} changes...")
        await asyncio.sleep(0.1 * len(changes) / self.config.batch_size)
        return len(changes)


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL database connector."""
    pass


class MongoDBConnector(DatabaseConnector):
    """MongoDB database connector."""
    pass


class DynamoDBConnector(DatabaseConnector):
    """AWS DynamoDB connector."""
    pass


class FirestoreConnector(DatabaseConnector):
    """Google Firestore connector."""
    pass


class ElasticsearchConnector(DatabaseConnector):
    """Elasticsearch connector."""
    pass


class DatabaseSyncManager:
    """Manages synchronization between multiple databases."""

    def __init__(self):
        self.connectors: Dict[str, DatabaseConnector] = {}
        self.sync_pairs: List[tuple] = []  # [(source, target, direction)]
        self.sync_history: List[SyncRecord] = []
        self.is_running = False

    def register_database(self, config: DatabaseConfig) -> None:
        """Register a database."""
        connector_map = {
            DatabaseType.POSTGRESQL: PostgreSQLConnector,
            DatabaseType.MONGODB: MongoDBConnector,
            DatabaseType.DYNAMODB: DynamoDBConnector,
            DatabaseType.FIRESTORE: FirestoreConnector,
            DatabaseType.ELASTICSEARCH: ElasticsearchConnector,
        }

        connector_class = connector_map[config.db_type]
        self.connectors[config.name] = connector_class(config)
        logger.info(f"Registered database: {config.name} ({config.db_type.value})")

    def add_sync_pair(
        self,
        source: str,
        target: str,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    ) -> None:
        """Add a sync pair between two databases."""
        if source not in self.connectors or target not in self.connectors:
            raise ValueError("Source or target database not registered")

        self.sync_pairs.append((source, target, direction))
        logger.info(
            f"Sync pair added: {source} <-> {target} ({direction.value})"
        )

    async def _sync_pair(self, source: str, target: str, direction: SyncDirection) -> SyncRecord:
        """Synchronize a pair of databases."""
        start_time = datetime.utcnow()
        source_connector = self.connectors[source]
        target_connector = self.connectors[target]

        try:
            if direction in [SyncDirection.SOURCE_TO_TARGET, SyncDirection.BIDIRECTIONAL]:
                logger.info(f"Syncing {source} -> {target}...")
                changes = await source_connector.fetch_changes()
                records_synced = await target_connector.apply_changes(changes)

            if direction in [SyncDirection.TARGET_TO_SOURCE, SyncDirection.BIDIRECTIONAL]:
                logger.info(f"Syncing {target} -> {source}...")
                changes = await target_connector.fetch_changes()
                records_synced = await source_connector.apply_changes(changes)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            record = SyncRecord(
                source=source,
                target=target,
                timestamp=start_time.isoformat(),
                records_synced=records_synced,
                duration_ms=duration_ms,
                status="success"
            )
            logger.info(
                f"✓ Sync successful: {records_synced} records in {duration_ms:.0f}ms"
            )
            return record

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            record = SyncRecord(
                source=source,
                target=target,
                timestamp=start_time.isoformat(),
                records_synced=0,
                duration_ms=duration_ms,
                status="failed",
                error=str(e)
            )
            logger.error(f"✗ Sync failed: {str(e)}")
            return record

    async def run_continuous_sync(self, check_interval: int = 30) -> None:
        """Run continuous database synchronization."""
        self.is_running = True
        logger.info("\n" + "="*80)
        logger.info("DATABASE SYNC MANAGER STARTED")
        logger.info(f"Registered Databases: {list(self.connectors.keys())}")
        logger.info(f"Sync Pairs: {len(self.sync_pairs)}")
        logger.info(f"Check Interval: {check_interval}s")
        logger.info("="*80 + "\n")

        # Connect all databases
        for connector in self.connectors.values():
            try:
                await connector.connect()
            except Exception as e:
                logger.error(f"Failed to connect: {str(e)}")

        try:
            iteration = 0
            while self.is_running:
                iteration += 1
                logger.info(f"\n[Cycle {iteration}] Starting database sync...")
                logger.info("-" * 80)

                # Execute all sync pairs concurrently
                tasks = [
                    self._sync_pair(source, target, direction)
                    for source, target, direction in self.sync_pairs
                ]
                results = await asyncio.gather(*tasks)

                # Record results
                for result in results:
                    self.sync_history.append(result)

                # Log summary
                successful = sum(1 for r in results if r.status == "success")
                logger.info(f"\nSync Summary:")
                logger.info(f"  Total Pairs: {len(results)}")
                logger.info(f"  Successful: {successful}")
                logger.info(f"  Failed: {len(results) - successful}")
                logger.info("-" * 80)

                await asyncio.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("\nDatabase sync stopped by user.")
        finally:
            # Disconnect all databases
            for connector in self.connectors.values():
                await connector.disconnect()

            self.is_running = False
            logger.info("\n" + "="*80)
            logger.info("DATABASE SYNC MANAGER STOPPED")
            logger.info("="*80)

    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sync history."""
        return [
            asdict(record)
            for record in self.sync_history[-limit:]
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get current sync manager status."""
        return {
            "running": self.is_running,
            "registered_databases": list(self.connectors.keys()),
            "sync_pairs": len(self.sync_pairs),
            "total_syncs": len(self.sync_history),
            "database_statuses": {
                name: {
                    "connected": connector.connected,
                    "last_sync": connector.last_sync.isoformat() if connector.last_sync else None
                }
                for name, connector in self.connectors.items()
            }
        }


async def main():
    """Initialize and run database sync manager."""
    manager = DatabaseSyncManager()

    # Register databases
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
    ]

    for config in configs:
        manager.register_database(config)

    # Add sync pairs
    manager.add_sync_pair(
        "prod-postgres",
        "backup-postgres",
        SyncDirection.SOURCE_TO_TARGET
    )
    manager.add_sync_pair(
        "prod-postgres",
        "analytics-mongo",
        SyncDirection.SOURCE_TO_TARGET
    )
    manager.add_sync_pair(
        "prod-postgres",
        "cache-dynamodb",
        SyncDirection.BIDIRECTIONAL
    )

    # Run continuous sync
    await manager.run_continuous_sync(check_interval=30)


if __name__ == "__main__":
    asyncio.run(main())
