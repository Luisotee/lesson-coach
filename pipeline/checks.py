"""Deterministic pack checks. They run before any LLM judge, in generate.py and verify.py.

sympy (through T1's `app.math`) decides every math question here: steps follow, answers are
right, claims such as "`A` is `B`", "`A` equals `B`" or "`A` becomes `B`" are true (a side with
the unknown is evaluated at the worked example's solution), and every number in a step
explanation appears in that step. A finding names the pack path it is about.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import sympy
from app.content.schema import (
    NUMBER,
    ExplainedStep,
    Misconception,
    Pack,
    PracticeItem,
    StepExplanations,
    WorkedExample,
)
from app.content.schema import Problem as ContentProblem
from app.math import (
    MathError,
    Problem,
    Step,
    check_steps,
    classify_answer,
    equivalent,
    parse_text,
    rule_reproduces,
    solve,
    to_sympy,
)
from app.math.nodes import Eq, free_vars

from pipeline.core import StepsFor
from pipeline.examples import EXAMPLES, prompt_for
from pipeline.sources import Sources

SPAN = re.compile(r"`([^`]+)`")
# "`A` is `B`", "`A`, which is `B`", "`A` = `B`", "`A` equals `B`" or "`A` becomes `B`": a
# claim that A equals B.
CLAIM = re.compile(r"`([^`=]+)`(?:,? which)? (?:is|=|equals|becomes) `([^`]+)`")
MISCONCEPTIONS = re.compile(r"^## Common misconceptions\n(.*?)(?=^## |\Z)", re.M | re.S)

Solution = dict[sympy.Symbol, sympy.Expr]  # the unknown's value in one worked problem


@dataclass(frozen=True)
class Finding:
    path: str
    check: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}: {self.check}: {self.detail}"


def math_problem(problem: ContentProblem) -> Problem:
    return Problem(problem.kind, problem.expr)


def numbers(*texts: str) -> set[str]:
    return {n for text in texts for n in NUMBER.findall(text)}


def solutions(*problems: ContentProblem) -> list[Solution]:
    """The unknown's value in each problem that has one."""
    found: list[Solution] = []
    for problem in problems:
        try:
            s = solve(math_problem(problem))
        except MathError:
            continue
        if s.kind == "value" and s.variable is not None and s.value is not None:
            found.append({sympy.Symbol(s.variable): s.value})
    return found


def _same_value(a: str, b: str, known: Sequence[Solution] = ()) -> bool:
    """A and B are equal. With the unknown in them, at one of the `known` solutions; with no
    solution known, a claim about the unknown can't be checked and passes."""
    try:
        left, right = parse_text(a), parse_text(b)
        if (
            isinstance(left, Eq)
            or isinstance(right, Eq)
            or not (free_vars(left) | free_vars(right))
        ):
            return equivalent(left, right)
        if not known:
            return True
        difference = to_sympy(left) - to_sympy(right)
        return any(sympy.simplify(difference.subs(s)) == 0 for s in known)
    except MathError:
        return False


def prose(
    path: str,
    text: str,
    *,
    allowed: set[str] | None = None,
    wrong: Iterable[str] = (),
    known: Sequence[Solution] = (),
) -> list[Finding]:
    """Every backtick span parses; every claim is true (with the unknown, at one of the `known`
    solutions) unless its right side is one of the `wrong` answers the text states on purpose;
    with `allowed`, every number is in it."""
    found: list[Finding] = []
    for span in SPAN.findall(text):
        try:
            parse_text(span)
        except MathError as err:
            found.append(Finding(path, "unparsable", f"`{span}`: {err}"))
    wrong = list(wrong)
    for left, right in CLAIM.findall(text):
        right = right.split("=")[-1].strip()
        if any(_same_value(right, w) for w in wrong):
            continue
        if not _same_value(left, right, known):
            found.append(Finding(path, "false_claim", f"`{left}` is not `{right}`"))
    if allowed is not None:
        stray = numbers(text) - allowed
        if stray:
            found.append(Finding(path, "number_not_in_step", f"{sorted(stray)} not in the step"))
    return found


