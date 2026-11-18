"""`GET /api/topics` and `GET /api/topics/{id}`: the packs, served from memory."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.api.models import Lang, TopicOut
from app.content.schema import Pack, TopicId
from app.content.store import PackStore

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _store(request: Request) -> PackStore:
    store: PackStore = request.app.state.store
    return store


@router.get("", response_model=list[TopicOut])
def list_topics(request: Request, lang: Lang = "en") -> list[TopicOut]:
    return [TopicOut(**vars(t)) for t in _store(request).topics(lang)]


@router.get("/{topic}", response_model=Pack)
def get_topic(request: Request, topic: TopicId, lang: Lang = "en") -> Pack:
    """The pack in `lang`, or in English when there is none; `lang` in the reply says which."""
    pack = _store(request).get(topic, lang)
    if pack is None:
        raise HTTPException(status_code=404, detail="no pack for this topic")
    return pack
