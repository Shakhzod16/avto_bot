"""Request limits and security headers for the API."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse

from backend.app.core.config import (
    MAX_MULTIPART_REQUEST_SIZE_BYTES,
    MAX_REQUEST_SIZE_BYTES,
    WRITE_RATE_LIMIT,
    WRITE_RATE_WINDOW_SECONDS,
)


class SecurityHeadersMiddleware:
    """Add browser-facing security headers to every response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        (
                            b"permissions-policy",
                            b"camera=(), microphone=(), geolocation=()",
                        ),
                        (
                            b"strict-transport-security",
                            b"max-age=31536000; includeSubDomains",
                        ),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestSizeLimitMiddleware:
    """Reject requests whose streamed body exceeds the configured limit."""

    def __init__(self, app, max_bytes: int = MAX_REQUEST_SIZE_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        multipart_endpoint = path == "/api/v1/admin/broadcast" or (
            path.startswith("/api/v1/admin/cars/") and path.endswith("/images")
        )
        max_bytes = (
            MAX_MULTIPART_REQUEST_SIZE_BYTES if multipart_endpoint else self.max_bytes
        )
        content_length = next(
            (
                value
                for key, value in scope.get("headers", [])
                if key.lower() == b"content-length"
            ),
            None,
        )
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    await self._too_large(scope, receive, send)
                    return
            except ValueError:
                pass

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > max_bytes:
                await self._too_large(scope, receive, send)
                return
            more_body = message.get("more_body", False)

        sent = False

        async def replay_body():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _too_large(scope, receive, send):
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request_too_large",
                    "message": "So'rov hajmi ruxsat etilganidan katta",
                }
            },
        )
        await response(scope, receive, send)


class WriteRateLimitMiddleware:
    """Apply a per-IP sliding-window limit to public API write requests."""

    def __init__(
        self,
        app,
        limit: int = WRITE_RATE_LIMIT,
        window_seconds: int = WRITE_RATE_WINDOW_SECONDS,
    ):
        self.app = app
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}
            or not scope.get("path", "").startswith("/api/v1/")
        ):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        key = client[0] if client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "rate_limited",
                            "message": "Juda ko'p so'rov yuborildi",
                        }
                    },
                    headers={"Retry-After": str(self.window_seconds)},
                )
                await response(scope, receive, send)
                return
            events.append(now)
        await self.app(scope, receive, send)
