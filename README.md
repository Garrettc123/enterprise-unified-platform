# Enterprise Unified Platform - Full Autonomous Sync

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen)

**Real-time autonomous synchronization across multiple cloud providers and databases**

[Documentation](#documentation) • [Quick Start](#quick-start) • [API Reference](#api-reference) • [Architecture](#architecture)

</div>

---

## Overview

The **Enterprise Unified Platform** is a production-grade autonomous sync orchestration system that continuously synchronizes:

- **Code Deployment**: GitHub → AWS, GCP, Azure, Render, Vercel (5+ cloud providers)
- **Data Replication**: PostgreSQL ↔ MongoDB, DynamoDB, Firestore, Elasticsearch
- **Real-time Monitoring**: Health checks, status reporting, deployment verification
- **Webhook Integration**: GitHub push events trigger immediate synchronization

### Key Features

✅ **Autonomous**: Runs continuously with minimal intervention
✅ **Multi-Cloud**: Deploy to 5+ cloud providers simultaneously
✅ **Database Replication**: Bidirectional data sync across heterogeneous databases
✅ **Real-time**: GitHub webhook triggers instant deployment
✅ **Resilient**: Automatic retry, error recovery, health monitoring
✅ **Observable**: Complete audit trail, status APIs, health endpoints
✅ **Scalable**: Async/await architecture, concurrent operations

---

## Quick Start

### Prerequisites

- Python 3.9+
- pip or poetry
- Git
- Docker (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/garrettc123/enterprise-unified-platform.git
cd enterprise-unified-platform

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
```

### Configure Credentials

Edit `.env` with your cloud provider and database credentials:

```env
# Cloud Providers
AWS_CREDENTIALS=your-aws-access-key
GCP_CREDENTIALS=your-gcp-service-account-json
AZURE_CREDENTIALS=your-azure-connection-string
RENDER_API_KEY=your-render-token
VERCEL_TOKEN=your-vercel-token

# Databases
POSTGRES_PROD=postgresql://user:password@host:5432/database
MONGO_ANALYTICS=mongodb://user:password@host/database
DYNAMODB_CACHE=dynamodb://region/table-name
ELASTICSEARCH_SEARCH=https://user:password@host:9200

# GitHub
GITHUB_TOKEN=your-github-personal-access-token
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

### Run Full Orchestration

```bash
# Option 1: Direct Python execution
python run_orchestration.py full

# Option 2: Docker Compose
docker-compose up -d

# Option 3: FastAPI with Uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs

# Check orchestration status
curl http://localhost:8000/api/v1/orchestration/status
```

---

## Documentation

### Running Modes

#### Full Autonomous Sync (Recommended)
```bash
python run_orchestration.py full
```
Synchronizes code to all cloud providers AND data across all databases.

#### Cloud-Only Sync
```bash
python run_orchestration.py cloud-only
```
Deploys code changes to AWS, GCP, Azure, Render, Vercel only.

#### Database-Only Sync
```bash
python run_orchestration.py database-only
```
Replicates data between databases without code deployment.

#### Monitor Mode
```bash
python run_orchestration.py monitor
```
Monitors system health and status without triggering sync operations.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   AUTONOMOUS SYNC ORCHESTRATION                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
        ┌───────▼────────┐ ┌──▼──────────┐ ┌─▼───────────────┐
        │  Sync Engine   │ │ Database    │ │ Webhook         │
        │  (Cloud Code)  │ │ Sync Mgr    │ │ Receiver        │
        └───────┬────────┘ └──┬──────────┘ └─┬───────────────┘
                │              │              │
        ┌───────▼────────┐ ┌──▼──────────┐   │
        │  AWS           │ │ PostgreSQL  │   │
        │  GCP           │ │ MongoDB     │   │
        │  Azure         │ │ DynamoDB    │   │
        │  Render        │ │ Firestore   │   │
        │  Vercel        │ │ Elasticsearch   │
        └────────────────┘ └─────────────┘   │
                                              │
                                    GitHub Push Event
```

### Sync Workflow

1. **Detect Changes**: Monitor GitHub for code commits (webhook or polling)
2. **Hash Comparison**: Check if code has actually changed (SHA-256)
3. **Parallel Deploy**: Simultaneously push to 5 cloud providers
4. **Verify**: Health checks on each deployed service
5. **Replicate Data**: Sync data changes to all databases
6. **Record**: Store complete audit trail of all operations
7. **Wait**: Sleep until next check interval (default 60s)
8. **Repeat**: Continuous autonomous operation

---

## API Reference

### Base URL
```
http://localhost:8000
```

### Authentication
Currently uses environment-based credentials. Add OAuth2 for production.

### Endpoints

#### Health & Info

**GET** `/health` - Health check
```bash
curl http://localhost:8000/health
```

**GET** `/` - API info
```bash
curl http://localhost:8000/
```

**GET** `/api/v1/info` - Detailed API information
```bash
curl http://localhost:8000/api/v1/info
```

#### Orchestration Control

**POST** `/api/v1/orchestration/start` - Start sync orchestration
```bash
curl -X POST http://localhost:8000/api/v1/orchestration/start
```

**POST** `/api/v1/orchestration/stop` - Stop orchestration
```bash
curl -X POST http://localhost:8000/api/v1/orchestration/stop
```

**GET** `/api/v1/orchestration/status` - Get full orchestration status
```bash
curl http://localhost:8000/api/v1/orchestration/status
```

#### Cloud Sync

**GET** `/api/v1/sync/status` - Cloud sync status
```bash
curl http://localhost:8000/api/v1/sync/status
```

**GET** `/api/v1/sync/history` - Recent sync history
```bash
curl http://localhost:8000/api/v1/sync/history?limit=10
```

**GET** `/api/v1/providers` - List cloud providers
```bash
curl http://localhost:8000/api/v1/providers
```

**GET** `/api/v1/providers/{provider}` - Get provider status
```bash
curl http://localhost:8000/api/v1/providers/aws-production
```

#### Database Sync

**GET** `/api/v1/database/status` - Database sync status
```bash
curl http://localhost:8000/api/v1/database/status
```

**GET** `/api/v1/database/history` - Database sync history
```bash
curl http://localhost:8000/api/v1/database/history?limit=10
```

**GET** `/api/v1/databases` - List databases
```bash
curl http://localhost:8000/api/v1/databases
```

**GET** `/api/v1/sync-pairs` - List sync pairs
```bash
curl http://localhost:8000/api/v1/sync-pairs
```

---

## Configuration

### Environment Variables

See `.env.example` for complete list. Key variables:

```env
# Cloud Provider Credentials
AWS_CREDENTIALS          # AWS Access Key or IAM Role
GCP_CREDENTIALS         # GCP Service Account JSON
AZURE_CREDENTIALS       # Azure Connection String
RENDER_API_KEY          # Render API Key
VERCEL_TOKEN            # Vercel API Token

# Database Connection Strings
POSTGRES_PROD           # Primary PostgreSQL instance
POSTGRES_BACKUP         # Backup PostgreSQL instance
MONGO_ANALYTICS         # MongoDB Analytics database
DYNAMODB_CACHE          # AWS DynamoDB table
ELASTICSEARCH_SEARCH    # Elasticsearch cluster

# GitHub Integration
GITHUB_TOKEN            # GitHub Personal Access Token
GITHUB_WEBHOOK_SECRET   # Webhook signature secret
```

### Customization

Edit `service_integration.py` to:
- Add/remove cloud providers
- Configure database connections
- Change sync intervals
- Modify sync pair directions

---

## Monitoring & Logs

### Log Files

Logs are written to `sync_orchestration_YYYYMMDD_HHMMSS.log`

```bash
# Watch logs in real-time
tail -f sync_orchestration_*.log

# Filter for errors
grep ERROR sync_orchestration_*.log

# Filter for specific provider
grep "aws-production" sync_orchestration_*.log
```

### Metrics Tracked

- Sync duration (ms)
- Records synchronized
- Success/failure rates
- Provider availability
- Database connectivity
- Data consistency checks

### Alerts

The system logs:
- ✅ Successful syncs
- ⚠️ Partial failures
- ❌ Complete failures
- 🔄 Retry attempts
- 📊 Performance metrics

---

## Performance

### Typical Metrics

- **Cloud Sync**: ~5-10s per cycle (5 providers in parallel)
- **Database Sync**: ~2-5s per pair (configurable batch size)
- **Health Check**: ~30-60s intervals
- **Change Detection**: Instant (SHA-256 comparison)

### Optimization

1. **Increase batch size** for faster database sync
2. **Reduce check intervals** for faster deployment
3. **Use connection pooling** for database connections
4. **Enable caching** for frequently accessed data
5. **Parallel operations** are automatic

---

## Troubleshooting

### Sync not starting
```bash
# Check if orchestrator is initialized
curl http://localhost:8000/api/v1/orchestration/status

# View logs
tail -f sync_orchestration_*.log | grep -i error

# Restart application
kill $(ps aux | grep run_orchestration | grep -v grep | awk '{print $2}')
python run_orchestration.py full
```

### Cloud provider deployment failing
```bash
# Check provider status
curl http://localhost:8000/api/v1/providers/aws-production

# Verify credentials in .env
cat .env | grep AWS_CREDENTIALS

# Check cloud provider API status
# AWS: https://status.aws.amazon.com
# GCP: https://status.cloud.google.com
# Azure: https://status.azure.com
```

### Database sync failing
```bash
# Check database status
curl http://localhost:8000/api/v1/databases

# Verify connection strings
cat .env | grep POSTGRES

# Check database logs directly
# psql: psql -h host -U user -d database -c "SELECT 1;"
# MongoDB: mongosh "mongodb://..."
```

---

## Security

### Best Practices

1. ✅ Store credentials in `.env` (never commit)
2. ✅ Use IAM roles instead of API keys when possible
3. ✅ Enable webhook signature verification
4. ✅ Use HTTPS for all external connections
5. ✅ Rotate credentials every 90 days
6. ✅ Enable audit logging on all services
7. ✅ Whitelist IP addresses for webhooks
8. ✅ Use least-privilege permissions

### Credential Management

```bash
# Never commit .env file
echo ".env" >> .gitignore
git rm --cached .env

# Use AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id enterprise-platform

# Use GCP Secret Manager
gcloud secrets versions access latest --secret=enterprise-platform

# Use Azure Key Vault
az keyvault secret show --vault-name enterprise-platform
```

---

## Deployment

### Docker

```bash
# Build image
docker build -t enterprise-platform:latest .

# Run container
docker run -p 8000:8000 \
  --env-file .env \
  --name enterprise-platform \
  enterprise-platform:latest

# Using docker-compose
docker-compose up -d
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: enterprise-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: enterprise-platform
  template:
    metadata:
      labels:
        app: enterprise-platform
    spec:
      containers:
      - name: api
        image: enterprise-platform:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: enterprise-platform-secrets
```

### Cloud Platforms

**Render.com**
```bash
git push render main
# Auto-deploys from git
```

**Vercel**
```bash
vercel deploy
```

**AWS ECS**
```bash
aws ecs create-service --cluster production \
  --service-name enterprise-platform \
  --task-definition enterprise-platform:1
```

---

## Contributing

1. Fork repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## License

MIT License - See LICENSE file for details

---

## Support & Contact

- 📧 Email: [contact@example.com](mailto:contact@example.com)
- 🐛 Issues: [GitHub Issues](https://github.com/garrettc123/enterprise-unified-platform/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/garrettc123/enterprise-unified-platform/discussions)
- 📚 Documentation: [Full Documentation](./ORCHESTRATION.md)

---

<div align="center">

**Made with ❤️ for enterprise scale**

Repository: [garrettc123/enterprise-unified-platform](https://github.com/garrettc123/enterprise-unified-platform)

</div>
