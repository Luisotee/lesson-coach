"""Lesson Coach API, and the built frontend served as a single-page app."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ALL_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

app = FastAPI(title="Lesson Coach")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Register every API route above this line: the two catch-alls below must come last.


@app.api_route("/api", methods=ALL_METHODS, include_in_schema=False)
@app.api_route("/api/{rest:path}", methods=ALL_METHODS, include_in_schema=False)
def api_not_found() -> None:
    """Unknown API paths are a JSON 404 for any method, never the SPA or a 405."""
    raise HTTPException(status_code=404)


def _is_api_path(path: str) -> bool:
    lowered = path.lower()
    return lowered == "api" or lowered.startswith("api/")


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
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
