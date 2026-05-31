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

async def _resume_interrupted_indexing() -> None:
    """Re-launch indexing for events left in 'processing' by a restart.

    The indexer runs as an in-memory background task, so a redeploy or an
    OOM kill abandons any in-flight event (its status stays 'processing'
    forever). On startup we find those events and restart their indexing.
    Indexing is idempotent — photos already stored are skipped — so this
    resumes rather than redoes the work.
    """
    import asyncio

    from sqlalchemy import select

    from app.database import async_session
    from app.models import Event
    from app.services.indexer import index_event

    async with async_session() as session:
        result = await session.execute(
            select(Event).where(Event.status.in_(["processing", "pending"]))
        )
        stuck = result.scalars().all()

    if not stuck:
        return

    for event in stuck:
        logger.info(
            "↻ Resuming interrupted indexing for event %s (%s)",
            event.id, event.name,
        )
        asyncio.create_task(
            index_event(event.id, event.drive_folder_id),
            name=f"resume-index-{event.id}",
        )


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

    # Initialise heavy resources. A failure here is logged but does NOT
    # crash the app — login, health, and other lightweight endpoints stay
    # up. Indexing/search endpoints depend on these services and will
    # re-attempt initialisation (or surface a clear error) when called.

    # Initialise face detection model
    try:
        face_service.init_model()
        logger.info("✅ Face detection model loaded")
    except Exception:
        logger.exception(
            "❌ Failed to load face detection model — continuing without it. "
            "Login/health stay available; indexing & search will be degraded."
        )

    # Initialise Google Drive client
    try:
        drive_service.build_service()
        logger.info("✅ Google Drive service initialised")
    except Exception:
        logger.exception(
            "❌ Failed to initialise Google Drive service — continuing without it. "
            "Login/health stay available; indexing will be degraded."
        )

    # Resume any indexing that was interrupted by a restart/crash. The
    # background indexer runs in-memory, so a redeploy or OOM kill leaves
    # events stranded in "processing". Re-launching is safe and resumable:
    # already-indexed photos are skipped, so it picks up where it left off.
    try:
        await _resume_interrupted_indexing()
    except Exception:
        logger.exception("Failed while resuming interrupted indexing")

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
