"""`POST /api/transcribe`: a photo or drawing of math in, structured lines out.

The image is checked (size, declared type and magic bytes), read in memory, sent once to the
vision model and dropped. It is never stored or logged. The teacher confirms every line
before anything else runs.
"""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.api.limits import rate_limit
from app.api.models import TranscribedLine, TranscribeResult
from app.llm.client import LLM
from app.llm.prompts import TRANSCRIBE_SCHEMA, TranscribeOut, transcribe_messages
from app.math.nodes import MathError
from app.math.parse import parse_text

router = APIRouter(prefix="/api", tags=["transcribe"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024
UNCERTAIN_BELOW = 0.7
ALLOWED = ("image/png", "image/jpeg", "image/webp")


def sniff(data: bytes) -> str | None:
    """The image type from its first bytes, or None when it isn't one we accept."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _readable(text: str) -> bool:
    if not text.strip():
        return True
    try:
        parse_text(text)  # size-guarded, no sympy evaluation
    except MathError:
        return False
    return True


@router.post(
    "/transcribe",
    response_model=TranscribeResult,
    dependencies=[Depends(rate_limit("transcribe"))],
)
async def post_transcribe(
    request: Request, image: Annotated[UploadFile, File()]
) -> TranscribeResult:
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="the image is larger than 5 MB")
    kind = sniff(data)
    if kind is None or image.content_type not in ALLOWED or image.content_type != kind:
        raise HTTPException(status_code=415, detail="send a PNG, JPEG or WebP image")
    url = f"data:{kind};base64,{base64.b64encode(data).decode()}"
    del data
    llm: LLM = request.app.state.llm
    reply = await llm.structured(
        task="transcribe",
        messages=transcribe_messages(url),
        schema_name="transcription",
        schema=TRANSCRIBE_SCHEMA,
        output=TranscribeOut,
    )
    if reply.value is None:
        return TranscribeResult(status="unclear", reason="ai_unavailable")
    lines = [
        TranscribedLine(
            left=line.left.strip(),
            right=line.right.strip(),
            op=line.op.strip(),
            confidence=line.confidence,
            uncertain=line.confidence < UNCERTAIN_BELOW
            or not (_readable(line.left) and _readable(line.right)),
        )
        for line in reply.value.lines
        if line.left.strip() or line.right.strip()
    ]
    if not lines:
        return TranscribeResult(status="unclear", reason="no_math")
    return TranscribeResult(status="ok", lines=lines)
