"""
Vercel Serverless Entry Point — Garcar Enterprise Platform
Gated by keyless-toolkit.yml (OIDC+HKDF+Ed25519+Merkle) before every deploy.
Uses absolute imports so Vercel's Python runtime resolves them without errors.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers.revenue import router as revenue_router

app = FastAPI(
    title="Garcar Enterprise Platform",
    description="Autonomous revenue infrastructure — Stripe billing, lead scoring, churn prediction. Keyless-verified.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(revenue_router)


@app.get("/")
async def root():
    return {
        "status": "live",
        "platform": "Garcar Enterprise",
        "version": "2.0.0",
        "security": "keyless-oidc-hkdf-ed25519-merkle",
        "revenue_endpoints": [
            "/revenue/checkout",
            "/revenue/webhook",
            "/revenue/dashboard",
            "/revenue/invoice",
            "/revenue/health",
        ],
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Garcar Enterprise Platform",
        "keyless_verified": True,
    }


handler = app
