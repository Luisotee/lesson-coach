"""The pipeline: generate.py's retry, vote and drop loop with a fake LLM, and verify.py's
deterministic checks, including packs broken on purpose that verify must reject."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import generate  # noqa: E402
from pipeline.checks import lesson_findings, pack_findings, prose  # noqa: E402
from pipeline.generate import Stats  # noqa: E402
from pipeline.prompts import (  # noqa: E402
    ClaimOut,
    JudgeOut,
    OutlineOut,
    PackProseOut,
    QuestionOut,
    StepOut,
    StepsOut,
    strict_schema,
)
from pipeline.sources import load, pack_path  # noqa: E402
from pipeline.verify import verify_topic  # noqa: E402

from app.content.schema import TOPIC_IDS, Pack, PracticeItem, TopicId  # noqa: E402
from app.math import Kind, Problem, Step, check_steps  # noqa: E402

# sympy's steps for the worked examples, written out so these tests don't need the generator.
STEPS: dict[str, list[tuple[str, str, str]]] = {
    "5 - (-3)": [("5 - (-3)", "", ""), ("5 + 3", "", ""), ("8", "", "")],
    "-7 + 4": [("-7 + 4", "", ""), ("-(7 - 4)", "", ""), ("-3", "", "")],
    "(-4)*(-6)": [("(-4)*(-6)", "", ""), ("4*6", "", ""), ("24", "", "")],
    "1/2 + 1/3": [("1/2 + 1/3", "", ""), ("3/6 + 2/6", "", ""), ("5/6", "", "")],
    "3*(2/5)": [("3*(2/5)", "", ""), ("(3*2)/5", "", ""), ("6/5", "", "")],
    "(2/3)/(3/4)": [("(2/3)/(3/4)", "", ""), ("(2/3)*(4/3)", "", ""), ("8/9", "", "")],
    "2*x + 6 = 10": [("2*x + 6", "10", "-6"), ("2*x", "4", "/2"), ("x", "2", "")],
    "5*(x + 3) = 35": [("5*(x + 3)", "35", "/5"), ("x + 3", "7", "-3"), ("x", "4", "")],
    "3*x + 4 = x + 10": [
        ("3*x + 4", "x + 10", "-x"),
        ("2*x + 4", "10", "-4"),
        ("2*x", "6", "/2"),
        ("x", "3", ""),
    ],
}


def fake_steps(problem: Problem) -> list[Step]:
    return [Step(*line) for line in STEPS[problem.expr]]


@pytest.mark.parametrize("expr", list(STEPS))
def test_fake_steps_are_valid(expr: str) -> None:
    kind: Kind = "solve" if "=" in expr else "evaluate"
    assert check_steps(Problem(kind, expr), fake_steps(Problem(kind, expr))) == []


GOOD_STEP = StepOut(
    why="This line follows the engine's step.",
    another_way="Read the line aloud and picture it.",
    visual="The picture shows this line.",
)
BAD_STEP = StepOut(why="Add 999 here.", another_way="Or 999.", visual="999 blocks.")
GOOD_PROSE = PackProseOut(
    summary="A short card about the topic.",
    idea="The idea, in plain words, with `1/2 + 1/3` as an example.",
    why_it_works="Why it works: `5 - (-3)` is `8` here only if the topic says so.",
    questions=[QuestionOut(question=f"Question {n}?", answer="An answer.") for n in "ABCD"],
    outline=[OutlineOut(minutes=10, title="Part", activity="Do this.") for _ in range(4)],
)


@dataclass
class FakeUsage:
    prompt_tokens: int = 100
    cached_tokens: int = 50
    completion_tokens: int = 20
    reasoning_tokens: int = 5


@dataclass
class FakeResult:
    value: Any
    error: str | None = None
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeLLM:
    """Steps answers come from `steps` (one per call, the last repeats); the judge flags the
    fields in `flags` (one set per judge call, the last repeats)."""

    def __init__(
        self,
        steps: list[StepOut] | None = None,
        prose: list[PackProseOut] | None = None,
        flags: list[set[str]] | None = None,
    ) -> None:
        self.steps = steps or [GOOD_STEP]
        self.prose = prose or [GOOD_PROSE]
        self.flags = flags or [set()]
        self.calls: dict[str, int] = {}

    def _next[T](self, name: str, items: list[T]) -> T:
        n = self.calls.get(name, 0)
        self.calls[name] = n + 1
        return items[min(n, len(items) - 1)]

    async def structured(
        self,
        *,
        task: str,
        messages: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
        output: type[BaseModel],
    ) -> FakeResult:
        if output is JudgeOut:
            text = messages[-1]["content"]
            flags = self._next("judge", self.flags)
            claims = [
                ClaimOut(field=f, claim="a claim", verdict="unsupported", reason="wrong")
                for f in flags
                if f'"{f}"' in text
            ]
            return FakeResult(JudgeOut(claims=claims))
        if output is PackProseOut:
            return FakeResult(self._next("prose", self.prose))
        ask = next(m["content"] for m in messages if "for all " in str(m["content"]))
        lines = int(ask.split("for all ")[1].split()[0])
        step = self._next("steps", self.steps)
        return FakeResult(StepsOut(steps=[step] * lines))


def build(topic: TopicId, llm: FakeLLM) -> tuple[Pack, Stats]:
    packs, stats = asyncio.run(generate.generate([topic], llm, "fake-model", fake_steps))
    return packs[0], stats


def test_good_output_is_kept() -> None:
    pack, stats = build("fractions", FakeLLM())
    assert pack.unavailable == []
    assert pack_findings(pack, load("fractions"), fake_steps) == []
    assert stats.retries == 0 and stats.samples == 0
    assert stats.calls["generate"] == 4  # the pack text and one call per worked example


def test_bad_explanations_are_retried_voted_then_dropped() -> None:
    pack, stats = build("negative-numbers", FakeLLM(steps=[BAD_STEP]))
    for example in pack.worked_examples:
        assert all(s.explanations is None for s in example.steps)
    assert len(pack.unavailable) == sum(len(e.steps) for e in pack.worked_examples)
    assert pack_findings(pack, load("negative-numbers"), fake_steps) == []
    assert stats.retries == 3 and stats.samples == 3 * generate.SAMPLES


def test_the_targeted_retry_can_fix_the_output() -> None:
    pack, stats = build("negative-numbers", FakeLLM(steps=[BAD_STEP, GOOD_STEP]))
    assert pack.unavailable == []
    assert stats.retries >= 1


def test_one_judge_flag_is_outvoted() -> None:
    llm = FakeLLM(flags=[{"idea"}, set(), set()])
    pack, _ = build("fractions", llm)
    assert pack.idea is not None


def test_a_majority_of_judges_drops_the_field() -> None:
    llm = FakeLLM(flags=[{"idea"}])
    pack, stats = build("fractions", llm)
    assert pack.idea is None and "idea" in pack.unavailable
    assert stats.judge_flags["idea"] >= 1


def test_strict_schema_requires_every_property() -> None:
    schema = strict_schema(PackProseOut)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    for sub in schema["$defs"].values():
        assert sub["additionalProperties"] is False


@pytest.fixture(scope="module")
def good() -> Pack:
    return build("linear-equations", FakeLLM())[0]


def broken(pack: Pack, path: str, value: Any) -> Pack:
    """A copy of `pack` with the value at a dotted path (with [i] indexes) replaced."""
    data = pack.model_dump()
    keys = path.replace("[", ".").replace("]", "").split(".")
    node: Any = data
    for key in keys[:-1]:
        node = node[int(key)] if key.isdigit() else node[key]
    last = keys[-1]
    node[int(last) if last.isdigit() else last] = value
    return Pack.model_validate(data)


@pytest.mark.parametrize(
    ("path", "value", "check"),
    [
        ("worked_examples[0].steps[1].right", "5", "steps_changed"),
        ("worked_examples[0].answer", "x = 3", "wrong_answer"),
        ("worked_examples[0].steps[0].explanations.why", "Take away 7 here.", "number_not_in_step"),
        ("idea", "So `1/2 + 1/3` is `2/5`.", "false_claim"),
        ("why_it_works", "Write `2*x +` like this.", "unparsable"),
        ("misconceptions[0].example_wrong_answer", "2", "example_not_wrong"),
        ("misconceptions[0].check_question.answer", "6", "wrong_answer"),
        ("practice[0].answer", "8", "wrong_answer"),
        ("source_hash", "0" * 64, "stale"),
        ("title", "Another title", "changed"),
        ("unavailable", ["idea"], "mismatch"),
    ],
)
def test_verify_rejects_a_broken_pack(good: Pack, path: str, value: Any, check: str) -> None:
    findings = pack_findings(broken(good, path, value), load("linear-equations"), fake_steps)
    assert check in {f.check for f in findings}, findings


def test_the_schema_rejects_a_prompt_with_stray_math(good: Pack) -> None:
    with pytest.raises(ValueError, match="prompt numbers"):
        broken(good, "worked_examples[0].prompt", "Solve 2x + 6 = 12:")
    item = good.practice[0].model_dump()
    with pytest.raises(ValueError, match="prompt numbers"):
        PracticeItem.model_validate({**item, "prompt": "Solve 8x = 57."})


def test_claims_skip_only_the_stated_wrong_answer() -> None:
    text = "They write `5 - (-3)` as `2`. But `5 - (-3)` is `8`, and `6/2`, which is `3`."
    assert prose("t", text, wrong=["2"]) == []
    assert prose("t", "Then `6/2`, which is `4`.", wrong=["2"])


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_lessons_hold_every_claim(topic: TopicId) -> None:
    assert lesson_findings(load(topic)) == []


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_committed_packs_verify(topic: TopicId) -> None:
    if not pack_path(topic, "en").exists():
        pytest.skip("packs not generated yet")
    result = verify_topic(topic, "en")
    assert result.findings == []
