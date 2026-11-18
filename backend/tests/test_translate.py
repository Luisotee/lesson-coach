"""translate.py with a fake translator, and the checks that keep a translation's math identical
to the English pack. The committed translations are checked here too."""

from __future__ import annotations

import asyncio
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import translate  # noqa: E402
from pipeline.checks import item_findings, prose_paths, translation_findings  # noqa: E402
from pipeline.generate import Stats  # noqa: E402
from pipeline.languages import LANGUAGES  # noqa: E402
from pipeline.prompts import ClaimOut, JudgeOut  # noqa: E402
from pipeline.sources import load_pack, translation_hash  # noqa: E402
from pipeline.translate_prompts import ItemOut, TranslationOut  # noqa: E402
from pipeline.verify import pack_langs, verify_topic  # noqa: E402

from app.content.schema import PROMPTS, TOPIC_IDS, Pack, TopicId  # noqa: E402
from app.llm.client import LLMResult, Task, Usage  # noqa: E402
from app.math import Problem, Step  # noqa: E402
from app.math.worked import worked_solution  # noqa: E402

ITEMS = re.compile(r"<items>\n(.*)\n</items>", re.S)


class FakeTranslator:
    """Prefixes every text with `[xx]`, which keeps its math. `mangle` changes the texts whose
    id contains it, every time; `flag` makes the judge flag those ids."""

    def __init__(self, mangle: str = "", flag: str = "") -> None:
        self.mangle, self.flag = mangle, flag
        self.calls: dict[str, int] = {}
        self.asked: list[str] = []

    async def structured[T: BaseModel](
        self,
        *,
        task: Task,
        messages: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> LLMResult[T]:
        import json

        self.calls[task] = self.calls.get(task, 0) + 1
        asked = [str(m["content"]) for m in messages if "<items>" in str(m["content"])]
        if task == "generate":
            self.asked.append(asked[-1])
        found = ITEMS.search(asked[-1])
        assert found is not None
        raw: dict[str, Any] = json.loads(found.group(1))
        items = {k: v["english"] if isinstance(v, dict) else v for k, v in raw.items()}
        if output is JudgeOut:
            claims = [
                ClaimOut(field=key, claim="x", verdict="unsupported", reason="meaning")
                for key in items
                if self.flag and self.flag in key
            ]
            return LLMResult(JudgeOut(claims=claims), usage=Usage(10, 0, 5, 0))  # type: ignore[arg-type]
        out = [
            ItemOut(id=k, text=v if k.startswith("prompts.") else f"[xx] {v}")
            for k, v in items.items()
        ]
        if self.mangle:
            out = [
                ItemOut(id=i.id, text=i.text.replace("`", "") if self.mangle in i.id else i.text)
                for i in out
            ]
        return LLMResult(TranslationOut(items=out), usage=Usage(100, 0, 50, 0))  # type: ignore[arg-type]


def steps(problem: Problem) -> list[Step]:
    return worked_solution(problem)


@pytest.fixture
def clean_prompts() -> Iterator[None]:
    yield
    PROMPTS.pop("xx-test", None)
    LANGUAGES.pop("xx-test", None)


def run(llm: FakeTranslator) -> tuple[list[Pack], dict[str, str], Stats]:
    LANGUAGES["xx-test"] = "Test language"
    stats = Stats()
    packs, prompts = asyncio.run(
        translate.translate_language("xx-test", llm, "fake", stats, steps_for=steps)
    )
    return packs, prompts, stats


def test_a_faithful_translation_passes(clean_prompts: None) -> None:
    packs, prompts, stats = run(FakeTranslator())
    assert [p.topic for p in packs] == list(TOPIC_IDS)
    assert prompts == PROMPTS["en"]
    for pack in packs:
        english = load_pack(pack.topic, "en")
        assert pack.machine_translated and pack.lang == "xx-test"
        assert translation_findings(pack, english, translation_hash(pack.topic), steps) == []
        assert all(t.startswith("[xx] ") for t in prose_paths(pack).values())
    assert stats.retries == 0 and stats.calls["judge"] == 1 + 3 * 6
    assert stats.calls["generate"] == 1 + 3 * 6  # the prompts, then six units per pack


def test_a_translation_that_changes_math_is_left_out(clean_prompts: None) -> None:
    with pytest.raises(translate.TranslationError, match="spans_changed"):
        run(FakeTranslator(mangle="what_to_say.tell"))
    assert "xx-test" not in PROMPTS


def test_a_translation_the_judge_keeps_flagging_is_left_out(clean_prompts: None) -> None:
    llm = FakeTranslator(flag="idea")
    with pytest.raises(translate.TranslationError, match="idea: judge"):
        run(llm)


def test_only_the_failing_texts_are_asked_for_again(clean_prompts: None) -> None:
    llm = FakeTranslator(mangle="practice[0].hints[0]")
    with pytest.raises(translate.TranslationError, match=r"practice\[0\]\.hints\[0\]"):
        run(llm)
    repairs = [m for m in llm.asked if "earlier" in m]
    assert repairs and all(
        '"practice[0].hints[0].text"' in m and "hints[1]" not in m for m in repairs
    )


@pytest.mark.parametrize(
    ("english", "translated", "check"),
    [
        ("So `5 - (-3)` is `8`.", "Donc `5 - (-3)` vaut `9`.", "spans_changed"),
        ("Add `3` and `4`.", "Ajoutez `3` et `4` puis 7.", "number_not_in_source"),
        ("Step 2 of 3.", "الخطوة ٢ من 3.", "digits"),
        ("Hi.", " ", "empty"),
    ],
)
def test_item_checks(english: str, translated: str, check: str) -> None:
    assert check in {f.check for f in item_findings("idea", english, translated)}


def test_changed_math_in_a_translated_pack_is_found(clean_prompts: None) -> None:
    packs, _, _ = run(FakeTranslator())
    pack = packs[0]
    english = load_pack(pack.topic, "en")
    data = pack.model_dump()
    data["worked_examples"][0]["answer"] = "9"
    data["practice"][0]["hints"][0]["text"] = "[xx] 41"
    broken = Pack.model_validate(data)
    found = {f.check for f in translation_findings(broken, english, pack.source_hash, steps)}
    assert {"changed", "wrong_answer", "number_not_in_source"} <= found
    stale = translation_findings(pack, english, "0" * 64, steps)
    assert "stale" in {f.check for f in stale}


@pytest.mark.parametrize("lang", [lang for lang in pack_langs() if lang != "en"])
def test_committed_translations_verify(lang: str) -> None:
    for topic in TOPIC_IDS:
        assert verify_topic(topic, lang).findings == [], (lang, topic)


def test_every_translated_language_has_its_prompts_and_all_packs() -> None:
    for lang in pack_langs():
        assert lang in PROMPTS, lang
        topics: list[TopicId] = list(TOPIC_IDS)
        for topic in topics:
            assert (ROOT / "content" / "generated" / lang / f"{topic}.json").exists(), lang
