"""The generated packs, loaded once at startup and held in memory.

Files are `<content_dir>/<lang>/<topic>.json`, validated with the `Pack` schema (T5 owns it,
so the store never names its fields beyond topic and lang). A pack that doesn't validate
stops the app from starting, so a broken pack can't ship.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.content.schema import TOPIC_IDS, Pack

FALLBACK_LANG = "en"


class PackError(Exception):
    pass


@dataclass(frozen=True)
class TopicSummary:
    id: str
    title: str
    lang: str
    langs: list[str]
    machine_translated: bool
    prerequisites: list[str]
    grades: list[int]
    summary: str | None


class PackStore:
    def __init__(self, packs: dict[tuple[str, str], Pack] | None = None) -> None:
        self._packs = packs or {}

    @classmethod
    def load(cls, content_dir: Path) -> PackStore:
        packs: dict[tuple[str, str], Pack] = {}
        if not content_dir.is_dir():
            return cls(packs)
        for path in sorted(content_dir.glob("*/*.json")):
            lang, topic = path.parent.name, path.stem
            try:
                pack = Pack.model_validate_json(path.read_bytes())
            except ValueError as err:
                raise PackError(f"{path} doesn't match the pack schema: {err}") from err
            if (pack.lang, pack.topic) != (lang, topic):
                raise PackError(f"{path} holds {pack.lang}/{pack.topic}")
            packs[(lang, topic)] = pack
        return cls(packs)

    def langs(self, topic: str) -> list[str]:
        return sorted(lang for lang, t in self._packs if t == topic)

    def get(self, topic: str, lang: str) -> Pack | None:
        """The pack in `lang`, else in English. `pack.lang` says which one was served."""
        return self._packs.get((lang, topic)) or self._packs.get((FALLBACK_LANG, topic))

    def topics(self, lang: str) -> list[TopicSummary]:
        out = []
        for topic in TOPIC_IDS:
            pack = self.get(topic, lang)
            if pack is None:
                continue
            out.append(
                TopicSummary(
                    id=topic,
                    title=pack.title,
                    lang=pack.lang,
                    langs=self.langs(topic),
                    machine_translated=pack.machine_translated,
                    prerequisites=list(pack.prerequisites),
                    # T5 adds these to the pack; until then they are empty.
                    grades=list(getattr(pack, "grades", None) or []),
                    summary=getattr(pack, "summary", None),
                )
            )
        return out
