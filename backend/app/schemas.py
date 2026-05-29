"""
Pydantic schemas for request / response validation.

Organised by domain:
- Event schemas  — creating, reading, and tracking events
- Search schemas — selfie upload and matched-face results
- Photo schemas  — individual photo responses
- Admin schemas  — authentication
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────────────
# Admin
# ──────────────────────────────────────────────────────────────────────

class AdminLogin(BaseModel):
    """Admin login request body."""
    password: str = Field(..., min_length=1, description="Admin password")


class AdminToken(BaseModel):
    """Successful admin login response."""
    authenticated: bool = True
    message: str = "Login successful"


# ──────────────────────────────────────────────────────────────────────
# Event
# ──────────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    """Request body to create a new event and start indexing."""
    name: str = Field(..., min_length=1, max_length=500, description="Human-readable event name")
    drive_folder_url: str = Field(
        ...,
        min_length=1,
        description="Google Drive folder URL (various formats accepted)",
    )


class EventResponse(BaseModel):
    """Full event representation returned to the client."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    drive_folder_id: str
    status: str
    total_photos: int
    indexed_photos: int
    created_at: datetime
    updated_at: datetime


class EventStatusResponse(BaseModel):
    """Lightweight status check for polling during indexing."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    total_photos: int
    indexed_photos: int
    failed_photos: int = 0
    progress_pct: float = Field(
        default=0.0, description="Indexing progress as a percentage (0-100)"
    )


# ──────────────────────────────────────────────────────────────────────
# Photo
# ──────────────────────────────────────────────────────────────────────

class PhotoResponse(BaseModel):
    """A single photo in API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    drive_file_id: str
    filename: str
    thumbnail_url: str | None = None
    image_url: str | None = None
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────
# Search
# ──────────────────────────────────────────────────────────────────────

class MatchedPhoto(BaseModel):
    """A photo that matched the selfie search."""
    photo_id: uuid.UUID
    similarity: float = Field(..., ge=0.0, le=1.0)
    drive_file_id: str
    thumbnail_url: str | None = None
    image_url: str | None = None
    filename: str


class SearchResponse(BaseModel):
    """Response from the selfie-search endpoint."""
    matches: list[MatchedPhoto]
    total: int
    event_id: uuid.UUID
    threshold: float


# ──────────────────────────────────────────────────────────────────────
# Generic
# ──────────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    detail: str
    success: bool = False
