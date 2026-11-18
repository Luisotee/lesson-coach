"""Lesson Coach API, and the built frontend served as a single-page app."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

app = FastAPI(title="Lesson Coach")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    """Serve a built file if it exists, otherwise index.html so client routes work."""
    if path.startswith("api/"):
        raise HTTPException(status_code=404)
    dist = FRONTEND_DIST.resolve()
    candidate = (dist / path).resolve()
    if path and candidate.is_relative_to(dist) and candidate.is_file():
        return FileResponse(candidate)
    index = dist / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend not built. Run `make build`.")
    return FileResponse(index)
