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
import gc
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

# Global indexing lock: ensures only ONE event indexes at a time across the
# whole process. Without this, auto-resume plus a freshly created event could
# run multiple heavy face-detection jobs at once and OOM-kill the container.
_index_lock = asyncio.Lock()


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
    already_indexed: set[str],
) -> bool:
    """Download one image, detect faces, and store results.

    Args:
        event_id: The parent event UUID.
        file_info: Dict with ``id`` and ``name`` keys from the Drive API.
        semaphore: Concurrency-limiting semaphore.
        already_indexed: Set of ``drive_file_id`` values already indexed for
            this event (loaded once per run) — used for instant in-memory
            skipping on resume.

    Returns:
        ``True`` if the image was processed successfully, ``False`` otherwise.
    """
    file_id = file_info["id"]
    filename = file_info["name"]

    async with semaphore:
        try:
            logger.info("Processing image: %s (id=%s)", filename, file_id)

            # Fast path: skip photos already indexed BEFORE the expensive
            # download + face detection. The set of already-indexed file IDs
            # is loaded ONCE per run (see index_event), so resume-after-restart
            # skips completed photos in-memory instantly — instead of one slow
            # DB round-trip per photo, which previously made every restart
            # spend minutes re-skipping and never advance past where it was.
            if file_id in already_indexed:
                return True

            # Download image (I/O-bound but uses sync google-api-client,
            # so run in threadpool). Hard timeout so one stalled download
            # can't freeze the whole pipeline — the primary get_media path
            # has no timeout of its own.
            loop = asyncio.get_running_loop()
            image_bytes = await asyncio.wait_for(
                loop.run_in_executor(
                    None, drive_service.download_image_bytes, file_id
                ),
                timeout=90,
            )
            logger.info("Downloaded %s — %d bytes", filename, len(image_bytes))

            # Detect faces (CPU-bound → threadpool), also time-bounded.
            face_data = await asyncio.wait_for(
                loop.run_in_executor(
                    None, face_service.get_embeddings_from_bytes, image_bytes
                ),
                timeout=120,
            )
            logger.info("Face detection complete for %s — %d face(s) found", filename, len(face_data))

            # Release the decoded image buffer promptly — holding hundreds of
            # multi-MB buffers across a run is what grows RSS until OOM.
            del image_bytes

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

    # Hold the global lock for the whole run so indexing jobs queue instead
    # of stacking — only one event is ever processed at a time (memory safety).
    await _index_lock.acquire()
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

        # Load already-indexed file IDs for this event in ONE query so resume
        # skips completed photos in-memory (instant) instead of a slow
        # per-photo DB lookup. Re-checking hundreds of done photos one query
        # at a time is what made restarts appear "stuck" — they spent their
        # whole uptime re-skipping and never reached the unindexed ones.
        async with async_session() as session:
            rows = await session.execute(
                text("SELECT drive_file_id FROM photos WHERE event_id = :eid"),
                {"eid": str(event_id)},
            )
            already_indexed: set[str] = {row[0] for row in rows.fetchall()}
        logger.info(
            "Event %s: %d/%d photos already indexed — skipping those on resume",
            event_id, len(already_indexed), total,
        )

        # Step 2 — process images with concurrency limit
        semaphore = asyncio.Semaphore(settings.indexing_concurrency)
        indexed = 0
        failed = 0

        # Process in small batches so progress is written to the DB often —
        # the bar advances in near-real-time and a crash loses at most a few
        # photos of *displayed* progress (each photo is committed individually
        # regardless, so no real work is redone on resume).
        batch_size = 5
        for i in range(0, total, batch_size):
            batch = image_files[i : i + batch_size]
            tasks = [
                _process_single_image(event_id, f, semaphore, already_indexed)
                for f in batch
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

            # Reclaim memory between batches so RSS stays flat across a long
            # run instead of creeping up until the container is OOM-killed.
            gc.collect()
            # glibc holds freed heap by default; hand it back to the OS so RSS
            # actually drops (otherwise it ratchets up toward the OOM limit).
            try:
                import ctypes

                ctypes.CDLL("libc.so.6").malloc_trim(0)
            except Exception:
                pass

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
    finally:
        _index_lock.release()
