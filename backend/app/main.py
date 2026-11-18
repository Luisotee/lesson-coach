"""Lesson Coach API, and the built frontend served as a single-page app."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api import check_working, mistake, topics, transcribe
from app.api.limits import BodySizeLimit, RateLimiter
from app.config import Settings, get_settings
from app.content.store import PackStore
from app.llm.azure import AzureLLM
from app.llm.client import LLM, NullLLM
from app.mathpool import MathPool

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ALL_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def _log_numbers_only() -> None:
    """LLM calls log one JSON line of numbers each (no text) on the `app` logger."""
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())


def create_app(settings: Settings | None = None, llm: LLM | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings and a fake LLM."""
    settings = settings or get_settings()
    pool = MathPool(settings.math_workers, settings.math_timeout_s)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool.start()
        try:
            yield
        finally:
            pool.stop()

    app = FastAPI(title="Lesson Coach", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = PackStore.load(settings.content_dir)
    app.state.pool = pool  # without the lifespan (plain TestClient) it runs inline
    app.state.limiter = RateLimiter()
    if llm is None:
        llm = AzureLLM(settings) if settings.llm_configured else NullLLM()
    app.state.llm = llm
    app.add_middleware(BodySizeLimit)
    _log_numbers_only()

    for module in (topics, mistake, transcribe, check_working):
        app.include_router(module.router)
    # Register every API route above this line: the catch-alls must come last.
    app.include_router(fallback)
    return app


fallback = APIRouter()


@fallback.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@fallback.api_route("/api", methods=ALL_METHODS, include_in_schema=False)
@fallback.api_route("/api/{rest:path}", methods=ALL_METHODS, include_in_schema=False)
def api_not_found() -> None:
    """Unknown API paths are a JSON 404 for any method, never the SPA or a 405."""
    raise HTTPException(status_code=404)


def _is_api_path(path: str) -> bool:
    lowered = path.lower()
    return lowered == "api" or lowered.startswith("api/")


@fallback.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def spa(path: str) -> FileResponse:
    """Serve a built file if it exists, otherwise index.html so client routes work."""
    if _is_api_path(path):
        raise HTTPException(status_code=404)
    dist = FRONTEND_DIST.resolve()
    candidate = (dist / path).resolve()
    if path and candidate.is_relative_to(dist) and candidate.is_file():
        return FileResponse(candidate)
    index = dist / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend not built. Run `make build`.")
    return FileResponse(index)


app = create_app()
