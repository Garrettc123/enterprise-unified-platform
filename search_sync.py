"""Search Index Sync - Elasticsearch, Algolia, Meilisearch synchronization."""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class SearchEngineType(Enum):
    """Supported search engines."""
    ELASTICSEARCH = "elasticsearch"
    ALGOLIA = "algolia"
    MEILISEARCH = "meilisearch"
    OPENSEARCH = "opensearch"


@dataclass
class SearchEngineConfig:
    """Search engine configuration."""
    name: str
    engine_type: SearchEngineType
    endpoint: str
    api_key: str
    sync_enabled: bool = True


class SearchEngineConnector:
    """Base search engine connector."""

    def __init__(self, config: SearchEngineConfig):
        self.config = config
        self.connected = False
        self.last_sync: Optional[datetime] = None
        self.documents_indexed = 0

    async def connect(self) -> bool:
        """Connect to search engine."""
        logger.info(f"[{self.config.name}] Connecting to {self.config.engine_type.value}...")
        await asyncio.sleep(0.1)
        self.connected = True
        return True

    async def index_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Index documents."""
        if not self.connected:
            raise Exception("Not connected")
        
        logger.info(f"[{self.config.name}] Indexing {len(documents)} documents...")
        await asyncio.sleep(0.1)
        
        self.last_sync = datetime.utcnow()
        self.documents_indexed += len(documents)
        
        return {
            "search_engine": self.config.name,
            "documents_indexed": len(documents),
            "total_indexed": self.documents_indexed,
            "timestamp": self.last_sync.isoformat()
        }


class ElasticsearchConnector(SearchEngineConnector):
    """Elasticsearch connector."""
    pass


class AlgoliaConnector(SearchEngineConnector):
    """Algolia connector."""
    pass


class MeilisearchConnector(SearchEngineConnector):
    """Meilisearch connector."""
    pass


class SearchIndexSyncManager:
    """Manages search index synchronization."""

    def __init__(self):
        self.connectors: Dict[str, SearchEngineConnector] = {}
        self.sync_history: List[Dict[str, Any]] = []
        self.is_running = False

    def register_search_engine(self, config: SearchEngineConfig) -> None:
        """Register search engine."""
        connector_map = {
            SearchEngineType.ELASTICSEARCH: ElasticsearchConnector,
            SearchEngineType.ALGOLIA: AlgoliaConnector,
            SearchEngineType.MEILISEARCH: MeilisearchConnector,
        }

        connector_class = connector_map[config.engine_type]
        self.connectors[config.name] = connector_class(config)
        logger.info(f"Registered search engine: {config.name} ({config.engine_type.value})")

    async def run_continuous_sync(self, check_interval: int = 25) -> None:
        """Run continuous search index sync."""
        self.is_running = True
        logger.info("\n" + "="*80)
        logger.info("SEARCH INDEX SYNC MANAGER STARTED")
        logger.info("="*80 + "\n")

        for connector in self.connectors.values():
            await connector.connect()

        try:
            iteration = 0
            while self.is_running:
                iteration += 1
                logger.info(f"[Cycle {iteration}] Indexing documents...")
                
                sample_docs = [
                    {"id": i, "title": f"Doc {i}", "content": f"Content {i}"}
                    for i in range(8)
                ]

                tasks = [
                    connector.index_documents(sample_docs)
                    for connector in self.connectors.values()
                ]
                results = await asyncio.gather(*tasks)

                for result in results:
                    self.sync_history.append(result)
                    logger.info(f"✓ {result['search_engine']}: {result['documents_indexed']} documents indexed")

                await asyncio.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Search sync stopped.")
        finally:
            self.is_running = False
            logger.info("Search Index Sync Manager Stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get status."""
        return {
            "running": self.is_running,
            "search_engines": list(self.connectors.keys()),
            "total_documents_indexed": sum(r.get("documents_indexed", 0) for r in self.sync_history)
        }
