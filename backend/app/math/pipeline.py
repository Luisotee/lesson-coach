"""The math half of each API request, as one function per endpoint.

These run in a worker process under a time limit (`app.mathpool`), so they take and return
plain, picklable data and turn every math error into a field instead of raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.math.canonical import Verdict, classify_answer
from app.math.nodes import Bin, Eq, MathError, MathParseError, Neg, Node, UnsupportedProblem, render
from app.math.parse import parse_text
from app.math.problems import Format, Kind, Problem, Step, parse_input, solve
from app.math.rules import ALL_RULES, reproducing_rules
from app.math.steps import first_line_that_doesnt_follow
from app.math.worked import worked_solution

MathErrorKind = Literal["problem_unreadable", "answer_unreadable", "unsupported"]


@dataclass(frozen=True)
class MathText:
    """Math typed by a person: plain text, or LaTeX from MathLive."""

    value: str
    fmt: Format = "text"


@dataclass(frozen=True)
class LineText:
    """A line of working: `left`/`right` plain text (the step contract), or one field of math
    (`math`) that may hold `=`. `op` is the margin operation on this line."""

    left: str = ""
    right: str = ""
    op: str = ""
    math: MathText | None = None


@dataclass(frozen=True)
class BadLine:
    index: int
    reason: str


@dataclass(frozen=True)
class WorkingLine:
    """A line as the student sent it, normalised (`2*x = 4`). When it can't be read, `left`
    is the raw text and `right`/`op` are None, so indexes still line up."""

    left: str
    right: str | None
    op: str | None


@dataclass
class MistakeFindings:
    """Everything sympy knows about a student's answer (PLAN mistake pipeline, steps 1-4)."""

    error: MathErrorKind | None = None
    kind: Kind | None = None
    expr: str | None = None
    correct_answer: str | None = None
    worked: list[Step] = field(default_factory=list)
    student_answer: str | None = None
    verdict: Verdict | None = None
    first_bad_line: BadLine | None = None
    rule_ids: list[str] = field(default_factory=list)
    topic: str | None = None
    working: list[WorkingLine] = field(default_factory=list)


@dataclass
class WorkingFindings:
    error: MathErrorKind | None = None
    lines: list[WorkingLine] = field(default_factory=list)
    first_bad_line: BadLine | None = None
    final: Verdict | None = None


def read_problem(problem: MathText, kind: Kind | None) -> Problem:
    """Normalise a typed problem to the `{kind, expr}` contract. Without a kind, an equation
    is solved and anything else is evaluated (which grades the same way as simplify)."""
    node = parse_input(problem.value, problem.fmt)
    if kind is None:
        kind = "solve" if isinstance(node, Eq) else "evaluate"
    return Problem(kind, render(node))  # sympy-parsable: `2*x + 6 = 10`


def read_line(line: LineText) -> Step:
    """A working line as a `Step`. A line that can't be read is kept as written, so the
    check reports it as unparsable at its own index."""
    if line.math is None:
        return Step(line.left, line.right, line.op)
    try:
        node = parse_input(line.math.value, line.math.fmt)
    except MathError:
        return Step(line.math.value, "", line.op)
    if isinstance(node, Eq):
        return Step(render(node.left), render(node.right), line.op)
    return Step(render(node), "", line.op)


def echo_line(line: LineText) -> WorkingLine:
    """The line normalised for display, or as sent when it can't be read."""
    if line.math is not None:
        raw = line.math.value
    else:
        raw = f"{line.left} = {line.right}" if line.right.strip() else line.left
    try:
        if line.math is not None:
            node = parse_input(line.math.value, line.math.fmt)
            if isinstance(node, Eq):
                left, right = render(node.left), render(node.right)
            else:
                left, right = render(node), ""
        else:
            left = render(parse_text(line.left))
            right = render(parse_text(line.right)) if line.right.strip() else ""
    except MathError:
        return WorkingLine(raw.strip(), None, None)
    return WorkingLine(left, right, line.op.strip())


