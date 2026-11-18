"""Request limits, applied in one ASGI middleware before any route runs.

For each limited API path it checks the per-client rate limit first (so a client over its
limit uploads nothing), then reads the whole body into memory while counting it, answers
413 when it is too large (with or without Content-Length), and replays the body to the app.
Uploads are at most 6 MB and must stay in memory anyway (no spooling to disk).

Everything is in memory and per process, which fits one small container. Nothing about a
client is kept beyond request times, for one minute.
"""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable

from starlette.formparsers import MultiPartParser
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings

WINDOW_S = 60.0
MAX_CLIENTS = 10_000

JSON_BODY_LIMIT = 64 * 1024
UPLOAD_BODY_LIMIT = 6 * 1024 * 1024

# Path -> (rate-limit bucket, body limit).
LIMITED: dict[str, tuple[str, int]] = {
    "/api/mistake": ("mistake", JSON_BODY_LIMIT),
    "/api/check-working": ("check_working", JSON_BODY_LIMIT),
    "/api/transcribe": ("transcribe", UPLOAD_BODY_LIMIT),
}


def keep_uploads_in_memory() -> None:
    """Starlette spools multipart files over 1 MB to a temporary file on disk. Photos must
    stay in memory, and the body cap is 6 MB, so raise the spool threshold above it."""
    MultiPartParser.spool_max_size = UPLOAD_BODY_LIMIT + 1


class RateLimiter:
    """A sliding window of request times per (bucket, client)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._clock = clock

    def check(self, bucket: str, client: str, per_minute: int) -> float | None:
        """None when allowed (and counted); else the seconds until the next request fits.
        A limit of 0 or less turns the limit off."""
        if per_minute <= 0:
            return None
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


def client_ip(scope: Scope, trust_proxy: bool) -> str:
    """The client's IP. Behind the Container Apps ingress (`trust_proxy`), it is the
    right-most X-Forwarded-For entry: the proxy appends the address it saw, and anything to
    its left was sent by the client and can be forged. When the proxy sends a single entry,
    the right-most is also the first."""
    if trust_proxy:
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                hops = [h.strip() for h in value.decode("latin-1").split(",") if h.strip()]
                if hops:
                    return str(hops[-1])
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


class ApiGuard:
    def __init__(self, app: ASGIApp, settings: Settings, limiter: RateLimiter) -> None:
        self.app = app
        self.settings = settings
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limited = LIMITED.get(scope.get("path", "")) if scope["type"] == "http" else None
        if limited is None or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        bucket, body_limit = limited
        per_minute: int = getattr(self.settings, f"rate_{bucket}_per_min")
        wait = self.limiter.check(bucket, client_ip(scope, self.settings.trust_proxy), per_minute)
        if wait is not None:
            await _reply(send, 429, "too many requests", {"retry-after": str(max(1, round(wait)))})
            return
        body = await _read_body(scope, receive, body_limit)
        if body is None:
            await _reply(send, 413, "request body too large")
            return
        await self.app(scope, _replay(body, receive), send)


async def _read_body(scope: Scope, receive: Receive, limit: int) -> bytes | None:
    """The whole body, or None as soon as it is over `limit`."""
    for name, value in scope.get("headers", []):
        if name == b"content-length" and value.isdigit() and int(value) > limit:
            return None
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break  # the client went away; the app will see an empty body
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _replay(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()  # http.disconnect

    return replay


async def _reply(
    send: Send, status: int, detail: str, headers: dict[str, str] | None = None
) -> None:
    body = json.dumps({"detail": detail}).encode()
    raw = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    raw += [(k.encode(), v.encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": status, "headers": raw})
    await send({"type": "http.response.body", "body": body})
