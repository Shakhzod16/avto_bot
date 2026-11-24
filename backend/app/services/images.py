"""Validated car image processing and WebP derivative generation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from backend.app.core.config import (
    ALLOWED_IMAGE_FORMATS,
    CAR_MEDIA_DIR,
    MAX_IMAGE_SIZE_BYTES,
)

MIME_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class ImageUploadError(ValueError):
    """Raised when an uploaded image is invalid or too large."""


@dataclass(frozen=True)
class StoredCarImage:
    """Relative paths for generated display and thumbnail images."""

    path: str
    thumbnail_path: str


def _process_image(data: bytes, image_id: str) -> StoredCarImage:
    CAR_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(BytesIO(data)) as original:
            image_format = (original.format or "").upper()
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ImageUploadError("Faqat JPEG, PNG yoki WebP qabul qilinadi")
            original.verify()

        with Image.open(BytesIO(data)) as original:
            image = original.convert("RGBA" if "A" in original.getbands() else "RGB")
            image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            large_path = CAR_MEDIA_DIR / f"{image_id}.webp"
            image.save(large_path, format="WEBP", quality=86, method=6)

            thumbnail = image.copy()
            thumbnail.thumbnail((480, 480), Image.Resampling.LANCZOS)
            thumb_path = CAR_MEDIA_DIR / f"{image_id}_thumb.webp"
            thumbnail.save(thumb_path, format="WEBP", quality=82, method=6)
    except ImageUploadError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageUploadError("Rasm fayli buzilgan yoki o'qib bo'lmadi") from exc

    return StoredCarImage(
        path=f"media/cars/{large_path.name}",
        thumbnail_path=f"media/cars/{thumb_path.name}",
    )


async def save_car_image(upload: UploadFile) -> StoredCarImage:
    """Validate an upload and create WebP display and thumbnail images."""
    expected_format = MIME_FORMATS.get(upload.content_type or "")
    if expected_format is None:
        raise ImageUploadError("Faqat JPEG, PNG yoki WebP formatlari qabul qilinadi")

    data = await upload.read(MAX_IMAGE_SIZE_BYTES + 1)
    if not data:
        raise ImageUploadError("Rasm fayli bo'sh")
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise ImageUploadError("Rasm hajmi 5 MB dan oshmasligi kerak")

    image_id = uuid4().hex

    try:
        with Image.open(BytesIO(data)) as image:
            actual_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageUploadError("Rasm fayli buzilgan yoki o'qib bo'lmadi") from exc

    if actual_format != expected_format:
        raise ImageUploadError("Fayl mazmuni ko'rsatilgan rasm formatiga mos emas")

    return await asyncio.to_thread(_process_image, data, image_id)
