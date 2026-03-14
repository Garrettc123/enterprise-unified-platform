---
applyTo: "*.py"
---

# Sync Systems Instructions

These instructions apply to root-level Python sync modules:
`sync_engine.py`, `database_sync.py`, `storage_sync.py`, `cache_sync.py`,
`message_sync.py`, `search_sync.py`, `ml_pipeline_sync.py`, `graphql_sync.py`,
`webhook_sync.py`, `monitoring.py`, `mega_orchestrator.py`

## Structure & Patterns
- All sync modules must implement async functions using `asyncio`
- Use `asyncio.gather()` for parallel execution of independent sync tasks
- Base classes are in `sync_base.py` — extend `BaseConnector` and `BaseManager` to reduce duplication
- New sync systems must be registered in `mega_orchestrator.py`
- New sync modes must be exposed as `--mode` flags in `run_mega_sync.py`

## Configuration
- All configuration must come from environment variables via `python-dotenv`
- Never hardcode credentials, connection strings, or API keys
- See `.env.example` for the list of expected environment variables
- Use `pydantic-settings` for configuration validation

## Error Handling
- Catch exceptions per-endpoint with context logging
- Do NOT let one failure abort the full sync cycle — log and continue
- Use structured logging with context binding (see `monitoring.py`)
- Add Prometheus metrics for each new sync system (counters, histograms)

## Health Checks
- Every sync system must implement a health check method
- Register health checks in the `--mode check` path in `run_mega_sync.py`
- Health check should verify connectivity without performing writes

## Testing
- Unit tests for sync modules go in `tests/` (root level)
- Mock external services (AWS, GCP, Redis, etc.) with `unittest.mock`
- Never use real cloud credentials in tests — use environment variable mocks
