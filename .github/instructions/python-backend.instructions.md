---
applyTo: backend/**/*.py
---

# Python Backend Instructions

## Structure
- Route handlers live in `backend/routers/` — one file per domain (e.g., `auth.py`, `projects.py`)
- Pydantic request/response schemas live in `backend/schemas.py`
- SQLAlchemy models live in `backend/models.py`
- Every new router must be registered in `backend/main.py` via `app.include_router(...)`
- Router must define a `prefix` and `tags`, e.g.: `router = APIRouter(prefix="/api/myroute", tags=["myroute"])`

## Database
- All database operations must use `async`/`await` with SQLAlchemy 2.0 async session (`AsyncSession`)
- Use `selectinload()` to eagerly load relationships and prevent N+1 queries
- Use `asyncio.gather()` to run independent queries in parallel
- Alembic migration required for any schema change: `alembic revision --autogenerate -m "description"` then `alembic upgrade head`
- Do NOT use `metadata` as a column name in SQLAlchemy models — it is reserved. Use `extra_data` instead
- Index names must be globally unique across all tables (prefix with table name, e.g., `idx_task_project_id`)

## Security
- Use `passlib[bcrypt]` for password hashing — never use `hashlib` directly
- JWT auth via `python-jose[cryptography]` — see `backend/security.py`
- All protected routes must use the `get_current_user` dependency from `backend/security.py`
- Input validation via Pydantic schemas — all API inputs must be validated
- Never commit secrets; use environment variables via `python-dotenv`

## Testing
- Every new endpoint needs a corresponding test in `backend/tests/test_<router_name>.py`
- Use SQLite in-memory (`sqlite+aiosqlite:///:memory:`) for test databases
- Tests use `TestClient` from `fastapi.testclient` with `app.dependency_overrides[get_db]` for DB injection
- The `test_db` fixture must be `async` and `asyncio_mode = "auto"` is set in `pyproject.toml`
- Run: `pytest backend/tests/ -v --override-ini="addopts="`

## Code Style
- Follow PEP 8 with 100 character line length
- Use type hints for all function signatures
- Use `async`/`await` for all I/O operations
- Use descriptive variable names — avoid single letters and abbreviations
- Format with `black backend/ --line-length 100`
