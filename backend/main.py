"""
FastAPI application entry point.

Configures CORS, mounts API routes, and starts the server.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.config import setup_logging

# Initialize logging
setup_logging(level=logging.INFO)
logger = logging.getLogger("trading_bot")

# ── Create FastAPI app ───────────────────────────────────────────────────
app = FastAPI(
    title="AI Trading Bot — HMM Regime Analysis",
    description=(
        "Market regime detection using Hidden Markov Models with "
        "SMA crossover strategy parameter optimization."
    ),
    version="0.1.0",
)

# ── CORS — allow frontend dev server ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",    # Vite dev server
        "http://localhost:3000",    # Fallback
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routes ─────────────────────────────────────────────────────────
app.include_router(router)


@app.on_event("startup")
async def startup():
    """Application startup hook."""
    logger.info("=== AI Trading Bot API starting up ===")
    logger.info("Docs available at http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown():
    """Application shutdown hook."""
    logger.info("=== AI Trading Bot API shutting down ===")
