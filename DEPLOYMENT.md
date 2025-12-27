# Deployment Guide - Enterprise Unified Platform

This guide explains how to deploy the Enterprise Unified Platform to production.

## Prerequisites

- Docker and Docker Compose installed on the target server
- Git installed
- Domain name (optional, but recommended)
- SSL certificates (recommended for production)

## Deployment Options

### Option 1: Docker Compose Deployment (Recommended for Single Server)

This is the simplest deployment method, suitable for small to medium deployments.

#### 1. Clone the Repository

```bash
git clone https://github.com/Garrettc123/enterprise-unified-platform.git
cd enterprise-unified-platform
```

#### 2. Configure Environment Variables

Copy the production environment template and update with your values:

```bash
cp .env.production .env
```

**IMPORTANT**: Edit `.env` and change the following:
- `DB_PASSWORD`: Set a strong database password
- `SECRET_KEY`: Generate a secure random string (e.g., using `openssl rand -hex 32`)
- `VITE_API_URL`: Update to your production domain if using one

#### 3. Build and Start Services

```bash
docker-compose -f docker-compose.prod.yml up -d
```

This will:
- Start PostgreSQL database
- Start Redis cache
- Build and start the backend API
- Build and start the frontend application

#### 4. Run Database Migrations

```bash
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

#### 5. Verify Deployment

Check that all services are running:

```bash
docker-compose -f docker-compose.prod.yml ps
```

Test the health endpoints:

```bash
# Backend health check
curl http://localhost:8000/health

# Frontend (should return the HTML page)
curl http://localhost:5173
```

#### 6. Access the Application

- **Frontend**: http://your-domain:5173 (or http://localhost:5173)
- **API Documentation**: http://your-domain:8000/docs
- **API**: http://your-domain:8000/api

### Option 2: GitHub Actions Automated Deployment

The repository includes a GitHub Actions workflow for automated deployment.

#### Setup

1. **Add GitHub Secrets**: Go to your repository settings and add these secrets:
   - `DEPLOY_KEY`: SSH private key for accessing your server
   - `DEPLOY_HOST`: Your server hostname or IP address
   - `DEPLOY_USER`: SSH username for your server

2. **Prepare Your Server**:
   ```bash
   # On your server
   mkdir -p /app
   cd /app
   git clone https://github.com/Garrettc123/enterprise-unified-platform.git .
   cp .env.production .env
   # Edit .env with your production values
   ```

3. **Deploy**: Push to the `main` branch, and GitHub Actions will automatically deploy.

## Production Best Practices

### Security

1. **Change Default Passwords**
   - Update `DB_PASSWORD` in `.env`
   - Generate a new `SECRET_KEY` using: `openssl rand -hex 32`

2. **Use HTTPS**
   - Set up a reverse proxy (Nginx or Caddy)
   - Obtain SSL certificates (Let's Encrypt recommended)

3. **Firewall Configuration**
   - Only expose ports 80 (HTTP) and 443 (HTTPS) to the internet
   - Keep database and Redis ports (5432, 6379) internal

4. **Regular Updates**
   - Keep Docker images updated
   - Apply security patches promptly

### Performance

1. **Database Optimization**
   - Configure PostgreSQL for production workloads
   - Set up regular backups
   - Consider read replicas for high traffic

2. **Caching**
   - Redis is configured for session and data caching
   - Configure cache TTLs based on your needs

3. **Resource Limits**
   - Add resource limits to docker-compose.prod.yml if needed:
     ```yaml
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
     ```

### Monitoring

1. **Logs**
   ```bash
   # View all logs
   docker-compose -f docker-compose.prod.yml logs -f
   
   # View specific service logs
   docker-compose -f docker-compose.prod.yml logs -f backend
   ```

2. **Health Checks**
   - Backend health: `curl http://localhost:8000/health`
   - Monitor container health: `docker-compose -f docker-compose.prod.yml ps`

3. **Database Backups**
   ```bash
   # Backup
   docker-compose -f docker-compose.prod.yml exec db pg_dump -U enterprise enterprise_platform > backup.sql
   
   # Restore
   docker-compose -f docker-compose.prod.yml exec -T db psql -U enterprise enterprise_platform < backup.sql
   ```

### Scaling

For larger deployments, consider:
- Using Kubernetes for orchestration
- Implementing a load balancer (e.g., Nginx, HAProxy)
- Separating database to a managed service (AWS RDS, Azure Database)
- Using a CDN for static assets
- Implementing horizontal scaling with multiple backend instances

## Reverse Proxy Setup (Optional)

### Using Nginx

1. **Install Nginx**:
   ```bash
   sudo apt-get update
   sudo apt-get install nginx certbot python3-certbot-nginx
   ```

2. **Configure Nginx**:
   Create `/etc/nginx/sites-available/enterprise-platform`:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       # Frontend
       location / {
           proxy_pass http://localhost:5173;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
       
       # Backend API
       location /api {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
       
       # API Docs
       location /docs {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
       
       # WebSocket support
       location /ws {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   ```

3. **Enable the site**:
   ```bash
   sudo ln -s /etc/nginx/sites-available/enterprise-platform /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. **Setup SSL with Let's Encrypt**:
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

## Troubleshooting

### Services Won't Start

Check logs:
```bash
docker-compose -f docker-compose.prod.yml logs
```

### Database Connection Errors

1. Verify database is healthy:
   ```bash
   docker-compose -f docker-compose.prod.yml ps db
   ```

2. Check DATABASE_URL in .env matches your configuration

### Port Already in Use

Find and stop conflicting services:
```bash
sudo lsof -i :8000
sudo lsof -i :5173
```

### Frontend Can't Connect to Backend

1. Check VITE_API_URL in .env
2. Verify backend is accessible
3. Check CORS settings if using a different domain

## Updating the Application

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart services
docker-compose -f docker-compose.prod.yml up -d --build

# Run any new migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

## Rollback

If you need to rollback to a previous version:

```bash
# Stop services
docker-compose -f docker-compose.prod.yml down

# Checkout previous version
git checkout <previous-commit-hash>

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

# Rollback database if needed
docker-compose -f docker-compose.prod.yml exec backend alembic downgrade -1
```

## Support

For issues or questions:
1. Check the [DEVELOPMENT.md](DEVELOPMENT.md) guide
2. Review logs for error messages
3. Open an issue on GitHub with details
