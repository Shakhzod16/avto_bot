"""Compatibility exports for legacy bot modules."""

from __future__ import annotations

import os
from pathlib import Path

from backend.app.core.config import (
    ADMIN_IDS,
    BOT_TOKEN,
    ENV_FILE,
    PROJECT_ROOT,
    WEBAPP_URL,
)


def _clean_env(value: str | None) -> str:
    return value.strip().strip('"').strip("'").strip() if value else ""


MAP_URL = _clean_env(os.getenv("MAP_URL")) or "https://maps.google.com/"

try:
    ANNUAL_INTEREST_RATE = float(_clean_env(os.getenv("ANNUAL_INTEREST_RATE")) or "24")
except ValueError as exc:
    raise RuntimeError(
        "Noto'g'ri ANNUAL_INTEREST_RATE qiymati / "
        "Invalid ANNUAL_INTEREST_RATE value"
    ) from exc

DATABASE_PATH = Path(
    _clean_env(os.getenv("DATABASE_PATH")) or str(PROJECT_ROOT / "bot.sqlite3")
)

__all__ = [
    "ADMIN_IDS",
    "ANNUAL_INTEREST_RATE",
    "BOT_TOKEN",
    "DATABASE_PATH",
    "ENV_FILE",
    "MAP_URL",
    "PROJECT_ROOT",
    "WEBAPP_URL",
]
