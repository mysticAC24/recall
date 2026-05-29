"""
Background indexing pipeline.

Orchestrates the full flow for an event:
1. List images in the Google Drive folder
2. Download each image (with concurrency limit)
3. Run face detection / embedding extraction
4. Store embeddings in the database
5. Track progress in the events table

All heavy lifting (Drive API, InsightFace) runs in a thread pool.
Progress is written to the ``events`` table so the frontend can poll.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session
from app.models import Event, FaceEmbedding, Photo
from app.services.drive import drive_service
from app.services.face import face_service

logger = logging.getLogger(__name__)


def _build_thumbnail_url(file_id: str) -> str:
    """Construct a Google Drive thumbnail URL."""
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"


def _build_image_url(file_id: str) -> str:
    """Construct a Google Drive full-image URL."""
    return f"https://drive.google.com/uc?export=view&id={file_id}"


async def _update_event_progress(
    event_id: uuid.UUID,
    *,
    status: Optional[str] = None,
    total_photos: Optional[int] = None,
    indexed_photos: Optional[int] = None,
) -> None:
    """Write indexing progress back to the events table.

    Only sets the fields that are not ``None``.
    """
    values: dict[str, Any] = {}
    if status is not None:
        values["status"] = status
    if total_photos is not None:
        values["total_photos"] = total_photos
    if indexed_photos is not None:
        values["indexed_photos"] = indexed_photos

    if not values:
        return

    async with async_session() as session:
        await session.execute(
            update(Event).where(Event.id == event_id).values(**values)
        )
        await session.commit()


async def _process_single_image(
    event_id: uuid.UUID,
    file_info: dict[str, str],
    semaphore: asyncio.Semaphore,
) -> bool:
    """Download one image, detect faces, and store results.

    Args:
        event_id: The parent event UUID.
        file_info: Dict with ``id`` and ``name`` keys from the Drive API.
        semaphore: Concurrency-limiting semaphore.

    Returns:
        ``True`` if the image was processed successfully, ``False`` otherwise.
    """
    file_id = file_info["id"]
    filename = file_info["name"]

    async with semaphore:
        try:
            logger.info("Processing image: %s (id=%s)", filename, file_id)

            # Download image (I/O-bound but uses sync google-api-client,
            # so run in threadpool)
            loop = asyncio.get_running_loop()
            image_bytes = await loop.run_in_executor(
                None, drive_service.download_image_bytes, file_id
            )
            logger.info("Downloaded %s — %d bytes", filename, len(image_bytes))

            # Detect faces (CPU-bound → threadpool)
            face_data = await loop.run_in_executor(
                None, face_service.get_embeddings_from_bytes, image_bytes
            )
            logger.info("Face detection complete for %s — %d face(s) found", filename, len(face_data))

            # Persist photo + embeddings
            thumbnail_url = _build_thumbnail_url(file_id)
            image_url = _build_image_url(file_id)

            async with async_session() as session:
                # Check if photo already exists (idempotent re-indexing)
                existing = await session.execute(
                    text("SELECT id FROM photos WHERE drive_file_id = :fid"),
                    {"fid": file_id},
                )
                row = existing.fetchone()

                if row is not None:
                    logger.debug("Photo %s already indexed — skipping", file_id)
                    return True

                photo = Photo(
                    event_id=event_id,
                    drive_file_id=file_id,
                    filename=filename,
                    thumbnail_url=thumbnail_url,
                    image_url=image_url,
                )
                session.add(photo)
                await session.flush()  # Get photo.id

                for face in face_data:
                    embedding_record = FaceEmbedding(
                        photo_id=photo.id,
                        embedding=face["embedding"],
                        bbox=face["bbox"],
                        det_score=face["det_score"],
                    )
                    session.add(embedding_record)

                await session.commit()

            logger.debug(
                "Indexed %s — %d face(s) detected", filename, len(face_data)
            )
            return True

        except Exception as exc:
            logger.error(
                "Failed to process image %s (%s): %s: %s",
                filename, file_id, type(exc).__name__, exc
            )
            return False


async def index_event(event_id: uuid.UUID, folder_id: str) -> None:
    """Run the full indexing pipeline for an event.

    This is designed to be launched with ``asyncio.create_task()`` so it
    runs in the background while the HTTP response is returned immediately.

    Args:
        event_id: The UUID of the event being indexed.
        folder_id: The Google Drive folder ID to scan.
    """
    settings = get_settings()

    try:
        await _update_event_progress(event_id, status="processing")

        # Step 1 — list images (sync Drive API → threadpool)
        loop = asyncio.get_running_loop()
        image_files = await loop.run_in_executor(
            None, drive_service.list_image_files, folder_id
        )

        total = len(image_files)
        await _update_event_progress(event_id, total_photos=total)
        logger.info("Event %s: found %d images to index", event_id, total)

        if total == 0:
            await _update_event_progress(event_id, status="completed")
            return

        # Step 2 — process images with concurrency limit
        semaphore = asyncio.Semaphore(settings.indexing_concurrency)
        indexed = 0
        failed = 0

        # Process in batches to update progress periodically
        batch_size = 10
        for i in range(0, total, batch_size):
            batch = image_files[i : i + batch_size]
            tasks = [
                _process_single_image(event_id, f, semaphore) for f in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if result is True:
                    indexed += 1
                else:
                    failed += 1
                    if isinstance(result, Exception):
                        logger.error("Unexpected error in batch: %s", result)

            await _update_event_progress(event_id, indexed_photos=indexed)
            logger.info(
                "Event %s: progress %d/%d (%d failed)", event_id, indexed, total, failed
            )

        # Step 3 — mark complete
        final_status = "completed" if indexed > 0 else "failed"
        await _update_event_progress(
            event_id, status=final_status, indexed_photos=indexed
        )
        logger.info(
            "Event %s indexing finished: %d/%d indexed, %d failed, status=%s",
            event_id,
            indexed,
            total,
            failed,
            final_status,
        )

    except Exception:
        logger.exception("Event %s indexing failed with unhandled error", event_id)
        await _update_event_progress(event_id, status="failed")
