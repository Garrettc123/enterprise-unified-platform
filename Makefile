.PHONY: help install dev build test lint clean docker-up docker-down migrate

help:
	@echo "Available commands:"
	@echo "  make install         - Install all dependencies"
	@echo "  make dev             - Start development servers"
	@echo "  make build           - Build for production"
	@echo "  make test            - Run all tests"
	@echo "  make lint            - Run linting"
	@echo "  make clean           - Clean build artifacts"
	@echo "  make docker-up       - Start Docker containers"
	@echo "  make docker-down     - Stop Docker containers"
	@echo "  make migrate         - Run database migrations"

install:
	pip install -r requirements.txt
	cd frontend && npm install

dev:
	docker-compose up -d
	@echo "Starting backend..."
	uvicorn backend.main:app --reload &
	@echo "Starting frontend..."
	cd frontend && npm run dev

build:
	cd frontend && npm run build

test:
	pytest backend/tests/ -v
	cd frontend && npm test

lint:
	flake8 backend/
	cd frontend && npm run lint

clean:
	rm -rf backend/__pycache__
	rm -rf backend/*.pyc
	rm -rf frontend/dist
	rm -rf frontend/node_modules
	docker-compose down -v

docker-up:
	docker-compose up -d
	docker-compose logs -f

docker-down:
	docker-compose down

migrate:
	alembic upgrade head
