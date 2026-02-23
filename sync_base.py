"""Base classes for sync systems - eliminates code duplication."""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Generic, TypeVar
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

ConfigType = TypeVar('ConfigType')


class BaseConnector(ABC, Generic[ConfigType]):
    """Base connector class for all sync connectors."""

    def __init__(self, config: ConfigType):
        self.config = config
        self.connected = False
        self.last_sync: Optional[datetime] = None

    async def connect(self) -> bool:
        """Connect to the service."""
        logger.info(f"[{self._get_name()}] Connecting to {self._get_type()}...")
        await asyncio.sleep(0.1)
        self.connected = True
        logger.info(f"[{self._get_name()}] Connected successfully")
        return True

    async def disconnect(self) -> bool:
        """Disconnect from the service."""
        self.connected = False
        logger.info(f"[{self._get_name()}] Disconnected")
        return True

    @abstractmethod
    def _get_name(self) -> str:
        """Get connector name from config."""
        pass

    @abstractmethod
    def _get_type(self) -> str:
        """Get connector type description."""
        pass


class BaseSyncManager(ABC, Generic[ConfigType]):
    """Base sync manager for all sync systems."""

    def __init__(self):
        self.connectors: Dict[str, BaseConnector] = {}
        self.sync_history: List[Dict[str, Any]] = []
        self.is_running = False

    @abstractmethod
    def _get_manager_name(self) -> str:
        """Get the manager name for logging."""
        pass

    @abstractmethod
    async def _sync_iteration(self, iteration: int) -> List[Dict[str, Any]]:
        """Execute one sync iteration. Returns list of sync results."""
        pass

    @abstractmethod
    def _get_connector_class(self, config: ConfigType) -> type:
        """Get the appropriate connector class for a config."""
        pass

    def register_connector(self, config: ConfigType) -> None:
        """Register a connector with the manager."""
        connector_class = self._get_connector_class(config)
        name = self._get_config_name(config)
        self.connectors[name] = connector_class(config)
        logger.info(f"Registered connector: {name}")

    @abstractmethod
    def _get_config_name(self, config: ConfigType) -> str:
        """Get the name from a config object."""
        pass

    async def run_continuous_sync(self, check_interval: int = 30) -> None:
        """Run continuous sync loop."""
        self.is_running = True
        logger.info("\n" + "="*80)
        logger.info(f"{self._get_manager_name().upper()} STARTED")
        logger.info("="*80 + "\n")

        # Connect all connectors
        for connector in self.connectors.values():
            await connector.connect()

        try:
            iteration = 0
            while self.is_running:
                iteration += 1
                logger.info(f"[Cycle {iteration}] Starting sync iteration...")

                # Execute sync iteration
                results = await self._sync_iteration(iteration)

                # Log results
                for result in results:
                    self.sync_history.append(result)
                    self._log_result(result)

                await asyncio.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info(f"{self._get_manager_name()} sync stopped.")
        finally:
            self.is_running = False
            # Disconnect all connectors
            for connector in self.connectors.values():
                await connector.disconnect()
            logger.info(f"{self._get_manager_name().upper()} STOPPED")

    def _log_result(self, result: Dict[str, Any]) -> None:
        """Log a sync result."""
        # Default logging - can be overridden
        logger.info(f"✓ Sync completed: {result}")

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the sync manager."""
        return {
            "running": self.is_running,
            "connectors": list(self.connectors.keys()),
            "total_syncs": len(self.sync_history)
        }

    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sync history."""
        return self.sync_history[-limit:]
