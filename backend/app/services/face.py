"""
Face detection & embedding service using InsightFace.

- Model is initialised once at app startup (via lifespan).
- All inference runs in a thread pool (CPU-bound work).
- ctx_id=-1 forces CPU execution (no GPU on Render free tier).
- Uses CPUExecutionProvider for ONNX Runtime.

Public API:
- ``init_model()``   — load the InsightFace model (call once)
- ``get_embeddings_from_bytes(image_bytes)`` — detect faces → embeddings
- ``get_largest_face_embedding(image_bytes)`` — single embedding for selfie
"""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class FaceService:
    """Manages the InsightFace model and provides face-analysis helpers."""

    def __init__(self) -> None:
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        """Return the loaded FaceAnalysis model, or raise if not initialised."""
        if self._model is None:
            raise RuntimeError(
                "FaceService not initialised — call init_model() first"
            )
        return self._model

    @property
    def is_ready(self) -> bool:
        """Whether the model has been loaded."""
        return self._model is not None

    def init_model(self) -> None:
        """Load the InsightFace FaceAnalysis model.

        Must be called once at application startup (inside the lifespan
        context manager). Subsequent calls are no-ops.
        """
        if self._model is not None:
            logger.info("FaceService already initialised — skipping")
            return

        settings = get_settings()
        model_name = settings.insightface_model

        logger.info("Loading InsightFace model '%s' (CPU mode)…", model_name)

        # Import here to avoid slow import at module level
        from insightface.app import FaceAnalysis

        self._model = FaceAnalysis(
            name=model_name,
            providers=["CPUExecutionProvider"],
        )
        # ctx_id=-1 ⇒ CPU; det_size 640×640 is the default
        self._model.prepare(ctx_id=-1, det_size=(640, 640))
        logger.info("InsightFace model '%s' ready", model_name)

    def _decode_image(self, image_bytes: bytes) -> np.ndarray:
        """Decode raw image bytes into a BGR numpy array for OpenCV.

        Tries OpenCV first (fastest). Falls back to PIL for formats OpenCV
        can't handle (HEIC, some TIFFs, WebP variants, etc.).

        Args:
            image_bytes: Raw image file bytes (JPEG, PNG, HEIC, etc.).

        Returns:
            A numpy array in BGR format suitable for InsightFace.

        Raises:
            ValueError: If the image cannot be decoded by any method.
        """
        # Attempt 1: OpenCV (handles JPEG, PNG, WebP, BMP, standard TIFF)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            return img

        # Attempt 2: PIL (handles HEIC via pillow-heif if installed, plus
        # more TIFF variants, animated GIFs, and other edge cases)
        try:
            import io as _io
            from PIL import Image

            # Register HEIF/HEIC support if the plugin is installed
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except ImportError:
                pass

            pil_img = Image.open(_io.BytesIO(image_bytes)).convert("RGB")
            # PIL is RGB, OpenCV/InsightFace expect BGR
            img = np.array(pil_img)[:, :, ::-1].copy()
            logger.debug("PIL fallback decoder used for image (%d bytes)", len(image_bytes))
            return img
        except Exception as pil_exc:
            logger.warning("PIL fallback decoder failed: %s", pil_exc)

        raise ValueError(
            f"Could not decode image bytes ({len(image_bytes)} bytes) — "
            "format may be unsupported. HEIC support requires: pip install pillow-heif"
        )

    def get_faces(self, image_bytes: bytes) -> list[Any]:
        """Detect all faces in an image.

        Args:
            image_bytes: Raw image bytes.

        Returns:
            A list of InsightFace ``Face`` objects, each containing
            ``embedding``, ``bbox``, ``det_score``, etc.
        """
        img = self._decode_image(image_bytes)
        faces = self.model.get(img)
        return faces

    def get_embeddings_from_bytes(
        self, image_bytes: bytes
    ) -> list[dict[str, Any]]:
        """Detect faces and return structured embedding data.

        Used during **indexing** — we want *all* faces in every photo.

        Args:
            image_bytes: Raw image bytes.

        Returns:
            A list of dicts with keys:
            - ``embedding``: list[float] (512-d)
            - ``bbox``: dict with x1, y1, x2, y2
            - ``det_score``: float
        """
        faces = self.get_faces(image_bytes)
        results: list[dict[str, Any]] = []

        for face in faces:
            bbox = face.bbox.astype(float).tolist()
            results.append(
                {
                    "embedding": face.embedding.tolist(),
                    "bbox": {
                        "x1": bbox[0],
                        "y1": bbox[1],
                        "x2": bbox[2],
                        "y2": bbox[3],
                    },
                    "det_score": float(face.det_score),
                }
            )

        return results

    def get_largest_face_embedding(
        self, image_bytes: bytes
    ) -> list[float] | None:
        """Return the embedding for the **largest** detected face.

        Used during **search** — the user uploads a selfie and we want
        the dominant (biggest) face, which is most likely theirs.

        "Largest" is determined by bounding-box area.

        Args:
            image_bytes: Raw image bytes.

        Returns:
            A 512-d embedding as ``list[float]``, or ``None`` if no face
            was detected.
        """
        faces = self.get_faces(image_bytes)
        if not faces:
            return None

        # Pick the face with the largest bounding-box area
        def _bbox_area(face: Any) -> float:
            b = face.bbox
            return float((b[2] - b[0]) * (b[3] - b[1]))

        largest = max(faces, key=_bbox_area)
        return largest.embedding.tolist()


# Module-level singleton
face_service = FaceService()
