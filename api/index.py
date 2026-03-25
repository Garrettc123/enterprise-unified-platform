"""
Vercel Serverless Entry Point — Garcar Enterprise Platform
Mounts the full revenue router as an ASGI app.
Uses absolute imports so Vercel's build resolves them without relative-import errors.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers.revenue import router as revenue_router

app = FastAPI(
    title="Garcar Enterprise Platform",
    description="Autonomous revenue infrastructure — Stripe billing, lead scoring, churn prediction",
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
    return {"status": "healthy", "service": "Garcar Enterprise Platform"}


handler = app
