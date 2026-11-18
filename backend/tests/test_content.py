"""Every content file validates against the draft schema, and sympy checks its math.

Covers content/source (lessons and misconceptions), content/practice and evals/mistakes.yaml.
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
from sympy.parsing.sympy_parser import parse_expr

from app.content.schema import (
    RULE_IDS,
    TOPIC_IDS,
    LessonMeta,
    MisconceptionSet,
    MistakeEvalSet,
    PracticeSet,
    Problem,
    TopicId,
)

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
SPAN = re.compile(r"`([^`]+)`")


def parse(text: str) -> Any:
    return parse_expr(text, evaluate=True)


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


def check_spans(text: str) -> None:
    for span in spans(text):
        parse_math(span)


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
    check_spans(body)


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
        for text in strings(m.model_dump(exclude={"example_problem", "check_question"})):
            check_spans(text)


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
        if case.source.dataset == "MaE":
            assert case.source.commit and case.source.license == "MIT", case.id


def test_attribution() -> None:
    text = (CONTENT / "ATTRIBUTION.md").read_text()
    for topic in TOPIC_IDS:
        assert practice(topic).items[0].source.commit in text
    assert "12bee142d49dfb3c874149035cfbad28547a818b" in text
    assert "Permission is hereby granted" in text