def step_numbers(example: WorkedExample, index: int) -> set[str]:
    """The numbers an explanation of step `index` may use: its line and its neighbours, the
    problem and the answer."""
    lines = example.steps[max(0, index - 1) : index + 2]
    texts = [example.problem.expr, example.answer]
    texts += [t for s in lines for t in (s.left, s.right, s.op)]
    return numbers(*texts)


def explanation_findings(
    path: str, ex: StepExplanations, allowed: set[str], known: Sequence[Solution] = ()
) -> list[Finding]:
    found: list[Finding] = []
    for name in ("why", "another_way", "visual"):
        found += prose(f"{path}.{name}", getattr(ex, name), allowed=allowed, known=known)
    return found


def example_findings(
    path: str, example: WorkedExample, expected: ContentProblem, steps_for: StepsFor
) -> list[Finding]:
    """The steps and answer are sympy's, unchanged; the explanations hold up."""
    found: list[Finding] = []
    if example.problem != expected:
        found.append(Finding(path, "wrong_problem", f"expected {expected.expr}"))
    if example.prompt != prompt_for(example.problem):
        found.append(Finding(f"{path}.prompt", "wrong_prompt", example.prompt))
    problem = math_problem(example.problem)
    try:
        want = [(s.left, s.right, s.op) for s in steps_for(problem)]
        answer = solve(problem).answer_text
    except MathError as err:
        return [*found, Finding(path, "unsupported", str(err))]
    got = [(s.left, s.right, s.op) for s in example.steps]
    if got != want:
        found.append(Finding(f"{path}.steps", "steps_changed", "not sympy's worked steps"))
    if len(want) < 3:
        found.append(Finding(f"{path}.steps", "too_few_steps", "the generator gave no real steps"))
    for issue in check_steps(problem, [_step(s) for s in example.steps]):
        found.append(Finding(f"{path}.steps[{issue.index}]", issue.reason, issue.detail))
    if example.answer != answer:
        found.append(Finding(f"{path}.answer", "wrong_answer", f"sympy says {answer}"))
    known = solutions(example.problem)
    for i, step in enumerate(example.steps):
        if step.explanations is not None:
            allowed = step_numbers(example, i)
            found += explanation_findings(
                f"{path}.steps[{i}].explanations", step.explanations, allowed, known
            )
    return found


def _step(step: ExplainedStep) -> Step:
    return Step(step.left, step.right, step.op)


def misconception_findings(path: str, m: Misconception) -> list[Finding]:
    found: list[Finding] = []
    example = math_problem(m.example_problem)
    try:
        if classify_answer(example, m.example_wrong_answer) != "wrong":
            found.append(Finding(path, "example_not_wrong", m.example_wrong_answer))
        if m.rule_sympy and not rule_reproduces(m.rule_sympy, example, m.example_wrong_answer):
            found.append(Finding(path, "rule_does_not_reproduce", m.rule_sympy))
        check = math_problem(m.check_question.problem)
        if classify_answer(check, m.check_question.answer) != "correct":
            found.append(Finding(f"{path}.check_question", "wrong_answer", m.check_question.answer))
    except MathError as err:
        found.append(Finding(path, "unsupported", str(err)))
    wrong = [m.example_wrong_answer]
    known = solutions(m.example_problem, m.check_question.problem)
    texts = {
        "belief": m.belief,
        "why_it_feels_right": m.why_it_feels_right,
        "source_quote": m.source_quote,
        "what_to_say.probe": m.what_to_say.probe,
        "what_to_say.nudge": m.what_to_say.nudge,
        "what_to_say.tell": m.what_to_say.tell,
    }
    for name, text in texts.items():
        found += prose(f"{path}.{name}", text, wrong=wrong, known=known)
    return found


def practice_findings(path: str, item: PracticeItem) -> list[Finding]:
    found: list[Finding] = []
    try:
        if classify_answer(math_problem(item.problem), item.answer) != "correct":
            found.append(Finding(path, "wrong_answer", item.answer))
    except MathError as err:
        found.append(Finding(path, "unsupported", str(err)))
    known = solutions(item.problem)
    for i, hint in enumerate(item.hints):
        found += prose(f"{path}.hints[{i}]", hint.text, known=known)
    return found


