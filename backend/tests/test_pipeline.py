"""The pipeline: generate.py's retry, vote and drop loop with a fake LLM, and verify.py's
deterministic checks, including packs broken on purpose that verify must reject."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import generate  # noqa: E402
from pipeline.checks import lesson_findings, pack_findings, prose, solutions  # noqa: E402
from pipeline.examples import EXAMPLES  # noqa: E402
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
from pipeline.verify import (  # noqa: E402
    DEFAULT_PRICES,
    JUDGE_NOTE,
    judgeable,
    prices,
    verify_topic,
    write_report,
)

from app.content.schema import TOPIC_IDS, Pack, PracticeItem, TopicId  # noqa: E402
from app.content.schema import Problem as ContentProblem  # noqa: E402
from app.llm.client import LLMResult, Task, Usage  # noqa: E402
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


USAGE = Usage(prompt_tokens=100, cached_tokens=50, completion_tokens=20, reasoning_tokens=5)


class FakeLLM:
    """Steps answers come from `steps` (one per call, the last repeats): a StepOut repeated for
    every line, or a whole StepsOut. The judge flags the fields in `flags` (one set per judge
    call, the last repeats), or gives no verdict when `judge_down`."""

    def __init__(
        self,
        steps: list[StepOut | StepsOut] | None = None,
        prose: list[PackProseOut] | None = None,
        flags: list[set[str]] | None = None,
        judge_down: bool = False,
    ) -> None:
        self.steps = steps or [GOOD_STEP]
        self.prose = prose or [GOOD_PROSE]
        self.flags = flags or [set()]
        self.judge_down = judge_down
        self.calls: dict[str, int] = {}
        self.sent: list[str] = []  # every generate message, to see what retries quoted

    def _next[T](self, name: str, items: list[T]) -> T:
        n = self.calls.get(name, 0)
        self.calls[name] = n + 1
        return items[min(n, len(items) - 1)]

    async def structured[T: BaseModel](
        self,
        *,
        task: Task,
        messages: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> LLMResult[T]:
        return LLMResult(self._reply(messages, output), usage=USAGE)  # type: ignore[arg-type]

    def _reply(self, messages: list[dict[str, Any]], output: type[BaseModel]) -> BaseModel | None:
        if output is JudgeOut:
            if self.judge_down:
                self.calls["judge"] = self.calls.get("judge", 0) + 1
                return None
            text = messages[-1]["content"]
            flags = self._next("judge", self.flags)
            claims = [
                ClaimOut(field=f, claim="a claim", verdict="unsupported", reason="wrong")
                for f in flags
                if f'"{f}"' in text
            ]
            return JudgeOut(claims=claims)
        self.sent += [str(m["content"]) for m in messages]
        if output is PackProseOut:
            return self._next("prose", self.prose)
        ask = next(m["content"] for m in messages if "for all " in str(m["content"]))
        lines = int(ask.split("for all ")[1].split()[0])
        step = self._next("steps", self.steps)
        return step if isinstance(step, StepsOut) else StepsOut(steps=[step] * lines)


def build(topic: TopicId, llm: FakeLLM) -> tuple[Pack, Stats]:
    """One topic's pack; the topics run one at a time so FakeLLM's call order is fixed."""
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


def test_prose_failing_a_check_is_still_judged() -> None:
    """Every sample fails a check in one question; the judge must still read the rest."""
    bad_question = QuestionOut(question="Why?", answer="Because `2*x +` here.")
    sample = GOOD_PROSE.model_copy(update={"questions": [bad_question, *GOOD_PROSE.questions[1:]]})
    pack, _ = build("fractions", FakeLLM(prose=[sample], flags=[{"idea"}]))
    assert pack.idea is None
    assert {"idea", "questions[0]"} <= set(pack.unavailable)
    assert len(pack.questions) == 3
    assert pack_findings(pack, load("fractions"), fake_steps) == []


def test_a_whole_unit_failure_ranks_below_a_partial_one() -> None:
    """The first answer has the wrong number of lines; the later ones get one line wrong."""
    one_bad = StepsOut(steps=[GOOD_STEP, BAD_STEP, GOOD_STEP])
    llm = FakeLLM(steps=[StepsOut(steps=[GOOD_STEP]), one_bad])
    pack, _ = build("negative-numbers", llm)
    explained = [s.explanations is not None for s in pack.worked_examples[0].steps]
    assert explained == [True, False, True]


def test_no_judge_verdict_ships_nothing_and_is_not_sent_back() -> None:
    llm = FakeLLM(judge_down=True)
    pack, stats = build("fractions", llm)
    assert pack.idea is None and pack.summary is None and pack.questions == []
    assert all(s.explanations is None for e in pack.worked_examples for s in e.steps)
    assert stats.calls["generate"] == 4 and stats.retries == 0
    assert stats.calls["judge"] == 4 * generate.JUDGE_ATTEMPTS
    assert not any("no verdict" in m for m in llm.sent)
    assert pack_findings(pack, load("fractions"), fake_steps) == []


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("questions[0].answer", "questions[0]"),
        ("questions[1]", "questions[1]"),
        ("steps[1].why", "steps[1]"),
        ("steps[12]", "*"),
        ("questions", "*"),
        ("idea", "idea"),
    ],
)
def test_judge_fields_map_to_the_text_they_name(name: str, key: str) -> None:
    texts = {"idea": "", "questions[0]": "", "questions[1]": "", "steps[1]": ""}
    assert generate.judged_key(name, texts) == key


def test_each_pack_is_handed_on_as_soon_as_it_passes() -> None:
    def steps_for(problem: Problem) -> list[Step]:
        return [] if problem.expr == "1/2 + 1/3" else fake_steps(problem)

    written: list[str] = []
    with pytest.raises(generate.PackError, match="fractions"):
        asyncio.run(
            generate.generate(
                ["negative-numbers", "fractions"],
                FakeLLM(),
                "fake-model",
                steps_for,
                on_pack=lambda p: written.append(p.topic),
            )
        )
    assert written == ["negative-numbers"]


def test_strict_schema_requires_every_property() -> None:
    schema = strict_schema(PackProseOut)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    for sub in schema["$defs"].values():
        assert sub["additionalProperties"] is False
    outline = schema["$defs"]["OutlineOut"]
    assert (
        set(outline["required"]) == set(outline["properties"]) == {"minutes", "title", "activity"}
    )


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
        ("unavailable", ["questions[9]"], "mismatch"),
        ("lang", "de", "wrong_prompt"),
    ],
)
def test_verify_rejects_a_broken_pack(good: Pack, path: str, value: Any, check: str) -> None:
    findings = pack_findings(broken(good, path, value), load("linear-equations"), fake_steps)
    assert check in {f.check for f in findings}, findings


def test_the_schema_rejects_a_prompt_with_math(good: Pack) -> None:
    with pytest.raises(ValueError, match="prompt must be one of"):
        broken(good, "worked_examples[0].prompt", "Solve 2x + 6 = 12:")
    item = good.practice[0].model_dump()
    with pytest.raises(ValueError, match="prompt must be one of"):
        PracticeItem.model_validate({**item, "prompt": "Divide eight by two."})


def test_claims_about_the_unknown_use_the_solution() -> None:
    known = solutions(ContentProblem(kind="solve", expr="2*x + 6 = 10"))
    assert prose("t", "So `x` is `2`, and `2*x` equals `4`.", known=known) == []
    assert prose("t", "So `x` is `3`.", known=known)
    assert prose("t", "Then `2*x + 6` becomes `9`.", known=known)
    assert prose("t", "So `x` is `3`.")  # no solution known: only an identity passes
    assert prose("t", "And `2*(x + 3)` is `2*x + 6`.") == []
    assert prose("lesson", "Note `x + 3` is `x + 4`.")


def test_a_stated_wrong_answer_skips_only_numeric_claims() -> None:
    known = solutions(ContentProblem(kind="solve", expr="2*x + 6 = 10"))
    assert prose("t", "So `2*(x + 3)` is `2*x + 3`.", wrong=["5"], known=known)


def test_a_claim_is_checked_at_the_example_it_names() -> None:
    known = solutions(*EXAMPLES["linear-equations"])
    assert prose("t", "For `2*x + 6 = 10`, `x` is `2`.", known=known) == []
    assert prose("t", "For `2*x + 6 = 10`, `x` is `3`.", known=known)
    assert prose("t", "So `x` is `3`.", known=known)  # names no example: can't be tied


def test_generation_checks_claims_as_verify_does() -> None:
    pack, _ = build(
        "linear-equations",
        FakeLLM(
            steps=[StepOut(why="So `x` is `9`.", another_way="Picture it.", visual="A scale.")]
        ),
    )
    assert all(s.explanations is None for e in pack.worked_examples for s in e.steps)
    sample = GOOD_PROSE.model_copy(update={"idea": "For `2*x + 6 = 10`, `x` is `3`."})
    pack, _ = build("linear-equations", FakeLLM(prose=[sample]))
    assert pack.idea is None and "idea" in pack.unavailable


def test_wrong_answers_are_skipped_only_in_the_misconception_section() -> None:
    sources = load("negative-numbers")
    wrong = sources.misconceptions.misconceptions[0]
    claim = f"`{wrong.example_problem.expr}` is `{wrong.example_wrong_answer}`"
    lesson = sources.lesson.replace(
        "## Common misconceptions\n", f"## Common misconceptions\n{claim}\n"
    )
    assert lesson_findings(replace(sources, lesson=lesson)) == []
    lesson = sources.lesson.replace("## The idea\n", f"## The idea\n{claim}\n")
    assert lesson_findings(replace(sources, lesson=lesson))


def test_claims_skip_only_the_stated_wrong_answer() -> None:
    text = "They write `5 - (-3)` as `2`. But `5 - (-3)` is `8`, and `6/2`, which is `3`."
    assert prose("t", text, wrong=["2"]) == []
    assert prose("t", "Then `6/2`, which is `4`.", wrong=["2"])


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_lessons_hold_every_claim(topic: TopicId) -> None:
    assert lesson_findings(load(topic)) == []


def test_topics_without_a_readable_pack_are_not_judged() -> None:
    results = [verify_topic(t, "xx") for t in TOPIC_IDS]
    assert judgeable(results) == []


def test_a_bad_price_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICE_INPUT", "five")
    monkeypatch.setenv("PRICE_OUTPUT", "12")
    assert prices() == {**DEFAULT_PRICES, "output": 12.0}


def test_the_report_keeps_one_judge_note(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text("# old\n\n## Generation\n\n- LLM calls: 1\n")
    for _ in range(3):
        write_report(report, "en", judged={})
        write_report(report, "en", judged={"fractions": {}})
    text = report.read_text()
    assert text.count(JUDGE_NOTE) == 1 and text.count("## Generation") == 1
    assert "- LLM calls: 1" in text


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_committed_packs_verify(topic: TopicId) -> None:
    if not pack_path(topic, "en").exists():
        pytest.skip("packs not generated yet")
    result = verify_topic(topic, "en")
    assert result.findings == []
