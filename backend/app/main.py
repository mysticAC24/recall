"""
Recall — FastAPI application entry point.

Responsibilities:
- Configure logging
- Initialise services (InsightFace, Google Drive) at startup via lifespan
- Mount routers
- Set up CORS middleware
- Provide a health-check endpoint
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, photos, search
from app.services.drive import drive_service
from app.services.face import face_service

# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialise heavy resources once.

    Startup:
    - Load InsightFace model (can take 10-30s on first run while
      downloading weights).
    - Build the Google Drive API client.

    Shutdown:
    - Nothing special needed (GC handles cleanup).
    """
    logger.info("🚀 Recall backend starting up…")

    # Initialise face detection model
    try:
        face_service.init_model()
        logger.info("✅ Face detection model loaded")
    except Exception:
        logger.exception("❌ Failed to load face detection model")
        raise

    # Initialise Google Drive client
    try:
        drive_service.build_service()
        logger.info("✅ Google Drive service initialised")
    except Exception:
        logger.exception("❌ Failed to initialise Google Drive service")
        raise

    logger.info("🟢 Recall backend ready")
    yield  # ← app is running

    logger.info("🔴 Recall backend shutting down…")


# ──────────────────────────────────────────────────────────────────────
# App factory
# ──────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Recall API",
        description=(
            "AI-powered batch photo finder. Upload a selfie to find all "
            "photos of yourself in an event's Google Drive folder."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────
    app.include_router(admin.router)
    app.include_router(search.router)
    app.include_router(photos.router)

    # ── Health check ──────────────────────────────────────────────
    @app.get("/health", tags=["system"], summary="Health check")
    async def health_check() -> dict[str, str]:
        """Simple liveness probe for load balancers and monitoring."""
        return {
            "status": "healthy",
            "service": "recall-api",
            "face_model_ready": str(face_service.is_ready),
        }

    return app


# Create the app instance (used by uvicorn: ``uvicorn app.main:app``)
app = create_app()