def lesson_findings(sources: Sources) -> list[Finding]:
    """The lesson's own claims. Only in its "Common misconceptions" section are claims whose
    right side is a misconception's stated wrong answer skipped."""
    wrong = [m.example_wrong_answer for m in sources.misconceptions.misconceptions]
    section = MISCONCEPTIONS.search(sources.lesson)
    if section is None:
        return prose("lesson", sources.lesson)
    rest = sources.lesson[: section.start()] + sources.lesson[section.end() :]
    return prose("lesson", rest) + prose("lesson", section.group(1), wrong=wrong)


def pack_findings(pack: Pack, sources: Sources, steps_for: StepsFor) -> list[Finding]:
    """Every deterministic check of a pack against its sources."""
    found: list[Finding] = []
    meta = sources.meta
    if pack.topic != sources.topic:
        found.append(Finding("topic", "wrong_topic", pack.topic))
    if pack.source_hash != sources.hash:
        found.append(Finding("source_hash", "stale", "the sources changed; regenerate the pack"))
    copied = {
        "title": (pack.title, meta.title),
        "grades": (pack.grades, meta.grades),
        "prerequisites": (pack.prerequisites, meta.prerequisites),
        "akelius_lessons": (pack.akelius_lessons, meta.akelius_lessons),
        "misconceptions": (pack.misconceptions, sources.misconceptions.misconceptions),
        "practice": (pack.practice, sources.practice.items),
    }
    for name, (got, want) in copied.items():
        if got != want:
            found.append(Finding(name, "changed", "must equal the source content"))
    for i, (example, expected) in enumerate(
        zip(pack.worked_examples, EXAMPLES[pack.topic], strict=True)
    ):
        found += example_findings(f"worked_examples[{i}]", example, expected, steps_for)
    for i, m in enumerate(pack.misconceptions):
        found += misconception_findings(f"misconceptions[{i}]", m)
    for i, item in enumerate(pack.practice):
        found += practice_findings(f"practice[{i}]", item)
    found += lesson_findings(sources)
    known = solutions(*EXAMPLES[pack.topic])
    for name in ("summary", "idea", "why_it_works"):
        text = getattr(pack, name)
        if text is not None:
            found += prose(name, text, known=known)
    for i, q in enumerate(pack.questions):
        found += prose(f"questions[{i}].question", q.question, known=known)
        found += prose(f"questions[{i}].answer", q.answer, known=known)
    for i, o in enumerate(pack.outline):
        found += prose(f"outline[{i}].activity", o.activity, known=known)
    found += unavailable_findings(pack)
    return found


def dropped_paths(pack: Pack) -> set[str]:
    """The prose a pack ships without: null fields, empty lists, and steps with no explanation."""
    dropped = {name for name in ("summary", "idea", "why_it_works") if getattr(pack, name) is None}
    dropped |= {name for name in ("questions", "outline") if not getattr(pack, name)}
    for i, example in enumerate(pack.worked_examples):
        for j, step in enumerate(example.steps):
            if step.explanations is None:
                dropped.add(f"worked_examples[{i}].steps[{j}].explanations")
    return dropped


QUESTION = re.compile(r"^questions\[(\d+)\]$")


def unavailable_findings(pack: Pack) -> list[Finding]:
    """`unavailable` lists exactly the prose that was dropped. A question dropped on its own
    leaves no gap in the pack, so it is listed as `questions[i]`, its index among the questions
    generated; the shipped and the dropped questions add up to the 4-6 asked for."""
    dropped = dropped_paths(pack)
    listed = set(pack.unavailable)
    single = {int(m[1]) for p in listed if (m := QUESTION.match(p))}
    generated = len(pack.questions) + len(single)
    extra = {p for p in listed - dropped if not QUESTION.match(p)}
    if not dropped <= listed or extra or (single and not 4 <= generated <= 6):
        return [Finding("unavailable", "mismatch", f"dropped {sorted(dropped)}")]
    if single and max(single) >= generated:
        return [
            Finding("unavailable", "mismatch", f"question index out of range: {sorted(single)}")
        ]
    return []
