"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from backend.app import models as _models  # noqa: F401
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.customer import router as customer_router
from backend.app.api.v1.routes import router as public_router
from backend.app.bot.runtime import start_telegram_bot, stop_telegram_bot
from backend.app.core.config import (
    BOT_MODE,
    CAR_MEDIA_DIR,
    CORS_ORIGINS,
    JWT_SECRET_KEY,
    PROJECT_ROOT,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
)
from backend.app.core.logging_config import configure_logging
from backend.app.core.middleware import (
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    WriteRateLimitMiddleware,
)
from backend.app.db.session import engine

configure_logging()
logger = logging.getLogger(__name__)
WEBAPP_DIST = PROJECT_ROOT / "frontend" / "webapp" / "dist"
ADMIN_DIST = PROJECT_ROOT / "frontend" / "admin" / "dist"


class MiniAppStaticFiles(StaticFiles):
    """Serve the Vite build and fall back to its entrypoint for client routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not Path(path).suffix:
                return await super().get_response("index.html", scope)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify database readiness and run managed background tasks."""
    configure_logging()
    try:
        if len(JWT_SECRET_KEY.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET_KEY kamida 32 bayt bo'lishi kerak")
        await initialize_database()
        await start_telegram_bot(app)
        yield
    finally:
        broadcast_tasks = tuple(getattr(app.state, "broadcast_tasks", ()))
        for task in broadcast_tasks:
            task.cancel()
        if broadcast_tasks:
            await asyncio.gather(*broadcast_tasks, return_exceptions=True)
        try:
            await stop_telegram_bot(app)
        finally:
            await engine.dispose()


app = FastAPI(
    title="Buxara Avto Magnat API",
    version="1.0.0",
    description="Avtomobillar va mijozlar uchun REST API",
    lifespan=lifespan,
)

app.add_middleware(WriteRateLimitMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(public_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(customer_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


async def telegram_webhook(request: Request) -> JSONResponse:
    """Validate and dispatch Telegram webhook updates in production mode."""
    if BOT_MODE != "webhook":
        raise StarletteHTTPException(
            status_code=404, detail="Webhook rejimi yoqilmagan"
        )
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(supplied_secret, WEBHOOK_SECRET):
        raise StarletteHTTPException(status_code=403, detail="Webhook imzosi noto'g'ri")
    try:
        update_data = await request.json()
        update = Update.model_validate(
            update_data, context={"bot": request.app.state.telegram_bot}
        )
    except (ValueError, ValidationError) as exc:
        raise StarletteHTTPException(
            status_code=400, detail="Telegram update formati noto'g'ri"
        ) from exc
    await request.app.state.telegram_dispatcher.feed_update(
        request.app.state.telegram_bot,
        update,
    )
    return JSONResponse(content={"ok": True})


app.add_api_route(
    WEBHOOK_PATH, telegram_webhook, methods=["POST"], include_in_schema=False
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Return HTTP errors in one predictable JSON envelope."""
    del request
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"http_{exc.status_code}",
                "message": message,
            }
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return validation errors without exposing submitted values."""
    del request
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Kiritilgan ma'lumotlar noto'g'ri",
                "details": [
                    {
                        "field": ".".join(str(item) for item in error["loc"]),
                        "message": error["msg"],
                    }
                    for error in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Log unexpected failures and return a non-sensitive error."""
    logger.exception(
        "So'rovni bajarishda kutilmagan xatolik: %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Ichki server xatoligi",
            }
        },
    )


@app.get("/health", tags=["health"], response_model=None)
async def health() -> dict[str, str] | JSONResponse:
    """Report process and database readiness."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health tekshiruvida ma'lumotlar bazasi ulanmagan")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unavailable"},
        )
    return {"status": "ok", "database": "ok"}


CAR_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media/cars", StaticFiles(directory=CAR_MEDIA_DIR), name="car-media")
if WEBAPP_DIST.is_dir():
    app.mount(
        "/app",
        MiniAppStaticFiles(directory=WEBAPP_DIST, html=True),
        name="customer-mini-app",
    )
if ADMIN_DIST.is_dir():
    app.mount(
        "/admin",
        MiniAppStaticFiles(directory=ADMIN_DIST, html=True),
        name="admin-panel",
    )


async def initialize_database(database_engine: AsyncEngine = engine) -> None:
    """Fail startup clearly when migrations have not been applied."""
    try:
        async with database_engine.connect() as connection:
            await connection.execute(text("SELECT id FROM cars LIMIT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Ma'lumotlar bazasi tayyor emas. Avval `python -m alembic upgrade head` buyrug'ini bajaring."
        ) from exc
