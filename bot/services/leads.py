"""Leadlar uchun validatsiya va formatlash servislari."""

from __future__ import annotations

import re

LEAD_TYPE_LABELS = {
    "test_drive": "Test-drayv",
    "buy": "Sotib olish",
    "callback": "Qayta qo'ng'iroq",
}


def normalize_phone(value: str) -> str | None:
    """O'zbekiston telefon raqamini +998 formatiga aylantiradi."""
    digits = re.sub(r"\D", "", value)
    digits = digits.removeprefix("998")
    if len(digits) == 9:
        return "+998" + digits
    return None
