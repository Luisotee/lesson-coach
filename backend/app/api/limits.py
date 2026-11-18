"""Request limits: an in-memory rate limit per client IP, and a body-size cap.

Both are in memory and per process, which fits one small container. Nothing about the
client is stored beyond request times, kept for one minute.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

WINDOW_S = 60.0
MAX_CLIENTS = 10_000

JSON_BODY_LIMIT = 64 * 1024
UPLOAD_BODY_LIMIT = 6 * 1024 * 1024
UPLOAD_PATHS = ("/api/transcribe",)


class RateLimiter:
    """A sliding window of request times per (bucket, client)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._clock = clock

    def check(self, bucket: str, client: str, per_minute: int) -> float | None:
        """None when allowed (and counted); else the seconds until the next request fits."""
        now = self._clock()
        key = (bucket, client)
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= MAX_CLIENTS:
                self._prune(now)
            hits = self._hits[key] = deque()
        while hits and now - hits[0] >= WINDOW_S:
            hits.popleft()
        if len(hits) >= per_minute:
            return WINDOW_S - (now - hits[0])
        hits.append(now)
        return None

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= WINDOW_S]:
            del self._hits[key]
        if len(self._hits) >= MAX_CLIENTS:  # still full: drop the oldest half
            for key in list(self._hits)[: MAX_CLIENTS // 2]:
                del self._hits[key]


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]  # added by our ingress; earlier entries are client-supplied
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str) -> Callable[[Request], Awaitable[None]]:
    """A FastAPI dependency that answers 429 with Retry-After when over the limit."""

    async def dependency(request: Request) -> None:
        settings = request.app.state.settings
        per_minute = getattr(settings, f"rate_{bucket}_per_min")
        wait = request.app.state.limiter.check(
            bucket, client_ip(request, settings.trust_proxy), per_minute
        )
        if wait is not None:
            raise HTTPException(
                status_code=429,
                detail="too many requests",
                headers={"Retry-After": str(max(1, round(wait)))},
            )

    return dependency


class BodySizeLimit:
    """Refuse API bodies over the limit with 413, counting bytes even without Content-Length."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        limit = UPLOAD_BODY_LIMIT if scope["path"] in UPLOAD_PATHS else JSON_BODY_LIMIT
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None and length.isdigit() and int(length) > limit:
            await _too_large(send)
            return
        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await _too_large(send)


class _BodyTooLarge(Exception):
    pass


async def _too_large(send: Send) -> None:
    body = b'{"detail":"request body too large"}'
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
