"""Safe image storage for broadcast campaigns."""

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from backend.app.core.config import (
    ALLOWED_IMAGE_FORMATS,
    MAX_IMAGE_SIZE_BYTES,
    MEDIA_DIR,
)


class BroadcastImageError(ValueError):
    """Raised when an optional broadcast image is invalid."""


def _write_broadcast_image(data: bytes, destination: Path) -> Path:
    try:
        with Image.open(BytesIO(data)) as original:
            image_format = (original.format or "").upper()
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise BroadcastImageError("Faqat JPEG, PNG yoki WebP qabul qilinadi")
            original.verify()
        with Image.open(BytesIO(data)) as original:
            image = original.convert("RGB")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, format="JPEG", quality=88, optimize=True)
    except BroadcastImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise BroadcastImageError("Rasm fayli buzilgan yoki o'qib bo'lmadi") from exc
    return destination


async def save_broadcast_image(upload: UploadFile) -> Path:
    """Validate an image upload and store a normalized JPEG for Telegram."""
    data = await upload.read(MAX_IMAGE_SIZE_BYTES + 1)
    if not data:
        raise BroadcastImageError("Rasm fayli bo'sh")
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise BroadcastImageError("Rasm hajmi 5 MB dan oshmasligi kerak")

    expected_formats = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }
    expected = expected_formats.get(upload.content_type or "")
    if expected is None:
        raise BroadcastImageError("Faqat JPEG, PNG yoki WebP formatlari qabul qilinadi")
    try:
        with Image.open(BytesIO(data)) as image:
            actual = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise BroadcastImageError("Rasm fayli buzilgan yoki o'qib bo'lmadi") from exc
    if actual != expected:
        raise BroadcastImageError("Fayl mazmuni ko'rsatilgan rasm formatiga mos emas")

    target = MEDIA_DIR / "broadcasts" / f"{uuid4().hex}.jpg"
    return await asyncio.to_thread(_write_broadcast_image, data, target)
