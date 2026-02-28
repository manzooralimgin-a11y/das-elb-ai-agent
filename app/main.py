"""
Das ELB Hotel AI Email Agent — FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.database import init_db
from app.email.poller import start_scheduler, scheduler
from app.api.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting Das ELB AI Email Agent...")
    await init_db()
    logger.info("Database initialized.")
    start_scheduler()
    yield
    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Das ELB AI Email Agent",
    version="1.0.0",
    description=(
        "Multi-agent AI system for automatically drafting hotel email replies. "
        "Human review required before sending."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "model": settings.OPENAI_MODEL,
        "auto_send_enabled": settings.ENABLE_AUTO_SEND,
        "polling_interval_seconds": settings.POLL_INTERVAL_SECONDS,
    }
