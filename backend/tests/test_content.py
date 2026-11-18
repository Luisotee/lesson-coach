"""Every content file validates against the draft schema, and sympy checks its math.

Covers content/source (lessons and misconceptions), content/practice and evals/mistakes.yaml.
sympy checks every answer, every wrong answer, and every inline claim written as
"`A` is `B`" or "`A` = `B`" in prose. Other backtick spans are only checked to parse.
The misconception sentences that state a wrong answer on purpose are skipped.
Math is parsed by T1's parser (`app.math.parse_text`), so content must be valid user input too.
Every misconception linked to a rule is reproduced by that rule from T1's registry.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.content.schema import (
    RULE_IDS,
    TOPIC_IDS,
    LessonMeta,
    MisconceptionSet,
    MistakeCase,
    MistakeEvalSet,
    PracticeItem,
    PracticeSet,
    Problem,
    TopicId,
)
from app.math import (
    TOPICS,
    classify_answer,
    equivalent,
    format_value,
    parse_text,
    reproducing_rules,
    rule_reproduces,
    solve,
    to_sympy,
)
from app.math import Problem as MathProblem

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
SPAN = re.compile(r"`([^`]+)`")
# "`A` is `B`", "`A`, which is `B`" or "`A` = `B`": a claim that A equals B.
CLAIM = re.compile(r"`([^`=]+)`(?:,? which)? (?:is|=) `([^`]+)`")


def parse(text: str) -> Any:
    """An expression's sympy value, through T1's parser."""
    return to_sympy(parse_text(text))


def parse_math(text: str) -> None:
    """Parse an expression or an equation with T1's parser."""
    parse_text(text)


def math_problem(problem: Problem) -> MathProblem:
    return MathProblem(problem.kind, problem.expr)


def check_answer(problem: Problem, answer: str) -> None:
    """T1 grades the answer correct, and it is written as T1 writes the value."""
    mp = math_problem(problem)
    expected = format_value(solve(mp).value)
    assert classify_answer(mp, answer) == "correct", f"{problem.expr}: {answer}"
    assert answer == expected, f"{problem.expr}: answer {answer}, T1 writes {expected}"


def check_wrong(problem: Problem, wrong: str) -> None:
    assert classify_answer(math_problem(problem), wrong) == "wrong", f"{problem.expr}: {wrong}"


def spans(text: str) -> list[str]:
    return SPAN.findall(text)


def check_spans(text: str, claims: bool = True) -> None:
    """Every span parses; with `claims`, every "`A` is `B`" pair is true."""
    for span in spans(text):
        parse_math(span)
    if claims:
        for left, right in CLAIM.findall(text):
            right = right.split("=")[-1]
            assert equivalent(parse_text(left), parse_text(right)), f"false claim: {left} = {right}"


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


def lesson(topic: TopicId) -> tuple[LessonMeta, str]:
    text = (CONTENT / "source" / f"{topic}.md").read_text()
    _, front, body = text.split("---\n", 2)
    return LessonMeta.model_validate(yaml.safe_load(front)), body


def misconceptions(topic: TopicId) -> MisconceptionSet:
    path = CONTENT / "source" / f"{topic}.misconceptions.json"
    return MisconceptionSet.model_validate(json.loads(path.read_text()))


def practice(topic: TopicId) -> PracticeSet:
    path = CONTENT / "practice" / f"{topic}.json"
    return PracticeSet.model_validate(json.loads(path.read_text()))


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_lesson(topic: TopicId) -> None:
    meta, body = lesson(topic)
    assert meta.id == topic
    assert topic not in meta.prerequisites
    # The misconceptions section states wrong answers on purpose: parse it, don't check claims.
    before, rest = body.split("## Common misconceptions", 1)
    wrong, after = rest.split("\n## ", 1)
    check_spans(before + after)
    check_spans(wrong, claims=False)


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_misconceptions(topic: TopicId) -> None:
    _, body = lesson(topic)
    found = misconceptions(topic)
    assert found.topic == topic
    linked = {m.rule_sympy for m in found.misconceptions if m.rule_sympy}
    assert linked == RULE_IDS[topic], "every contracted rule has a misconception"
    for m in found.misconceptions:
        assert m.source_quote in body, f"{m.id}: source_quote is not verbatim in the lesson"
        check_wrong(m.example_problem, m.example_wrong_answer)
        check_answer(m.check_question.problem, m.check_question.answer)
        for text in strings(m.what_to_say.model_dump()):
            check_spans(text)
        for text in (m.belief, m.why_it_feels_right, m.source_quote):
            check_spans(text, claims=False)


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_practice(topic: TopicId) -> None:
    found = practice(topic)
    assert found.topic == topic
    for item in found.items:
        check_answer(item.problem, item.answer)
        for hint in item.hints:
            check_spans(hint.text)
        final = spans(item.hints[-1].text)
        assert any(s.split("=")[-1].strip() == item.answer for s in final), item.id
        assert item.source.commit in item.source.url
        assert item.source.path.startswith("content-pool/")


