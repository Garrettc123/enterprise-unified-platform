# Development Guide - Enterprise Unified Platform

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git
- PostgreSQL (if not using Docker)
- Redis (if not using Docker)

### Quick Start with Docker

1. **Clone and setup**
```bash
git clone https://github.com/Garrettc123/enterprise-unified-platform.git
cd enterprise-unified-platform
cp .env.example .env
```

2. **Start all services**
```bash
docker compose up -d
```

3. **Access the platform**
- Frontend: http://localhost:5173
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Local Development Setup

**Backend Setup**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (using Docker)
docker compose up postgres redis -d

# Run migrations
alembic upgrade head

# Start development server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend Setup**
```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
enterprise-unified-platform/
├── backend/
│   ├── routers/              # API route handlers
│   │   ├── auth.py          # Authentication
│   │   ├── projects.py      # Project management
│   │   ├── tasks.py         # Task management
│   │   ├── organizations.py # Organization management
│   │   ├── analytics.py     # Analytics endpoints
│   │   ├── notifications.py # Notifications
│   │   ├── files.py         # File management
│   │   ├── search.py        # Search functionality
│   │   ├── export.py        # Data export
│   │   └── audit.py         # Audit logging
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas
│   ├── security.py          # Authentication & encryption
│   ├── database.py          # Database configuration
│   ├── middleware.py        # Custom middleware
│   ├── websocket_manager.py # WebSocket handling
│   ├── main.py              # FastAPI application
│   └── tests/               # Test suite
├── frontend/
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── services/        # API client
│   │   ├── App.tsx          # Main app component
│   │   └── main.tsx         # Entry point
│   ├── public/              # Static assets
│   └── vite.config.ts       # Vite configuration
├── docker compose.yml       # Docker orchestration
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── README.md                # Project overview
├── ARCHITECTURE.md          # System architecture
└── DEVELOPMENT.md           # This file
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user
- `POST /api/auth/api-keys` - Create API key
- `GET /api/auth/api-keys` - List API keys

### Projects
- `POST /api/projects` - Create project
- `GET /api/projects` - List projects
- `GET /api/projects/{id}` - Get project
- `PATCH /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project

### Tasks
- `POST /api/tasks` - Create task
- `GET /api/tasks` - List tasks
- `GET /api/tasks/{id}` - Get task
- `PATCH /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Delete task
- `POST /api/tasks/{id}/comments` - Add comment
- `GET /api/tasks/{id}/comments` - Get comments

### Organizations
- `POST /api/organizations` - Create organization
- `GET /api/organizations` - List organizations
- `GET /api/organizations/{id}` - Get organization
- `GET /api/organizations/{id}/members` - Get members
- `POST /api/organizations/{id}/members/{user_id}` - Add member
- `DELETE /api/organizations/{id}/members/{user_id}` - Remove member

### Analytics
- `GET /api/analytics/dashboard/overview` - Dashboard metrics
- `GET /api/analytics/projects/status-breakdown` - Project status
- `GET /api/analytics/tasks/priority-distribution` - Task priorities
- `GET /api/analytics/tasks/status-trend` - Completion trends
- `GET /api/analytics/team/workload` - Team workload

### Search & Export
- `GET /api/search?q=query` - Global search
- `GET /api/export/projects/csv` - Export projects
- `GET /api/export/tasks/json` - Export tasks

### Files
- `POST /api/files/upload/{task_id}` - Upload file
- `GET /api/files/{id}` - Download file
- `DELETE /api/files/{id}` - Delete file

### Audit
- `GET /api/audit/logs` - Get audit logs
- `GET /api/audit/summary` - Audit summary

## Testing

### Run Backend Tests
```bash
pytest backend/tests/ -v
pytest backend/tests/ --cov=backend  # With coverage
```

### Run Frontend Tests
```bash
cd frontend
npm test
npm run test:coverage  # With coverage
```

## Database Management

### Create Migration
```bash
alembic revision --autogenerate -m "Add new column"
```

### Apply Migrations
```bash
alembic upgrade head
```

### Rollback Migration
```bash
alembic downgrade -1
```

### View Database
```bash
# Using psql
psql -U enterprise -d enterprise_platform -h localhost

# Using Docker
docker compose exec db psql -U enterprise -d enterprise_platform
```

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
DEBUG=False
```

### Frontend (.env)
```
VITE_API_URL=http://localhost:8000/api
```

## Common Development Tasks

### Add New API Endpoint
1. Create route in `backend/routers/`
2. Define Pydantic schema in `models.py`
3. Write tests in `backend/tests/`
4. Include router in `main.py`
5. Create frontend API client in `src/services/api.ts`

### Add New Frontend Component
1. Create component in `frontend/src/components/`
2. Export from index file
3. Use in page components
4. Add styling in CSS file

### Add Database Model
1. Define model in `backend/models.py`
2. Create migration: `alembic revision --autogenerate`
3. Apply migration: `alembic upgrade head`

## Debugging

### Backend Debugging
```python
# In code
import logging
logger = logging.getLogger(__name__)
logger.info("Debug message")

# Or use pdb
import pdb; pdb.set_trace()
```

### Frontend Debugging
- Use React DevTools browser extension
- Open browser console (F12)
- Use VS Code debugger with Chrome

## Performance Tips

1. **Database Queries**
   - Use `.limit()` for large result sets
   - Add `.index` to frequently queried columns
   - Use `.select()` to fetch specific columns

2. **Frontend**
   - Use React.memo for expensive components
   - Implement code splitting with lazy loading
   - Optimize images and assets

3. **API Responses**
   - Paginate large datasets
   - Use appropriate HTTP caching headers
   - Compress responses with gzip

## Deployment

### Production Build
```bash
# Backend
pip install -r requirements.txt
gunicorn backend.main:app --workers 4

# Frontend
cd frontend
npm run build
# Serve dist folder
```

### Docker Deployment
```bash
docker compose -f docker compose.yml up -d
```

### Environment Setup
1. Set all required environment variables
2. Configure database with proper backups
3. Set up monitoring and logging
4. Configure SSL/TLS certificates
5. Set up CDN for static files

## Contributing

1. Create feature branch: `git checkout -b feature/name`
2. Make changes and commit: `git commit -m "Add feature"`
3. Push to branch: `git push origin feature/name`
4. Create Pull Request with description
5. Request review from team members

## Useful Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Run migrations
alembic upgrade head

# Create backup
pg_dump > backup.sql

# Restore from backup
psql < backup.sql

# Clean up Docker
docker compose down -v
```

## Troubleshooting

### Database Connection Issues
- Check DATABASE_URL format
- Verify PostgreSQL is running
- Check credentials

### Port Already in Use
```bash
# Find process using port
lsof -i :8000
# Kill process
kill -9 PID
```

### Frontend Build Issues
```bash
cd frontend
rm -rf node_modules
npm install
npm run build
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/)

## Support

For issues and questions:
1. Check existing GitHub issues
2. Create new issue with detailed description
3. Contact development team
