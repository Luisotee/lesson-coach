"""Loads a topic's source content and hashes it, so a pack built from older sources is stale."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from app.content.schema import LessonMeta, MisconceptionSet, Pack, PracticeSet, TopicId

from pipeline import ROOT

CONTENT = ROOT / "content"
PROMPT_VERSION = "2"  # bump when a prompt changes, so every pack is regenerated


@dataclass(frozen=True)
class Sources:
    topic: TopicId
    meta: LessonMeta
    lesson: str  # the markdown body, without front matter
    misconceptions: MisconceptionSet
    practice: PracticeSet
    hash: str


def files(topic: TopicId) -> list[Path]:
    return [
        CONTENT / "source" / f"{topic}.md",
        CONTENT / "source" / f"{topic}.misconceptions.json",
        CONTENT / "practice" / f"{topic}.json",
        ROOT / "pipeline" / "examples.py",
        ROOT / "pipeline" / "prompts.py",
    ]


def source_hash(topic: TopicId) -> str:
    digest = hashlib.sha256(PROMPT_VERSION.encode())
    for path in files(topic):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load(topic: TopicId) -> Sources:
    text = (CONTENT / "source" / f"{topic}.md").read_text()
    _, front, body = text.split("---\n", 2)
    return Sources(
        topic=topic,
        meta=LessonMeta.model_validate(yaml.safe_load(front)),
        lesson=body,
        misconceptions=MisconceptionSet.model_validate_json(
            (CONTENT / "source" / f"{topic}.misconceptions.json").read_text()
        ),
        practice=PracticeSet.model_validate_json(
            (CONTENT / "practice" / f"{topic}.json").read_text()
        ),
        hash=source_hash(topic),
    )


def pack_path(topic: TopicId, lang: str) -> Path:
    return CONTENT / "generated" / lang / f"{topic}.json"


def load_pack(topic: TopicId, lang: str) -> Pack:
    return Pack.model_validate_json(pack_path(topic, lang).read_text())


def write_pack(pack: Pack) -> Path:
    path = pack_path(pack.topic, pack.lang)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = pack.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path


TRANSLATE_PROMPTS = ROOT / "pipeline" / "translate_prompts.py"


def translate_prompts_hash() -> str:
    """The translation prompts' bytes (TRANSLATE_VERSION among them): the one fingerprint of
    how translations are made, in every translated pack's `source_hash` and in the unit cache
    key, so a changed prompt makes both stale together."""
    return hashlib.sha256(TRANSLATE_PROMPTS.read_bytes()).hexdigest()


def translation_hash(topic: TopicId) -> str:
    """A translated pack's `source_hash`: the English pack and the translation prompts, so a
    translation is stale when either changes."""
    from pipeline.translate_prompts import TRANSLATE_VERSION

    digest = hashlib.sha256(f"translate-{TRANSLATE_VERSION}".encode())
    for path in (pack_path(topic, "en"), TRANSLATE_PROMPTS):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()