def guess_topic(problem: Problem) -> str:
    """The topic a problem most likely belongs to, when the teacher didn't pick one."""
    if problem.kind == "solve":
        return "linear-equations"
    node = problem.node()
    return (
        "fractions"
        if _has(node, lambda n: isinstance(n, Bin) and n.op == "/")
        else ("negative-numbers")
    )


def _has(node: Node, test: object) -> bool:
    assert callable(test)
    if test(node):
        return True
    match node:
        case Neg(arg):
            return _has(arg, test)
        case Bin(_, left, right) | Eq(left, right):
            return _has(left, test) or _has(right, test)
        case _:
            return False


def analyse_mistake(
    problem_in: MathText,
    kind: Kind | None,
    answer_in: MathText,
    working: list[LineText],
    topic: str | None,
) -> MistakeFindings:
    """Solve the problem, classify the answer, find the first line that doesn't follow, and
    try the misconception rules, in that order."""
    out = MistakeFindings(working=[echo_line(w) for w in working])
    try:
        problem = read_problem(problem_in, kind)
        solution = solve(problem)
    except UnsupportedProblem:
        out.error = "unsupported"
        return out
    except MathError:
        out.error = "problem_unreadable"
        return out
    out.kind, out.expr = problem.kind, problem.expr
    out.correct_answer = solution.answer_text
    out.topic = topic or guess_topic(problem)
    try:
        out.worked = worked_solution(problem)
    except MathError:
        out.worked = []
    try:
        answer_node = parse_input(answer_in.value, answer_in.fmt)
        out.student_answer = render(answer_node)
        out.verdict = classify_answer(problem, out.student_answer)
    except UnsupportedProblem:
        out.error = "unsupported"
        return out
    except MathParseError:
        out.error = "answer_unreadable"
        return out
    if working:
        try:
            found = first_line_that_doesnt_follow([read_line(w) for w in working], problem)
        except UnsupportedProblem:
            found = None
        if found is not None:
            out.first_bad_line = BadLine(found.index, found.reason)
    if out.verdict == "wrong":
        out.rule_ids = reproducing_rules(problem, out.student_answer, topic=topic)
        if topic is None and out.rule_ids:
            out.topic = ALL_RULES[out.rule_ids[0]].topic
    return out


def check_working(
    problem_in: MathText | None, kind: Kind | None, lines: list[LineText]
) -> WorkingFindings:
    """Which line first doesn't follow (sympy only), and the last line's verdict."""
    out = WorkingFindings(lines=[echo_line(line) for line in lines])
    problem = None
    if problem_in is not None:
        try:
            problem = read_problem(problem_in, kind)
            _check_defined(problem)
        except UnsupportedProblem:
            out.error = "unsupported"
            return out
        except MathError:
            out.error = "problem_unreadable"
            return out
    steps = [read_line(line) for line in lines]
    try:
        found = first_line_that_doesnt_follow(steps, problem)
    except UnsupportedProblem:
        out.error = "unsupported"
        return out
    except MathError:
        out.error = "problem_unreadable"
        return out
    if found is not None:
        out.first_bad_line = BadLine(found.index, found.reason)
    elif problem is not None and steps:
        out.final = _final_verdict(problem, steps[-1])
    return out


def _check_defined(problem: Problem) -> None:
    """Raise like /api/mistake does for a problem with no value (`1/0`). A problem sympy
    can't solve (x^2 = 4) is still checked line by line."""
    try:
        solve(problem)
    except UnsupportedProblem:
        return


def _final_verdict(problem: Problem, last: Step) -> Verdict | None:
    text = (
        f"{last.left} = {last.right}"
        if last.left.strip() and last.right.strip()
        else (last.left or last.right)
    )
    try:
        return classify_answer(problem, text)
    except MathError:
        return None