def test_mistakes() -> None:
    data = yaml.safe_load((ROOT / "evals" / "mistakes.yaml").read_text())
    cases = MistakeEvalSet.model_validate(data).cases
    ids = {t: {m.id for m in misconceptions(t).misconceptions} for t in TOPIC_IDS}
    for case in cases:
        verdict = classify_answer(math_problem(case.problem), case.student_answer)
        assert verdict == case.expected.classification, f"{case.id}: T1 says {verdict}"
        for step in case.student_working:
            parse_math(step.left)
            if step.right:
                parse_math(step.right)
        mid = case.expected.misconception_id
        assert mid is None or mid == "other" or mid in ids[case.topic], case.id
        # A rule that fires is a diagnosis made before any LLM call, so the label must agree:
        # a rule-linked label is reproduced by exactly its rule, and other rows by no rule.
        problem = MathProblem(case.problem.kind, case.problem.expr)
        fired = reproducing_rules(problem, case.student_answer, topic=case.topic)
        expected_rules = [mid] if mid in RULE_IDS[case.topic] else []
        assert fired == expected_rules, f"{case.id}: rules {fired}, label {mid}"


def test_attribution() -> None:
    text = (CONTENT / "ATTRIBUTION.md").read_text()
    for topic in TOPIC_IDS:
        for item in practice(topic).items:
            assert item.source.commit in text, item.id
            folder = item.source.path.split("/")[1]
            assert item.source.url.endswith(f"/content-pool/{folder}"), item.id
            assert item.source.path.startswith(f"content-pool/{folder}/steps/"), item.id
    assert "12bee142d49dfb3c874149035cfbad28547a818b" in text
    assert "Permission is hereby granted" in text


def test_claim_check_catches_a_false_hint() -> None:
    with pytest.raises(AssertionError, match="false claim"):
        check_spans("So `7/12` is `29/48`.")
    check_spans("So `7/12 - 9/16` = `1/48`.")


def test_parser_reads_caret_as_power() -> None:
    assert parse("(-3)^5") == -243


def test_topics_match_the_math_core() -> None:
    assert set(TOPICS) == set(TOPIC_IDS)


@pytest.mark.parametrize("topic", TOPIC_IDS)
def test_rules_reproduce_their_examples(topic: TopicId) -> None:
    for m in misconceptions(topic).misconceptions:
        if m.rule_sympy is not None:
            problem = MathProblem(m.example_problem.kind, m.example_problem.expr)
            assert rule_reproduces(m.rule_sympy, problem, m.example_wrong_answer), m.id


def test_ai_generated_names_real_fields() -> None:
    item = practice("fractions").items[0].model_dump()
    with pytest.raises(ValidationError, match="unknown fields"):
        PracticeItem.model_validate({**item, "ai_generated": ["hintz"]})


DIAGNOSED = {"classification": "wrong", "status": "diagnosed", "misconception_id": "x"}


@pytest.mark.parametrize(
    ("expected", "source"),
    [
        ({"classification": "correct", "status": "diagnosed"}, {}),
        ({"classification": "wrong"}, {}),
        ({"classification": "wrong", "status": "unclear", "misconception_id": "other"}, {}),
        ({"classification": "wrong", "status": "diagnosed"}, {}),
        (DIAGNOSED, {"commit": None}),
        (DIAGNOSED, {"license": "CC-BY-4.0"}),
    ],
)
def test_case_validators_reject(expected: dict[str, Any], source: dict[str, Any]) -> None:
    data = yaml.safe_load((ROOT / "evals" / "mistakes.yaml").read_text())
    case = data["cases"][0]
    with pytest.raises(ValidationError):
        MistakeCase.model_validate(
            {**case, "expected": expected, "source": {**case["source"], **source}}
        )


def test_case_validators_accept_a_diagnosed_row() -> None:
    data = yaml.safe_load((ROOT / "evals" / "mistakes.yaml").read_text())
    MistakeCase.model_validate({**data["cases"][0], "expected": DIAGNOSED})


@pytest.mark.parametrize(
    "prompt", ["Solve 8x = 57.", "Solve 8x = 56.", "Solve for y:", "Add one half and one third."]
)
def test_prompt_is_an_allowed_instruction(prompt: str) -> None:
    item = practice("linear-equations").items[0].model_dump()
    with pytest.raises(ValidationError, match="prompt must be one of"):
        PracticeItem.model_validate({**item, "prompt": prompt})
    PracticeItem.model_validate({**item, "prompt": "Solve for x:"})
