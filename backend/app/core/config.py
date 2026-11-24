"""Backend configuration loaded from the project-root .env file."""

from __future__ import annotations

import os
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE, override=False)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{(PROJECT_ROOT / 'backend' / 'app.db').as_posix()}",
)
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip('"').strip("'")
if BOT_TOKEN:
    BOT_TOKEN = BOT_TOKEN.strip()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip().strip('"').strip("'")
JWT_ALGORITHM = "HS256"
CUSTOMER_TOKEN_MINUTES = 15
ADMIN_ACCESS_TOKEN_MINUTES = 15
ADMIN_REFRESH_TOKEN_DAYS = 7
TELEGRAM_AUTH_MAX_AGE_SECONDS = 24 * 60 * 60
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def _parse_admin_ids(value: str) -> tuple[int, ...]:
    ids = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError as exc:
            raise RuntimeError(f"ADMIN_IDS noto'g'ri: {item!r}") from exc
    return tuple(dict.fromkeys(ids))


ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
CORS_ORIGINS = tuple(
    value.strip()
    for value in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174",
    ).split(",")
    if value.strip()
)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() == "true"
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
BOT_MODE = os.getenv("BOT_MODE", "polling").strip().lower()
API_BIND_ADDRESS = os.getenv("API_BIND_ADDRESS", "127.0.0.1").strip() or "127.0.0.1"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
if not WEBHOOK_PATH.startswith("/") or "?" in WEBHOOK_PATH:
    raise RuntimeError(
        "WEBHOOK_PATH / bilan boshlanishi va query string bo'lmasligi kerak."
    )
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(PROJECT_ROOT / "media")))
if not MEDIA_DIR.is_absolute():
    MEDIA_DIR = PROJECT_ROOT / MEDIA_DIR
CAR_MEDIA_DIR = MEDIA_DIR / "cars"
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
LOG_DIR = Path(os.getenv("LOG_DIR", str(PROJECT_ROOT / "logs")))
if not LOG_DIR.is_absolute():
    LOG_DIR = PROJECT_ROOT / LOG_DIR
LEAD_RATE_LIMIT = 3
LEAD_RATE_WINDOW_SECONDS = 60 * 60
MAX_REQUEST_SIZE_BYTES = 6 * 1024 * 1024
MAX_MULTIPART_REQUEST_SIZE_BYTES = 51 * 1024 * 1024
WRITE_RATE_LIMIT = 60
WRITE_RATE_WINDOW_SECONDS = 60


def webapp_url_error(url: str) -> str | None:
    """Return a user-facing configuration problem for a Telegram Mini App URL."""
    if not url.lower().startswith("https://"):
        return "WEBAPP_URL ochiq HTTPS manzil bo'lishi kerak."

    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        return "WEBAPP_URL yaroqli, to'liq HTTPS havolasi bo'lishi kerak."
    if any(character.isspace() for character in url):
        return "WEBAPP_URL bo'sh joylarsiz yaroqli HTTPS havolasi bo'lishi kerak."
    if parsed.username is not None or parsed.password is not None:
        return "WEBAPP_URL login yoki parol saqlamasligi kerak."
    hostname = parsed.hostname
    if not hostname:
        return "WEBAPP_URL to'liq domen nomiga ega ochiq HTTPS manzil bo'lishi kerak."

    hostname = hostname.lower()
    try:
        ip = ip_address(hostname)
    except ValueError:
        ip = None
    if hostname == "localhost" or hostname.endswith(".localhost") or (
        ip is not None and ip.is_loopback
    ):
        return (
            "WEBAPP_URL ommaviy HTTPS domeni bo'lishi kerak; "
            "localhost va loopback manzillar Telegram'da ishlamaydi."
        )
    if ip is None:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            return "WEBAPP_URL yaroqli, ommaviy domen nomi bo'lishi kerak."
        labels = ascii_hostname.rstrip(".").split(".")
        if len(ascii_hostname) > 253 or len(labels) < 2 or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not label.replace("-", "").isalnum()
            for label in labels
        ):
            return "WEBAPP_URL yaroqli, ommaviy domen nomi bo'lishi kerak."
    return None
