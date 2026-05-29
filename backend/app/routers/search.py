"""
Search router — selfie-based face matching.

Endpoints:
- POST /search/{event_id}  — upload a selfie, find matching photos
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Event
from app.schemas import ErrorResponse, MatchedPhoto, SearchResponse
from app.services.face import face_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# Maximum selfie file size: 10 MB
_MAX_SELFIE_SIZE = 10 * 1024 * 1024


@router.post(
    "/{event_id}",
    response_model=SearchResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Search for photos matching a selfie",
)
async def search_by_selfie(
    event_id: uuid.UUID,
    selfie: UploadFile = File(..., description="Selfie image file"),
    threshold: float | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    """Upload a selfie to find matching photos in an event.

    Processing steps:
    1. Validate the event exists and is indexed.
    2. Read & validate the selfie image.
    3. Extract the largest face embedding (CPU, threadpool).
    4. Query the ``match_faces`` RPC function via raw SQL.
    5. Filter results to this event and return matches.

    Query params:
    - ``threshold`` — override the default similarity threshold.
    - ``limit`` — max number of matches to return (default 50).
    """
    # ── Validate event ──────────────────────────────────────────────
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    if event.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event is not fully indexed yet (status: {event.status}). "
            f"Please wait for indexing to complete.",
        )

    # ── Read & validate selfie ──────────────────────────────────────
    if selfie.content_type and not selfie.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an image",
        )

    image_bytes = await selfie.read()

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(image_bytes) > _MAX_SELFIE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selfie too large (max {_MAX_SELFIE_SIZE // (1024*1024)} MB)",
        )

    # ── Extract face embedding (CPU-bound → threadpool) ─────────────
    embedding = await run_in_threadpool(
        face_service.get_largest_face_embedding, image_bytes
    )

    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face detected in the uploaded selfie. "
            "Please upload a clear photo of your face.",
        )

    # ── Query matching faces ────────────────────────────────────────
    match_threshold = threshold if threshold is not None else settings.similarity_threshold

    # Use the match_faces RPC via raw SQL.
    # The RPC returns: photo_id, similarity, drive_file_id, thumbnail_url, image_url, filename
    query = text("""
        SELECT
            mf.photo_id,
            mf.similarity,
            mf.drive_file_id,
            mf.thumbnail_url,
            mf.image_url,
            mf.filename
        FROM match_faces(
            CAST(:query_embedding AS vector),
            :match_threshold,
            :match_count
        ) AS mf
        JOIN photos p ON p.id = mf.photo_id
        WHERE p.event_id = :event_id
        ORDER BY mf.similarity DESC
    """)

    # pgvector expects the embedding as a string like '[0.1, 0.2, ...]'
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    result = await db.execute(
        query,
        {
            "query_embedding": embedding_str,
            "match_threshold": match_threshold,
            "match_count": limit * 2,  # Fetch extra to account for event filtering
            "event_id": str(event_id),
        },
    )
    rows = result.fetchall()

    # Build response
    matches = [
        MatchedPhoto(
            photo_id=row.photo_id,
            similarity=round(float(row.similarity), 4),
            drive_file_id=row.drive_file_id,
            thumbnail_url=row.thumbnail_url,
            image_url=row.image_url,
            filename=row.filename,
        )
        for row in rows[:limit]
    ]

    logger.info(
        "Search in event %s: %d matches (threshold=%.2f)",
        event_id,
        len(matches),
        match_threshold,
    )

    return SearchResponse(
        matches=matches,
        total=len(matches),
        event_id=event_id,
        threshold=match_threshold,
    )
