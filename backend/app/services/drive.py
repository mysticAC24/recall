"""
Google Drive service – list images in a folder & download image bytes.

Uses a service account (JSON stored as a base64-encoded env var) so the
backend can access shared Drive folders without user OAuth.

Key capabilities:
- Parse various Google Drive folder URL formats to extract folder ID
- List all image files in a folder (handles pagination)
- Download image bytes for a given file ID
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.config import get_settings

logger = logging.getLogger(__name__)

# Google Drive API scopes (read-only)
_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Image MIME types we care about
_IMAGE_MIME_TYPES = (
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
)

# Regex patterns for extracting folder IDs from various Google Drive URL formats
_FOLDER_ID_PATTERNS = [
    # https://drive.google.com/drive/folders/<ID>?...
    re.compile(r"drive\.google\.com/drive/(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)"),
    # https://drive.google.com/open?id=<ID>
    re.compile(r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)"),
    # https://drive.google.com/folderview?id=<ID>
    re.compile(r"drive\.google\.com/folderview\?id=([a-zA-Z0-9_-]+)"),
]


def parse_folder_id(url_or_id: str) -> str:
    """Extract a Google Drive folder ID from a URL or return as-is if already an ID.

    Supports:
    - ``https://drive.google.com/drive/folders/<ID>``
    - ``https://drive.google.com/drive/u/0/folders/<ID>``
    - ``https://drive.google.com/open?id=<ID>``
    - ``https://drive.google.com/folderview?id=<ID>``
    - Raw folder ID strings

    Args:
        url_or_id: A Google Drive folder URL or plain folder ID.

    Returns:
        The extracted folder ID string.

    Raises:
        ValueError: If the input doesn't match any known format.
    """
    url_or_id = url_or_id.strip()

    # Try each pattern
    for pattern in _FOLDER_ID_PATTERNS:
        match = pattern.search(url_or_id)
        if match:
            return match.group(1)

    # If it looks like a raw ID (alphanumeric + hyphens/underscores, no spaces or slashes)
    if re.match(r"^[a-zA-Z0-9_-]+$", url_or_id) and len(url_or_id) > 10:
        return url_or_id

    raise ValueError(
        f"Could not extract a Google Drive folder ID from: {url_or_id!r}"
    )


class DriveService:
    """Wrapper around the Google Drive API v3.

    Initialised once at app startup; call :pymeth:`build_service` to
    authenticate and create the underlying API resource.
    """

    def __init__(self) -> None:
        self._service: Any | None = None

    def build_service(self) -> None:
        """Authenticate with the service account and build the API client."""
        settings = get_settings()
        info = settings.get_service_account_info()
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        logger.info("Google Drive service initialised")

    @property
    def service(self) -> Any:
        """Return the authenticated Drive API resource, raising if not built."""
        if self._service is None:
            raise RuntimeError(
                "DriveService not initialised – call build_service() first"
            )
        return self._service

    def _list_subfolders(self, folder_id: str) -> list[str]:
        """Return IDs of all immediate subfolders in a folder."""
        subfolder_ids: list[str] = []
        page_token: Optional[str] = None
        query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"

        while True:
            response = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token,
            ).execute()

            for f in response.get("files", []):
                logger.info("Found subfolder: %s (%s)", f["name"], f["id"])
                subfolder_ids.append(f["id"])

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return subfolder_ids

    def _list_images_in_folder(self, folder_id: str) -> list[dict[str, str]]:
        """List image files directly inside one folder (no recursion)."""
        files: list[dict[str, str]] = []
        page_token: Optional[str] = None
        mime_filter = " or ".join(f"mimeType='{mt}'" for mt in _IMAGE_MIME_TYPES)
        query = f"'{folder_id}' in parents and ({mime_filter}) and trashed=false"

        while True:
            response = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token,
            ).execute()
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return files

    def list_image_files(self, folder_id: str) -> list[dict[str, str]]:
        """Recursively list all image files in a folder and its subfolders.

        Handles photographers who organise shots into numbered sub-albums
        (e.g. folders 1/, 2/, 3/ inside the shared root).

        Args:
            folder_id: The root Google Drive folder ID to scan.

        Returns:
            A deduplicated list of dicts with keys ``id``, ``name``, ``mimeType``.
        """
        seen_ids: set[str] = set()
        all_files: list[dict[str, str]] = []

        # BFS over the folder tree (max depth 5 to avoid runaway recursion)
        queue: list[tuple[str, int]] = [(folder_id, 0)]
        max_depth = 5

        while queue:
            current_id, depth = queue.pop(0)

            # Collect images at this level
            images = self._list_images_in_folder(current_id)
            for img in images:
                if img["id"] not in seen_ids:
                    seen_ids.add(img["id"])
                    all_files.append(img)

            # Recurse into subfolders
            if depth < max_depth:
                subfolders = self._list_subfolders(current_id)
                for sf_id in subfolders:
                    queue.append((sf_id, depth + 1))

        logger.info(
            "Found %d unique image files across folder tree rooted at %s",
            len(all_files), folder_id,
        )
        return all_files

    def download_image_bytes(self, file_id: str) -> bytes:
        """Download the full image content for a Drive file.

        Tries ``get_media`` first (works for most files), then falls back to
        fetching via the file's ``webContentLink`` using the service account
        credentials, which handles edge cases like files flagged for abuse checks.

        Args:
            file_id: The Google Drive file ID.

        Returns:
            Raw image bytes.

        Raises:
            RuntimeError: If all download attempts fail.
        """
        last_exc: Exception | None = None

        # Attempt 1: standard get_media (fastest, works for most files)
        try:
            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True,
                acknowledgeAbuse=True,
            )
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            data = buffer.getvalue()
            if data:
                return data
        except Exception as exc:
            logger.warning("get_media failed for %s (%s: %s) — trying alt=media", file_id, type(exc).__name__, exc)
            last_exc = exc

        # Attempt 2: alt=media via requests using service-account auth token
        try:
            import google.auth.transport.requests as google_requests
            from google.oauth2.service_account import Credentials

            settings = get_settings()
            creds = Credentials.from_service_account_info(
                settings.get_service_account_info(),
                scopes=_SCOPES,
            )
            auth_req = google_requests.Request()
            creds.refresh(auth_req)

            import requests as req_lib
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true&acknowledgeAbuse=true"
            resp = req_lib.get(url, headers={"Authorization": f"Bearer {creds.token}"}, timeout=60)
            resp.raise_for_status()
            data = resp.content
            if data:
                logger.info("alt=media fallback succeeded for %s", file_id)
                return data
        except Exception as exc:
            logger.error("alt=media fallback also failed for %s (%s: %s)", file_id, type(exc).__name__, exc)
            last_exc = exc

        raise RuntimeError(f"Failed to download file {file_id}") from last_exc


# Module-level singleton
drive_service = DriveService()
