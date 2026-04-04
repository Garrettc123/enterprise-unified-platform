# Enterprise Unified Platform — Copilot Instructions

## Purpose
Enterprise-grade unified platform: Next.js 14 frontend + FastAPI backend + real-time analytics.

## Stack
- **Frontend**: Next.js 14, TypeScript, Tailwind
- **Backend**: FastAPI (Python 3.11), PostgreSQL, Redis
- **Infra**: Docker, GitHub Actions, AWS

## Standards
- All API routes must have OpenAPI docs via FastAPI's auto-docs
- All env vars must come from `.env` or AWS SSM — never hardcoded
- All new features need a corresponding GitHub Actions CI check
- PRs must not break existing `/health` endpoints
- Use `continue-on-error: true` on optional CI steps
- All workflows must support `workflow_dispatch` for manual triggering

## Key Dirs
- `frontend/` — Next.js app
- `backend/` — FastAPI app
