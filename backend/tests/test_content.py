"""Every content file validates against the draft schema, and sympy checks its math.

Covers content/source (lessons and misconceptions), content/practice and evals/mistakes.yaml.
sympy checks every answer, every wrong answer, and every inline claim written as
"`A` is `B`" or "`A` = `B`" in prose. Other backtick spans are only checked to parse.
The misconception sentences that state a wrong answer on purpose are skipped.
Rule reproduction (a rule turns the example problem into the wrong answer) is checked by
pipeline/verify.py in T5, once T1's rule registry exists.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
import sympy
import yaml
from pydantic import ValidationError
from sympy.parsing.sympy_parser import convert_xor, parse_expr, standard_transformations

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

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
SPAN = re.compile(r"`([^`]+)`")
# "`A` is `B`", "`A`, which is `B`" or "`A` = `B`": a claim that A equals B.
CLAIM = re.compile(r"`([^`=]+)`(?:,? which)? (?:is|=) `([^`]+)`")
TRANSFORMS = (*standard_transformations, convert_xor)


def parse(text: str) -> Any:
    return parse_expr(text, transformations=TRANSFORMS, evaluate=True)


def parse_math(text: str) -> None:
    """Parse an expression, or both sides of an equation."""
    for side in text.split("="):
        parse(side)


def solution(problem: Problem) -> Any:
    """sympy's answer: the value of an expression, or the single solution of an equation."""
    if problem.kind == "solve":
        left, right = problem.expr.split("=")
        eq = sympy.Eq(parse(left), parse(right))
        symbols = sorted(eq.free_symbols, key=str)
        assert len(symbols) == 1, f"{problem.expr}: one unknown expected"
        roots = sympy.solve(eq, symbols[0])
        assert len(roots) == 1, f"{problem.expr}: one solution expected"
        return roots[0]
    value = sympy.nsimplify(parse(problem.expr))
    assert value.is_Rational, f"{problem.expr}: rational value expected"
    return value


def check_answer(problem: Problem, answer: str) -> None:
    """The answer equals sympy's and is written in canonical form (lowest terms)."""
    expected = solution(problem)
    assert answer == str(expected), f"{problem.expr}: answer {answer}, sympy says {expected}"


def check_wrong(problem: Problem, wrong: str) -> None:
    assert sympy.simplify(parse(wrong) - solution(problem)) != 0, f"{problem.expr}: {wrong}"


def spans(text: str) -> list[str]:
    return SPAN.findall(text)


def check_spans(text: str, claims: bool = True) -> None:
    """Every span parses; with `claims`, every "`A` is `B`" pair is true."""
    for span in spans(text):
        parse_math(span)
    if claims:
        for left, right in CLAIM.findall(text):
            right = right.split("=")[-1]
            assert sympy.simplify(parse(left) - parse(right)) == 0, f"false claim: {left} = {right}"


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
        expected = solution(case.problem)
        given = parse(case.student_answer)
        same = sympy.simplify(given - expected) == 0
        match case.expected.classification:
            case "correct":
                assert case.student_answer == str(expected), case.id
            case "equivalent_not_simplified":
                assert same and case.student_answer != str(expected), case.id
            case "wrong":
                assert not same, case.id
        for step in case.student_working:
            parse_math(step.left)
            if step.right:
                parse_math(step.right)
        mid = case.expected.misconception_id
        assert mid is None or mid == "other" or mid in ids[case.topic], case.id


def test_attribution() -> None:
    text = (CONTENT / "ATTRIBUTION.md").read_text()
    for topic in TOPIC_IDS:
        assert practice(topic).items[0].source.commit in text
    assert "12bee142d49dfb3c874149035cfbad28547a818b" in text
    assert "Permission is hereby granted" in text


def test_claim_check_catches_a_false_hint() -> None:
    with pytest.raises(AssertionError, match="false claim"):
        check_spans("So `7/12` is `29/48`.")
    check_spans("So `7/12 - 9/16` = `1/48`.")


def test_parser_reads_caret_as_power() -> None:
    assert parse("(-3)^5") == -243


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
        (
            {"classification": "wrong", "status": "diagnosed", "misconception_id": "x"},
            {"commit": None},
        ),
        (
            {"classification": "wrong", "status": "diagnosed", "misconception_id": "x"},
            {"license": "CC-BY-4.0"},
        ),
    ],
)
def test_case_validators(expected: dict[str, Any], source: dict[str, Any]) -> None:
    data = yaml.safe_load((ROOT / "evals" / "mistakes.yaml").read_text())
    case = data["cases"][0]
    with pytest.raises(ValidationError):
        MistakeCase.model_validate(
            {**case, "expected": expected, "source": {**case["source"], **source}}
        )
