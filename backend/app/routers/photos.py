"""
Photos router — public photo retrieval endpoints.

Endpoints:
- GET /photos/event/{event_id}      — list all photos for an event
- GET /photos/stats                 — get public stats
- GET /photos/{photo_id}            — get a single photo's details
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Event, Photo
from app.schemas import ErrorResponse, PhotoResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/photos", tags=["photos"])


@router.get(
    "/event/{event_id}",
    response_model=list[PhotoResponse],
    responses={404: {"model": ErrorResponse}},
    summary="List photos for an event",
)
async def list_event_photos(
    event_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Photos per page"),
    db: AsyncSession = Depends(get_db),
) -> list[PhotoResponse]:
    """Return paginated photos for a given event.

    Photos are ordered by filename. This endpoint is public (no admin
    auth required) so the search results page can load photo details.
    """
    # Verify event exists
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    # Paginated query
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Photo)
        .where(Photo.event_id == event_id)
        .order_by(Photo.filename)
        .offset(offset)
        .limit(page_size)
    )
    photos = result.scalars().all()
    return [PhotoResponse.model_validate(p) for p in photos]


@router.get(
    "/stats",
    summary="Get public stats for the landing page",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return aggregate stats: total photos indexed, total faces detected,
    and the latest event name/status. Public endpoint (no auth)."""
    # Get the latest event
    result = await db.execute(
        select(Event)
        .where(Event.status == "completed")
        .order_by(Event.created_at.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()

    if event is None:
        return {
            "total_photos": 0,
            "total_faces": 0,
            "event_name": None,
            "event_id": None,
            "status": None,
        }

    # Count faces for this event
    from app.models import FaceEmbedding
    face_count_result = await db.execute(
        select(func.count(FaceEmbedding.id))
        .join(Photo, FaceEmbedding.photo_id == Photo.id)
        .where(Photo.event_id == event.id)
    )
    total_faces = face_count_result.scalar() or 0

    return {
        "total_photos": event.indexed_photos,
        "total_faces": total_faces,
        "event_name": event.name,
        "event_id": str(event.id),
        "status": event.status,
    }


@router.get(
    "/{photo_id}",
    response_model=PhotoResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single photo",
)
async def get_photo(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    """Return details for a single photo by its UUID."""
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()

    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Photo {photo_id} not found",
        )

    return PhotoResponse.model_validate(photo)
