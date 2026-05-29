"""
Admin router — event management and authentication.

Endpoints:
- POST /admin/login           — verify admin password
- POST /admin/events          — create event & start indexing
- GET  /admin/events          — list all events
- GET  /admin/events/{id}     — get event details with status
- DELETE /admin/events/{id}   — delete event and all associated data
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Event, FaceEmbedding, Photo
from app.schemas import (
    AdminLogin,
    AdminToken,
    ErrorResponse,
    EventCreate,
    EventResponse,
    EventStatusResponse,
    MessageResponse,
)
from app.services.drive import drive_service, parse_folder_id
from app.services.indexer import index_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ──────────────────────────────────────────────────────────────────────
# Auth dependency
# ──────────────────────────────────────────────────────────────────────

async def verify_admin(
    x_admin_password: str = Header(..., alias="X-Admin-Password"),
    settings: Settings = Depends(get_settings),
) -> bool:
    """Dependency that checks the admin password from a request header.

    Raises:
        HTTPException 401: If the password is missing or incorrect.
    """
    if x_admin_password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password",
        )
    return True


# ──────────────────────────────────────────────────────────────────────
# POST /admin/login
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=AdminToken,
    responses={401: {"model": ErrorResponse}},
    summary="Verify admin password",
)
async def admin_login(
    body: AdminLogin,
    settings: Settings = Depends(get_settings),
) -> AdminToken:
    """Validate the admin password.

    This is a simple check — no tokens or sessions are issued.
    The frontend stores the password and sends it with every
    subsequent request in the ``X-Admin-Password`` header.
    """
    if body.password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password",
        )
    return AdminToken()


# ──────────────────────────────────────────────────────────────────────
# POST /admin/events
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Create event and start background indexing",
)
async def create_event(
    body: EventCreate,
    _admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """Create a new event from a Google Drive folder URL.

    1. Parse the folder ID from the URL.
    2. Insert an event row with ``status='pending'``.
    3. Launch background indexing via ``asyncio.create_task``.
    4. Return the event immediately (client polls for progress).
    """
    # Parse folder ID
    try:
        folder_id = parse_folder_id(body.drive_folder_url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Create event record
    event = Event(
        name=body.name,
        drive_folder_id=folder_id,
        status="pending",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    logger.info("Created event %s (%s) — starting indexing", event.id, event.name)

    # Launch background indexing
    asyncio.create_task(
        index_event(event.id, folder_id),
        name=f"index-{event.id}",
    )

    return EventResponse.model_validate(event)


# ──────────────────────────────────────────────────────────────────────
# GET /admin/events
# ──────────────────────────────────────────────────────────────────────

@router.get(
    "/events",
    response_model=list[EventResponse],
    responses={401: {"model": ErrorResponse}},
    summary="List all events",
)
async def list_events(
    _admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> list[EventResponse]:
    """Return all events ordered by creation date (newest first)."""
    result = await db.execute(
        select(Event).order_by(Event.created_at.desc())
    )
    events = result.scalars().all()
    return [EventResponse.model_validate(e) for e in events]


# ──────────────────────────────────────────────────────────────────────
# GET /admin/events/{event_id}
# ──────────────────────────────────────────────────────────────────────

@router.get(
    "/events/{event_id}",
    response_model=EventStatusResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Get event status / progress",
)
async def get_event_status(
    event_id: uuid.UUID,
    _admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> EventStatusResponse:
    """Return the current indexing status and progress for an event."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    progress_pct = 0.0
    if event.total_photos > 0:
        progress_pct = round(
            (event.indexed_photos / event.total_photos) * 100, 1
        )

    failed_photos = max(0, event.total_photos - event.indexed_photos) if event.status in ("completed", "failed") else 0

    return EventStatusResponse(
        id=event.id,
        status=event.status,
        total_photos=event.total_photos,
        indexed_photos=event.indexed_photos,
        failed_photos=failed_photos,
        progress_pct=progress_pct,
    )


# ──────────────────────────────────────────────────────────────────────
# POST /admin/events/{event_id}/cancel
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/events/{event_id}/cancel",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Cancel a processing event",
)
async def cancel_event(
    event_id: uuid.UUID,
    _admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Mark a processing event as cancelled (sets status to 'failed').

    The background task may still be running but its progress updates
    become no-ops once the status is overwritten.
    """
    from sqlalchemy import update as sa_update

    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

    await db.execute(
        sa_update(Event).where(Event.id == event_id).values(status="failed")
    )
    await db.commit()
    logger.info("Cancelled event %s (%s)", event_id, event.name)
    return MessageResponse(message=f"Event '{event.name}' cancelled")


# ──────────────────────────────────────────────────────────────────────
# POST /admin/events/{event_id}/reset
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/events/{event_id}/reset",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
    summary="Reset a stuck or failed event and re-run indexing",
)
async def reset_event(
    event_id: uuid.UUID,
    _admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Reset a stuck processing or failed event and restart indexing from scratch.

    Clears existing photo/embedding data for the event so it can be re-indexed cleanly.
    """
    from sqlalchemy import delete as sa_delete
    from app.models import FaceEmbedding, Photo

    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

    # Clear existing data so re-indexing starts clean
    photo_result = await db.execute(select(Photo.id).where(Photo.event_id == event_id))
    photo_ids = [row[0] for row in photo_result.fetchall()]
    if photo_ids:
        await db.execute(sa_delete(FaceEmbedding).where(FaceEmbedding.photo_id.in_(photo_ids)))
    await db.execute(sa_delete(Photo).where(Photo.event_id == event_id))

    # Reset event counters
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(Event).where(Event.id == event_id).values(
            status="pending", total_photos=0, indexed_photos=0
        )
    )
    await db.commit()

    # Re-launch indexing
    asyncio.create_task(
        index_event(event_id, event.drive_folder_id),
        name=f"index-{event_id}",
    )

    logger.info("Reset and restarted indexing for event %s (%s)", event_id, event.name)
    return MessageResponse(message=f"Event '{event.name}' reset and indexing restarted")


# ──────────────────────────────────────────────────────────────────────
# DELETE /admin/events/{event_id}
# ──────────────────────────────────────────────────────────────────────

@router.delete(
    "/events/{event_id}",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Delete an event and all associated data",
)
async def delete_event(
    event_id: uuid.UUID,
    _admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete an event, its photos, and all face embeddings (cascade).

    Uses explicit deletes for clarity, though ON DELETE CASCADE would
    also handle the child rows.
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    # Get photo IDs for this event (needed for face_embeddings cleanup)
    photo_result = await db.execute(
        select(Photo.id).where(Photo.event_id == event_id)
    )
    photo_ids = [row[0] for row in photo_result.fetchall()]

    # Delete face embeddings for these photos
    if photo_ids:
        await db.execute(
            delete(FaceEmbedding).where(FaceEmbedding.photo_id.in_(photo_ids))
        )

    # Delete photos
    await db.execute(delete(Photo).where(Photo.event_id == event_id))

    # Delete event
    await db.execute(delete(Event).where(Event.id == event_id))
    await db.commit()

    logger.info("Deleted event %s (%s)", event_id, event.name)
    return MessageResponse(message=f"Event '{event.name}' deleted successfully")
