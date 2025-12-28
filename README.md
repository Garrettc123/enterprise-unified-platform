# 🚀 Enterprise Unified Platform

A comprehensive enterprise management system built with modern technologies for organizations to manage projects, tasks, teams, and analytics.

## Features

### 🔐 Security & Authentication
- JWT-based authentication
- OAuth2 support
- Secure password hashing with bcrypt
- API key management
- Rate limiting and request logging

### 📊 Project Management
- Create and manage projects
- Task tracking with status workflows
- Team collaboration features
- Milestone management
- Real-time updates via WebSockets

### 📈 Analytics & Reporting
- Dashboard with key metrics
- Project status breakdown
- Task completion trends
- Team workload analysis
- Historical data tracking

### 🔔 Notifications
- Real-time notifications
- Task assignments
- Comment mentions
- Project updates
- Customizable notification preferences

### 👥 Team Management
- Organization management
- Role-based access control
- Team collaboration
- Member management
- Activity tracking

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis
- **Real-time**: WebSockets
- **Authentication**: JWT, OAuth2
- **Task Queue**: Celery

### Frontend
- **Framework**: React 18
- **Language**: TypeScript
- **Build Tool**: Vite
- **State Management**: React Hooks
- **Styling**: CSS3
- **UI Components**: Custom built
- **HTTP Client**: Fetch API

### DevOps & Deployment
- Docker & Docker Compose
- GitHub Actions CI/CD
- PostgreSQL database
- Redis cache
- Uvicorn ASGI server

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/Garrettc123/enterprise-unified-platform.git
cd enterprise-unified-platform
```

2. **Set up environment variables**
```bash
cp .env.example .env
```

3. **Start with Docker Compose**
```bash
docker compose up -d
```

4. **Access the application**
- Frontend: http://localhost:5173
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Production Deployment

For production deployment, see the comprehensive [DEPLOYMENT.md](DEPLOYMENT.md) guide.

**Quick Deploy (Production)**:
```bash
# Copy and configure environment
cp .env.production .env
# Edit .env with your production values

# Run deployment script
./deploy.sh
```

Or manually with Docker Compose:
```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

**Important for Production**:
- Change `DB_PASSWORD` in `.env`
- Generate new `SECRET_KEY` (e.g., `openssl rand -hex 32`)
- Use HTTPS with a reverse proxy (Nginx/Caddy)
- Configure firewall rules
- Set up automated backups

### Development

**Backend Development**
```bash
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

**Frontend Development**
```bash
cd frontend
npm install
npm run dev
```

**Run Tests**
```bash
# Backend tests
pytest backend/tests/

# Frontend tests
cd frontend && npm run test
```

## API Documentation

Interactive API documentation available at `/docs` (Swagger UI) or `/redoc` (ReDoc)

### Authentication
All API endpoints (except `/auth/login` and `/auth/register`) require authentication via JWT token in the `Authorization: Bearer {token}` header.

### Example Request
```bash
curl -X GET http://localhost:8000/api/projects \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Project Structure

```
enterprise-unified-platform/
├── backend/
│   ├── models.py           # Database models
│   ├── schemas.py          # Pydantic schemas
│   ├── security.py         # Auth & security
│   ├── main.py             # FastAPI app
│   ├── database.py         # DB config
│   ├── middleware.py       # Custom middleware
│   ├── websocket_manager.py# WebSocket handling
│   └── routers/
│       ├── auth.py         # Auth endpoints
│       ├── projects.py     # Project endpoints
│       ├── tasks.py        # Task endpoints
│       ├── organizations.py# Org endpoints
│       ├── analytics.py    # Analytics endpoints
│       └── notifications.py# Notifications
├── frontend/
│   ├── src/
│   │   ├── pages/          # Page components
│   │   ├── components/     # Reusable components
│   │   ├── hooks/          # Custom hooks
│   │   ├── services/       # API client
│   │   ├── App.tsx         # Main app
│   │   └── main.tsx        # Entry point
│   └── public/             # Static assets
├── docker-compose.yml      # Docker setup
├── requirements.txt        # Python dependencies
└── .github/workflows/      # CI/CD pipelines
```

## Environment Variables

See `.env.example` for all available configuration options.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions, please open a GitHub issue.
