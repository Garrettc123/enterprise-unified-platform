#!/bin/bash
set -e

# Enterprise Unified Platform - Quick Deploy Script
echo "🚀 Enterprise Unified Platform Deployment"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    if [ -f .env.production ]; then
        cp .env.production .env
        echo "✅ Created .env from .env.production template"
        echo ""
        echo "⚠️  IMPORTANT: Please edit .env and set:"
        echo "   - DB_PASSWORD (strong password)"
        echo "   - SECRET_KEY (run: openssl rand -hex 32)"
        echo "   - VITE_API_URL (your production domain if applicable)"
        echo ""
        read -p "Press Enter after updating .env to continue, or Ctrl+C to exit..."
    else
        echo "❌ .env.production template not found!"
        exit 1
    fi
fi

# Validate critical environment variables
source .env
if [ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "CHANGE_ME_IN_PRODUCTION" ]; then
    echo "❌ DB_PASSWORD not set or still has default value!"
    echo "   Please update DB_PASSWORD in .env"
    exit 1
fi

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "CHANGE_ME_TO_A_SECURE_RANDOM_STRING_IN_PRODUCTION" ]; then
    echo "❌ SECRET_KEY not set or still has default value!"
    echo "   Generate one with: openssl rand -hex 32"
    echo "   Then update SECRET_KEY in .env"
    exit 1
fi

echo "✅ Environment configuration validated"
echo ""

# Ask for deployment mode
echo "Select deployment mode:"
echo "1) Production (docker-compose.prod.yml)"
echo "2) Development (docker-compose.yml)"
read -p "Enter choice [1-2]: " choice

case $choice in
    1)
        COMPOSE_FILE="docker-compose.prod.yml"
        MODE="Production"
        ;;
    2)
        COMPOSE_FILE="docker-compose.yml"
        MODE="Development"
        ;;
    *)
        echo "Invalid choice. Using Production mode."
        COMPOSE_FILE="docker-compose.prod.yml"
        MODE="Production"
        ;;
esac

echo ""
echo "🔧 Deploying in $MODE mode using $COMPOSE_FILE"
echo ""

# Pull latest images
echo "📥 Pulling base images..."
docker compose -f $COMPOSE_FILE pull db redis

# Build services
echo "🔨 Building application images..."
docker compose -f $COMPOSE_FILE build

# Start services
echo "🚀 Starting services..."
docker compose -f $COMPOSE_FILE up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service status
echo ""
echo "📊 Service Status:"
docker compose -f $COMPOSE_FILE ps

# Run migrations
echo ""
echo "🗄️  Running database migrations..."
docker compose -f $COMPOSE_FILE exec -T backend alembic upgrade head || echo "⚠️  Migration failed or not configured"

# Display access information
echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Access URLs:"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📝 Useful commands:"
echo "   View logs: docker compose -f $COMPOSE_FILE logs -f"
echo "   Stop services: docker compose -f $COMPOSE_FILE down"
echo "   Restart services: docker compose -f $COMPOSE_FILE restart"
echo "   Check status: docker compose -f $COMPOSE_FILE ps"
echo ""
echo "💡 For production, consider:"
echo "   - Setting up a reverse proxy (Nginx) with SSL"
echo "   - Configuring firewall rules"
echo "   - Setting up automated backups"
echo "   - Implementing monitoring and alerting"
echo ""
echo "📖 See DEPLOYMENT.md for detailed instructions"
