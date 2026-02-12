"""Elasticsearch service for full-text search functionality.

Provides connection management, index creation, document indexing,
and full-text search with relevance scoring. Falls back gracefully
when Elasticsearch is unavailable.
"""

import logging
from typing import Any, Dict, List, Optional

from elasticsearch import AsyncElasticsearch, NotFoundError

logger = logging.getLogger(__name__)

# Index mappings for each entity type
INDEX_MAPPINGS = {
    "projects": {
        "mappings": {
            "properties": {
                "name": {"type": "text", "analyzer": "standard", "fields": {"keyword": {"type": "keyword"}}},
                "description": {"type": "text", "analyzer": "standard"},
                "status": {"type": "keyword"},
                "priority": {"type": "keyword"},
                "organization_id": {"type": "integer"},
                "created_by": {"type": "integer"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
    },
    "tasks": {
        "mappings": {
            "properties": {
                "title": {"type": "text", "analyzer": "standard", "fields": {"keyword": {"type": "keyword"}}},
                "description": {"type": "text", "analyzer": "standard"},
                "status": {"type": "keyword"},
                "priority": {"type": "keyword"},
                "project_id": {"type": "integer"},
                "organization_id": {"type": "integer"},
                "assigned_to": {"type": "integer"},
                "created_by": {"type": "integer"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
    },
    "users": {
        "mappings": {
            "properties": {
                "username": {"type": "text", "analyzer": "standard", "fields": {"keyword": {"type": "keyword"}}},
                "email": {"type": "keyword"},
                "full_name": {"type": "text", "analyzer": "standard", "fields": {"keyword": {"type": "keyword"}}},
                "is_active": {"type": "boolean"},
                "created_at": {"type": "date"},
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
    },
}


class ElasticsearchService:
    """Service for managing Elasticsearch operations."""

    def __init__(self, elasticsearch_url: str, index_prefix: str = "enterprise"):
        self.elasticsearch_url = elasticsearch_url
        self.index_prefix = index_prefix
        self.client: Optional[AsyncElasticsearch] = None
        self._available = False

    def _index_name(self, entity_type: str) -> str:
        """Get the full index name for an entity type."""
        return f"{self.index_prefix}_{entity_type}"

    async def connect(self) -> bool:
        """Connect to Elasticsearch and verify connectivity."""
        try:
            self.client = AsyncElasticsearch(
                self.elasticsearch_url,
                request_timeout=10,
                retry_on_timeout=True,
                max_retries=2,
            )
            info = await self.client.info()
            self._available = True
            logger.info(
                "Connected to Elasticsearch cluster: %s",
                info.get("cluster_name", "unknown"),
            )
            return True
        except Exception:
            logger.warning(
                "Elasticsearch unavailable at %s. Search will use database fallback.",
                self.elasticsearch_url,
            )
            self._available = False
            return False

    async def close(self) -> None:
        """Close Elasticsearch client connection."""
        if self.client:
            await self.client.close()
            self.client = None
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if Elasticsearch is available."""
        return self._available and self.client is not None

    async def create_indices(self) -> None:
        """Create all required indices if they don't exist."""
        if not self.is_available:
            return

        for entity_type, mapping in INDEX_MAPPINGS.items():
            index_name = self._index_name(entity_type)
            try:
                exists = await self.client.indices.exists(index=index_name)
                if not exists:
                    await self.client.indices.create(index=index_name, body=mapping)
                    logger.info("Created index: %s", index_name)
            except Exception:
                logger.exception("Failed to create index %s", index_name)

    async def index_document(
        self, entity_type: str, doc_id: int, document: Dict[str, Any]
    ) -> bool:
        """Index a single document."""
        if not self.is_available:
            return False

        index_name = self._index_name(entity_type)
        try:
            await self.client.index(index=index_name, id=str(doc_id), document=document)
            return True
        except Exception:
            logger.exception("Failed to index document %s/%s", index_name, doc_id)
            return False

    async def bulk_index(
        self, entity_type: str, documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Bulk index multiple documents."""
        if not self.is_available:
            return {"indexed": 0, "errors": 0}

        index_name = self._index_name(entity_type)
        operations = []
        for doc in documents:
            doc_id = doc.pop("id", None)
            operations.append({"index": {"_index": index_name, "_id": str(doc_id)}})
            operations.append(doc)

        if not operations:
            return {"indexed": 0, "errors": 0}

        try:
            result = await self.client.bulk(operations=operations)
            errors = sum(1 for item in result["items"] if item["index"].get("error"))
            return {
                "indexed": len(documents) - errors,
                "errors": errors,
            }
        except Exception:
            logger.exception("Bulk indexing failed for %s", index_name)
            return {"indexed": 0, "errors": len(documents)}

    async def delete_document(self, entity_type: str, doc_id: int) -> bool:
        """Delete a document from the index."""
        if not self.is_available:
            return False

        index_name = self._index_name(entity_type)
        try:
            await self.client.delete(index=index_name, id=str(doc_id))
            return True
        except NotFoundError:
            return False
        except Exception:
            logger.exception("Failed to delete document %s/%s", index_name, doc_id)
            return False

    async def search(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        organization_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Perform full-text search across indices.

        Args:
            query: Search query string.
            entity_types: List of entity types to search (projects, tasks, users).
            organization_id: Filter by organization ID.
            skip: Number of results to skip.
            limit: Maximum number of results to return.

        Returns:
            Dict with results list and total count.
        """
        if not self.is_available:
            return {"results": [], "total": 0}

        if entity_types is None:
            entity_types = ["projects", "tasks", "users"]

        indices = [self._index_name(et) for et in entity_types]
        index_str = ",".join(indices)

        # Build multi-match query
        must_query = {
            "multi_match": {
                "query": query,
                "fields": [
                    "name^3",
                    "title^3",
                    "username^2",
                    "full_name^2",
                    "description",
                    "email",
                ],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }

        # Build filter for organization_id
        filter_clauses = []
        if organization_id is not None:
            filter_clauses.append(
                {"term": {"organization_id": organization_id}}
            )

        body = {
            "query": {
                "bool": {
                    "must": [must_query],
                    "filter": filter_clauses,
                }
            },
            "from": skip,
            "size": limit,
            "highlight": {
                "fields": {
                    "name": {},
                    "title": {},
                    "description": {"fragment_size": 150},
                    "username": {},
                    "full_name": {},
                }
            },
        }

        try:
            response = await self.client.search(
                index=index_str,
                body=body,
                ignore_unavailable=True,
            )

            results = []
            for hit in response["hits"]["hits"]:
                index_name = hit["_index"]
                # Determine entity type from index name
                entity_type = index_name.replace(f"{self.index_prefix}_", "")
                # Map plural to singular for type field
                type_map = {"projects": "project", "tasks": "task", "users": "user"}
                result_type = type_map.get(entity_type, entity_type)

                source = hit["_source"]
                result = {
                    "type": result_type,
                    "id": int(hit["_id"]),
                    "title": source.get("name") or source.get("title") or source.get("full_name") or source.get("username", ""),
                    "description": source.get("description") or source.get("email", ""),
                    "score": hit["_score"],
                    "url": f"/{entity_type}/{hit['_id']}",
                    "highlights": hit.get("highlight", {}),
                }
                results.append(result)

            return {
                "results": results,
                "total": response["hits"]["total"]["value"],
            }
        except Exception:
            logger.exception("Search failed for query: %s", query)
            return {"results": [], "total": 0}

    async def suggest(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get search suggestions using prefix matching.

        Args:
            query: Partial query string for suggestions.
            entity_types: List of entity types to search.
            limit: Maximum number of suggestions.

        Returns:
            List of suggestion dicts with type, id, and title.
        """
        if not self.is_available:
            return []

        if entity_types is None:
            entity_types = ["projects", "tasks", "users"]

        indices = [self._index_name(et) for et in entity_types]
        index_str = ",".join(indices)

        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "name^3",
                        "title^3",
                        "username^2",
                        "full_name^2",
                    ],
                    "type": "phrase_prefix",
                }
            },
            "size": limit,
            "_source": ["name", "title", "username", "full_name"],
        }

        try:
            response = await self.client.search(
                index=index_str,
                body=body,
                ignore_unavailable=True,
            )

            suggestions = []
            for hit in response["hits"]["hits"]:
                index_name = hit["_index"]
                entity_type = index_name.replace(f"{self.index_prefix}_", "")
                type_map = {"projects": "project", "tasks": "task", "users": "user"}
                result_type = type_map.get(entity_type, entity_type)

                source = hit["_source"]
                suggestions.append({
                    "type": result_type,
                    "id": int(hit["_id"]),
                    "title": source.get("name") or source.get("title") or source.get("full_name") or source.get("username", ""),
                })
            return suggestions
        except Exception:
            logger.exception("Suggest failed for query: %s", query)
            return []


# Global service instance
es_service: Optional[ElasticsearchService] = None


def get_elasticsearch_service() -> Optional[ElasticsearchService]:
    """Get the global Elasticsearch service instance."""
    return es_service
