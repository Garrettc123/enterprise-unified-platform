# Copilot Instructions for Enterprise Unified Platform

## Project Overview

This is a production-grade enterprise platform with three main components:

1. **Backend**: FastAPI (Python 3.11+) REST API with SQLAlchemy ORM, JWT authentication, and WebSocket support
2. **Frontend**: React 18 + TypeScript with Vite build system
3. **Sync Systems**: Autonomous infrastructure synchronization across 25+ endpoints (Cloud, Database, Storage, Cache, Messages, Search, ML, GraphQL, Webhooks)

## Architecture

- **Backend**: `backend/` - FastAPI application with modular routers
- **Frontend**: `frontend/` - React SPA with TypeScript
- **Sync Systems**: Root-level Python modules (`sync_engine.py`, `database_sync.py`, etc.)
- **Orchestration**: `mega_orchestrator.py` - Master controller for sync systems
- **Deployment**: Docker Compose, Kubernetes manifests in `k8s/`

## Development Setup

### Prerequisites
- Python 3.11+ with virtual environment
- Node.js 18+ with npm
- Docker & Docker Compose
- PostgreSQL and Redis (via Docker or local)

### Backend Setup
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Full Stack with Docker
```bash
docker compose up -d
```

## Code Standards

### Python (Backend & Sync Systems)

**Style Guide:**
- Follow PEP 8 with 100 character line length
- Use type hints for all function signatures
- Write docstrings for public functions and classes
- Use meaningful variable names (no single letters except loop counters)

**Formatting & Linting:**
```bash
# Format code
black backend/ --line-length 100
black *.py --line-length 100

# Lint code
flake8 backend/ --max-line-length=100
ruff check backend/

# Type checking
mypy backend/ --strict
```

**Code Conventions:**
- Use `async`/`await` for I/O operations (database, API calls, file operations)
- Prefer SQLAlchemy ORM queries over raw SQL
- Use Pydantic models for request/response validation
- JWT tokens for authentication (OAuth2 scheme)
- Use structured logging with context (see `monitoring.py`)
- Password hashing: bcrypt with salt via `passlib`
- Use environment variables via `python-dotenv` for configuration

**Testing:**
```bash
pytest backend/tests/ -v
pytest backend/tests/ --cov=backend --cov-report=term-missing
pytest -m "not slow"  # Skip slow tests
```

### TypeScript/React (Frontend)

**Style Guide:**
- Use functional components with React Hooks
- Add TypeScript types for all props and state
- Follow React naming conventions (PascalCase for components)
- Use semantic HTML elements
- Keep components focused and single-responsibility

**Formatting & Linting:**
```bash
cd frontend
npm run lint
npm run build  # Runs tsc then vite build
```

**Code Conventions:**
- Use custom hooks for API communication
- Store authentication tokens in localStorage
- Use React Router v6 for routing with protected routes
- Error handling: react-hot-toast for user notifications
- API client: axios with base URL configuration

**Testing:**
```bash
cd frontend
npm test
npm run test:coverage
```

## Building & Running

### Backend
```bash
# Development
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend
```bash
cd frontend
npm run dev      # Development
npm run build    # Production build
npm run preview  # Preview production build
```

### Sync Systems
```bash
# Full mega sync (all 9 systems)
python run_mega_sync.py

# Specific systems
python run_mega_sync.py --mode cloud
python run_mega_sync.py --mode database
python run_mega_sync.py --mode check  # Health check

# Orchestrator with REST API
python run_orchestration.py
```

## Database

**ORM**: SQLAlchemy 2.0+ with async support (`asyncpg` driver)

**Migrations:**
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Models Location**: `backend/models.py`
**Schemas Location**: `backend/schemas.py` (Pydantic models)

## API Endpoints

Base URL: `http://localhost:8000/api`

**Key Routes:**
- `/auth/*` - Authentication (register, login, API keys)
- `/projects/*` - Project CRUD operations
- `/tasks/*` - Task management with comments
- `/organizations/*` - Organization and member management
- `/analytics/*` - Dashboard metrics and reports
- `/search` - Global search functionality
- `/export/*` - CSV/JSON data export
- `/files/*` - File upload and management
- `/audit/logs` - Audit log tracking

**API Documentation**: http://localhost:8000/docs (Swagger UI)

## Security Best Practices

1. **Never commit secrets** - Use `.env` file (see `.env.example`)
2. **JWT tokens** - Short expiration times, secure signing
3. **Password hashing** - Always use bcrypt via `passlib`
4. **SQL injection** - Use ORM parameterized queries (never string concatenation)
5. **XSS protection** - React escapes by default, validate API inputs with Pydantic
6. **CORS** - Configure allowed origins in `backend/config.py`
7. **Rate limiting** - Implemented in middleware (100 req/min per IP, configurable in `backend/middleware.py`)
8. **Input validation** - Use Pydantic schemas for all API inputs
9. **Authentication** - Check JWT token on protected routes
10. **Audit logging** - Log all sensitive operations to `audit_logs` table

## Common Tasks

