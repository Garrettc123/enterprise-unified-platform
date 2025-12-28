# 🚀 Quick Deployment Guide

This is a quick reference for deploying the Enterprise Unified Platform.

## Prerequisites

✅ Docker and Docker Compose installed  
✅ Git installed  
✅ Server with at least 2GB RAM

## Deployment Steps

### 1️⃣ Validate Setup

```bash
./validate-deployment.sh
```

This checks that all configuration files and dependencies are correct.

### 2️⃣ Configure Environment

```bash
# Copy the production environment template
cp .env.production .env

# Generate a secure secret key
openssl rand -hex 32

# Edit .env and set:
# - DB_PASSWORD (use a strong password)
# - SECRET_KEY (paste the generated key above)
# - VITE_API_URL (your production domain or http://localhost:8000/api)
nano .env  # or use your preferred editor
```

### 3️⃣ Deploy

**Option A: Automated Deployment Script**
```bash
./deploy.sh
```

**Option B: Manual Deployment**
```bash
# Build and start services
docker compose -f docker-compose.prod.yml up -d

# Run database migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Check service status
docker compose -f docker-compose.prod.yml ps
```

### 4️⃣ Verify Deployment

```bash
# Check backend health
curl http://localhost:8000/health

# Check logs
docker compose -f docker-compose.prod.yml logs -f
```

### 5️⃣ Access Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Useful Commands

### View Logs
```bash
docker compose -f docker-compose.prod.yml logs -f [service_name]
```

### Restart Services
```bash
docker compose -f docker-compose.prod.yml restart
```

### Stop Services
```bash
docker compose -f docker-compose.prod.yml down
```

### Update Application
```bash
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Database Backup
```bash
docker compose -f docker-compose.prod.yml exec db pg_dump -U enterprise enterprise_platform > backup.sql
```

## Production Checklist

Before going live:

- [ ] Changed `DB_PASSWORD` from default value
- [ ] Generated and set secure `SECRET_KEY`
- [ ] Updated `VITE_API_URL` if using custom domain
- [ ] Set up reverse proxy (Nginx/Caddy) with SSL
- [ ] Configured firewall (only ports 80/443 exposed)
- [ ] Set up automated backups
- [ ] Configured monitoring and alerting
- [ ] Tested application functionality
- [ ] Reviewed security settings

## Troubleshooting

**Services won't start?**
```bash
docker compose -f docker-compose.prod.yml logs
```

**Database connection errors?**
```bash
docker compose -f docker-compose.prod.yml ps db
docker compose -f docker-compose.prod.yml logs db
```

**Port already in use?**
```bash
sudo lsof -i :8000
sudo lsof -i :5173
```

## Support

For detailed documentation:
- Full deployment guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- Development guide: [DEVELOPMENT.md](DEVELOPMENT.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

For issues: [GitHub Issues](https://github.com/Garrettc123/enterprise-unified-platform/issues)
