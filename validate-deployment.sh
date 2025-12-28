#!/bin/bash
# Deployment System Validation Script
# This script validates the deployment configuration without actually deploying

set -e

echo "=========================================="
echo "🧪 Deployment System Validation"
echo "=========================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✓${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
}

# Check Docker
echo "1. Checking Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    pass "Docker is installed: $DOCKER_VERSION"
else
    fail "Docker is not installed"
    exit 1
fi

# Check Docker Compose
echo ""
echo "2. Checking Docker Compose..."
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version)
    pass "Docker Compose is installed: $COMPOSE_VERSION"
else
    fail "Docker Compose is not installed"
    exit 1
fi

# Validate docker-compose.prod.yml
echo ""
echo "3. Validating docker-compose.prod.yml..."
if docker compose -f docker-compose.prod.yml config > /dev/null 2>&1; then
    pass "docker-compose.prod.yml syntax is valid"
else
    fail "docker-compose.prod.yml has syntax errors"
    exit 1
fi

# Validate docker-compose.yml
echo ""
echo "4. Validating docker-compose.yml..."
if docker compose -f docker-compose.yml config > /dev/null 2>&1; then
    pass "docker-compose.yml syntax is valid"
else
    fail "docker-compose.yml has syntax errors"
    exit 1
fi

# Check Dockerfiles
echo ""
echo "5. Checking Dockerfiles..."
if [ -f "Dockerfile.backend" ]; then
    pass "Dockerfile.backend exists"
else
    fail "Dockerfile.backend not found"
    exit 1
fi

if [ -f "Dockerfile.frontend" ]; then
    pass "Dockerfile.frontend exists"
else
    fail "Dockerfile.frontend not found"
    exit 1
fi

# Check environment files
echo ""
echo "6. Checking environment configuration..."
if [ -f ".env.production" ]; then
    pass ".env.production template exists"
else
    fail ".env.production template not found"
    exit 1
fi

if [ -f ".env.example" ]; then
    pass ".env.example template exists"
else
    warn ".env.example template not found"
fi

# Check deploy script
echo ""
echo "7. Checking deploy script..."
if [ -f "deploy.sh" ]; then
    pass "deploy.sh exists"
    if [ -x "deploy.sh" ]; then
        pass "deploy.sh is executable"
    else
        warn "deploy.sh is not executable (will still work with 'bash deploy.sh')"
    fi
    # Validate bash syntax
    if bash -n deploy.sh 2>/dev/null; then
        pass "deploy.sh syntax is valid"
    else
        fail "deploy.sh has syntax errors"
        exit 1
    fi
else
    fail "deploy.sh not found"
    exit 1
fi

# Check requirements.txt
echo ""
echo "8. Checking Python requirements..."
if [ -f "requirements.txt" ]; then
    pass "requirements.txt exists"
    echo "   Key dependencies:"
    grep -E "^(fastapi|uvicorn|sqlalchemy|alembic|pydantic|python-jose|passlib)" requirements.txt | sed 's/^/   - /'
else
    fail "requirements.txt not found"
    exit 1
fi

# Check backend structure
echo ""
echo "9. Checking backend structure..."
if [ -d "backend" ]; then
    pass "backend directory exists"
    required_files=("main.py" "models.py" "database.py" "security.py")
    for file in "${required_files[@]}"; do
        if [ -f "backend/$file" ]; then
            pass "backend/$file exists"
        else
            fail "backend/$file not found"
            exit 1
        fi
    done
else
    fail "backend directory not found"
    exit 1
fi

# Check frontend structure
echo ""
echo "10. Checking frontend structure..."
if [ -d "frontend" ]; then
    pass "frontend directory exists"
    if [ -f "frontend/package.json" ]; then
        pass "frontend/package.json exists"
    else
        fail "frontend/package.json not found"
        exit 1
    fi
    if [ -f "frontend/vite.config.ts" ]; then
        pass "frontend/vite.config.ts exists"
    else
        fail "frontend/vite.config.ts not found"
        exit 1
    fi
else
    fail "frontend directory not found"
    exit 1
fi

# Check alembic configuration
echo ""
echo "11. Checking Alembic migration configuration..."
if [ -f "alembic.ini" ]; then
    pass "alembic.ini exists"
else
    fail "alembic.ini not found"
    exit 1
fi

if [ -d "alembic" ]; then
    pass "alembic directory exists"
    if [ -f "alembic/env.py" ]; then
        pass "alembic/env.py exists"
    else
        fail "alembic/env.py not found"
        exit 1
    fi
else
    fail "alembic directory not found"
    exit 1
fi

# Check GitHub Actions workflow
echo ""
echo "12. Checking GitHub Actions workflow..."
if [ -f ".github/workflows/deploy.yml" ]; then
    pass ".github/workflows/deploy.yml exists"
else
    warn ".github/workflows/deploy.yml not found"
fi

# Check documentation
echo ""
echo "13. Checking documentation..."
docs=("README.md" "DEPLOYMENT.md")
for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        pass "$doc exists"
    else
        warn "$doc not found"
    fi
done

# Summary
echo ""
echo "=========================================="
echo "✅ Deployment System Validation Complete!"
echo "=========================================="
echo ""
echo "📋 Summary:"
echo "   - Docker and Docker Compose: Ready"
echo "   - Configuration files: Valid"
echo "   - Application structure: Complete"
echo "   - Migration system: Configured"
echo ""
echo "🚀 Next Steps for Production Deployment:"
echo "   1. Copy .env.production to .env"
echo "   2. Edit .env and set:"
echo "      - DB_PASSWORD (strong password)"
echo "      - SECRET_KEY (run: openssl rand -hex 32)"
echo "      - VITE_API_URL (your production domain)"
echo "   3. Run: ./deploy.sh"
echo ""
echo "📖 For detailed instructions, see: DEPLOYMENT.md"
echo ""