### Adding a New API Endpoint
1. Create route handler in `backend/routers/` (e.g., `backend/routers/myrouter.py`)
2. Define Pydantic request/response schemas in `backend/schemas.py`
3. Add database model in `backend/models.py` if needed
4. Create migration: `alembic revision --autogenerate`
5. Include router in `backend/main.py`: `app.include_router(myrouter.router)`
6. Write tests in `backend/tests/test_myrouter.py`
7. Update frontend API client in `frontend/src/services/api.ts`

### Adding a Frontend Component
1. Create component in `frontend/src/components/MyComponent.tsx`
2. Add TypeScript interfaces for props
3. Use in page components from `frontend/src/pages/`
4. Add styles (component-level or global CSS)

### Adding a Sync System
1. Create module following pattern of `sync_engine.py` or `database_sync.py`
2. Implement async sync functions with error handling
3. Add system to `mega_orchestrator.py`
4. Update `run_mega_sync.py` CLI with new mode
5. Add monitoring metrics to `monitoring.py`

## Performance Considerations

1. **Database**: Add indexes on frequently queried columns, use pagination for large result sets
2. **API**: Use async operations, implement caching with Redis where appropriate
3. **Frontend**: Lazy load routes, optimize images, use React.memo for expensive components
4. **Sync Systems**: Parallel execution using asyncio.gather(), connection pooling

## Deployment

**Docker Compose** (Development/Testing):
```bash
docker compose -f docker-compose.full.yml up -d
```

**Kubernetes** (Production):
```bash
kubectl apply -f k8s/deployment.yaml
kubectl scale deployment mega-orchestrator --replicas=3
```

**Environment Variables**: Copy `.env.example` to `.env` and configure all required credentials

## Testing Strategy

1. **Unit tests** - Test individual functions and methods
2. **Integration tests** - Test API endpoints with database
3. **E2E tests** - Test full user workflows
4. **Async tests** - Use `pytest-asyncio` for async code
5. **Coverage target** - Minimum 80% code coverage

**Run all tests:**
```bash
pytest backend/tests/ -v --cov=backend --cov-fail-under=80
cd frontend && npm test
```

## Documentation

- **README.md** - Project overview and quick start
- **ARCHITECTURE.md** - System design and data models
- **DEVELOPMENT.md** - Detailed development guide
- **CONTRIBUTING.md** - Contribution guidelines and code standards
- **DEPLOYMENT.md** - Production deployment instructions
- **MEGA_SYNC_GUIDE.md** - Complete sync system user guide

## Git Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make focused, atomic commits with clear messages
3. Follow conventional commits: `feat:`, `fix:`, `docs:`, `test:`, etc.
4. Ensure all tests pass before committing
5. Run linters and formatters before pushing
6. Create PR with descriptive title and detailed description
7. Reference related issues in PR description

## Key Dependencies

**Backend:**
- fastapi>=0.109.0,<0.110.0 - Web framework
- sqlalchemy>=2.0.25,<3.0.0 - ORM
- pydantic>=2.6.0,<3.0.0 - Data validation
- asyncpg>=0.29.0,<0.30.0 - PostgreSQL async driver
- redis>=5.0.1,<6.0.0 - Caching
- python-jose>=3.3.0,<4.0.0 - JWT tokens
- passlib[bcrypt]>=1.7.4,<2.0.0 - Password hashing

**Frontend:**
- react@^18.2.0 - UI framework
- react-router-dom@^6.20.0 - Routing
- axios@^1.6.0 - HTTP client
- typescript@^5.2.2 - Type safety

**Sync Systems:**
- boto3>=1.34.0,<2.0.0 - AWS services
- google-cloud-storage>=2.14.0,<3.0.0 - GCP services
- pymongo>=4.5.0,<5.0.0 - MongoDB
- redis>=5.0.1,<6.0.0 - Redis cache
- kafka-python>=2.0.2,<3.0.0 - Kafka messaging
- elasticsearch>=8.10.0,<9.0.0 - Search engine
- mlflow>=2.10.0,<3.0.0 - ML platform

## Monitoring & Observability

**Metrics**: Prometheus client exports metrics
**Logging**: Structured logging with context (JSON format)
**Health Checks**: `/health` endpoint and `--mode check`
**Dashboards**: Grafana (port 3000), Prometheus (port 9090)
**Audit Logs**: Database table tracks all user actions

## Troubleshooting

**Port conflicts:**
```bash
lsof -i :8000  # Find process
kill -9 <PID>  # Kill process
```

**Database issues:**
- Verify DATABASE_URL in `.env`
- Check PostgreSQL is running: `docker compose ps`
- Reset database: `alembic downgrade base && alembic upgrade head`

**Frontend build issues:**
```bash
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

## Important Notes for AI Assistance

1. **Always run tests** after making changes to ensure nothing breaks
2. **Follow existing patterns** - Look at similar code before implementing new features
3. **Use type hints** - Python code should have type annotations
4. **Async/await** - Backend code should be async for I/O operations
5. **Pydantic validation** - All API inputs must be validated
6. **Security first** - Never bypass authentication or validation
7. **Document changes** - Update docstrings and comments for complex logic
8. **Error handling** - Always handle exceptions gracefully with proper logging
9. **Database migrations** - Create migrations for schema changes
10. **Test coverage** - Write tests for new features and bug fixes
