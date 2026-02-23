"""Cache Layer Sync - Redis, Memcached synchronization."""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from sync_base import BaseConnector, BaseSyncManager

logger = logging.getLogger(__name__)


class CacheType(Enum):
    """Supported cache types."""
    REDIS = "redis"
    MEMCACHED = "memcached"
    DYNAMODB = "dynamodb"


@dataclass
class CacheConfig:
    """Cache configuration."""
    name: str
    cache_type: CacheType
    host: str
    port: int
    sync_enabled: bool = True


class CacheConnector(BaseConnector[CacheConfig]):
    """Base cache connector."""

    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self.keys_synced = 0

    def _get_name(self) -> str:
        return self.config.name

    def _get_type(self) -> str:
        return self.config.cache_type.value

    async def sync_cache(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync cache entries."""
        if not self.connected:
            raise Exception("Not connected")

        logger.info(f"[{self.config.name}] Syncing {len(data)} cache entries...")
        await asyncio.sleep(0.05)

        self.last_sync = datetime.utcnow()
        self.keys_synced += len(data)

        return {
            "cache": self.config.name,
            "keys_synced": len(data),
            "total_keys": self.keys_synced,
            "timestamp": self.last_sync.isoformat()
        }


class RedisConnector(CacheConnector):
    """Redis cache connector."""
    pass


class MemcachedConnector(CacheConnector):
    """Memcached connector."""
    pass


class CacheSyncManager(BaseSyncManager[CacheConfig]):
    """Manages cache synchronization."""

    def __init__(self):
        super().__init__()
        self._connector_map = {
            CacheType.REDIS: RedisConnector,
            CacheType.MEMCACHED: MemcachedConnector,
        }

    def _get_manager_name(self) -> str:
        return "Cache Sync Manager"

    def _get_connector_class(self, config: CacheConfig) -> type:
        return self._connector_map[config.cache_type]

    def _get_config_name(self, config: CacheConfig) -> str:
        return config.name

    async def _sync_iteration(self, iteration: int) -> List[Dict[str, Any]]:
        """Execute one cache sync iteration."""
        logger.info(f"[Cycle {iteration}] Syncing cache entries...")

        sample_data = {f"key_{i}": f"value_{i}" for i in range(10)}

        tasks = [
            connector.sync_cache(sample_data)
            for connector in self.connectors.values()
        ]
        return await asyncio.gather(*tasks)

    def _log_result(self, result: Dict[str, Any]) -> None:
        """Log cache sync result."""
        logger.info(f"✓ {result['cache']}: {result['keys_synced']} keys synced")

    def register_cache(self, config: CacheConfig) -> None:
        """Register cache (legacy method for backwards compatibility)."""
        self.register_connector(config)
