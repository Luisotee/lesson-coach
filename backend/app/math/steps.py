"""Checks over written lines: a worked example's steps, or a student's working.

A line's margin op acts on that line and gives the next one: `3x + 5 = 20 | -5`, then
`3x = 15 | /3`, then `x = 5` (as in the design's notebook).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import sympy

from app.math.canonical import is_canonical
from app.math.nodes import (
    BinOp,
    Eq,
    MathError,
    MathParseError,
    Node,
    Var,
    apply_op,
    free_vars,
    to_sympy,
)
from app.math.parse import parse_text
from app.math.problems import Kind, Problem, Step, equivalent, isolated, same_value, solve

MAX_OP_LENGTH = 30
_OP_SIGNS: dict[str, BinOp] = {
    "+": "+",
    "-": "-",
    "−": "-",
    "*": "*",
    "×": "*",
    "·": "*",
    "/": "/",
    "÷": "/",
    ":": "/",
}


@dataclass(frozen=True)
class Line:
    """A parsed line. `node` is what the line says now; `false_equality` marks a line such as
    `1/2 + 1/3 = 2/5` in an expression chain, whose two sides differ."""

    node: Node
    false_equality: bool = False


def parse_op(op: str) -> tuple[BinOp, sympy.Expr] | None:
    """`| -6`, `÷ 3`, `*(-1)` into an operation and its exact operand. None for an empty op."""
    text = op.strip().removeprefix("|").strip()
    if not text:
        return None
    if len(text) > MAX_OP_LENGTH:
        raise MathParseError(f"an operation may have at most {MAX_OP_LENGTH} characters")
    sign = _OP_SIGNS.get(text[0])
    if sign is None:
        raise MathParseError(f"an operation starts with + - * or /, not {text[0]!r}")
    operand = parse_text(text[1:])
    if isinstance(operand, Eq):
        raise MathParseError("an operation can't contain '='")
    return sign, to_sympy(operand)


def _side(text: str) -> Node:
    node = parse_text(text)
    if isinstance(node, Eq):
        raise MathParseError("one side of a line can't contain '='")
    return node


def parse_line(step: Step, kind: Kind, variable: str | None = None) -> Line:
    """Read a step. In a solve problem a line is an equation, and a bare number `3` means
    `variable = 3`. In an expression chain the line's value is its last written side."""
    left, right = step.left.strip(), step.right.strip()
    if not left and not right:
        raise MathParseError("the line is empty")
    if kind == "solve":
        if left and right:
            return Line(Eq(_side(left), _side(right)))
        node = parse_text(left or right)
        if not isinstance(node, Eq) and variable is not None and not free_vars(node):
            node = Eq(Var(variable), node)
        return Line(node)
    if left and right:
        a, b = _side(left), _side(right)
        return Line(b, false_equality=not equivalent(a, b))
    return Line(_side(left or right))


def _op_matches(prev: Eq, op: tuple[BinOp, sympy.Expr], nxt: Eq) -> bool:
    sign, operand = op
    try:
        sides = (
            apply_op(sign, to_sympy(prev.left), operand),
            apply_op(sign, to_sympy(prev.right), operand),
        )
        return same_value(sides[0], to_sympy(nxt.left)) and same_value(
            sides[1], to_sympy(nxt.right)
        )
    except MathError:
        return False


@dataclass(frozen=True)
class StepCheck:
    equivalent: bool
    identical: bool
    op_ok: bool | None

    @property
    def ok(self) -> bool:
        """A worked-example step must keep the value and change the writing."""
        return self.equivalent and not self.identical and self.op_ok is not False


def check_step(prev: Step, nxt: Step, kind: Kind = "solve") -> StepCheck:
    """Compare two consecutive lines. `prev.op` (if any) must turn `prev` into `nxt`."""
    variable = _single_var(prev, kind)
    a, b = parse_line(prev, kind, variable), parse_line(nxt, kind, variable)
    op = parse_op(prev.op)
    op_ok: bool | None = None
    if op is not None and isinstance(a.node, Eq) and isinstance(b.node, Eq):
        op_ok = _op_matches(a.node, op, b.node)
    return StepCheck(
        equivalent=not b.false_equality and equivalent(a.node, b.node),
        identical=a.node == b.node,
        op_ok=op_ok,
    )


def _single_var(step: Step, kind: Kind) -> str | None:
    if kind != "solve":
        return None
    names: set[str] = set()
    for text in (step.left, step.right):
        if text.strip():
            names |= free_vars(parse_text(text))
    return next(iter(names)) if len(names) == 1 else None


StepIssueReason = Literal[
    "unparsable",
    "false_equality",
    "not_equivalent",
    "identical",
    "op_mismatch",
    "wrong_answer",
    "not_simplified",
]


@dataclass(frozen=True)
class StepIssue:
    index: int
    reason: StepIssueReason
    detail: str = ""


def check_steps(problem: Problem, steps: list[Step]) -> list[StepIssue]:
    """Every issue in a worked example, for `pipeline/verify.py`. Empty means it passes.

    Step 0 must be equivalent to the problem (restating it is fine). Every later step must be
    equivalent to the one before and written differently, and each margin op must produce the
    next line. The last step must be the answer in simplest form.
    """
    solution = solve(problem)
    variable = solution.variable
    issues: list[StepIssue] = []
    lines: list[Line | None] = []
    for index, step in enumerate(steps):
        try:
            line = parse_line(step, problem.kind, variable)
            parse_op(step.op)
        except MathError as err:
            issues.append(StepIssue(index, "unparsable", str(err)))
            lines.append(None)
            continue
        if line.false_equality:
            issues.append(StepIssue(index, "false_equality"))
        lines.append(line)

    previous: Node = problem.node()
    for index, parsed in enumerate(lines):
        if parsed is None:
            return issues
        node = parsed.node
        if not equivalent(previous, node):
            issues.append(StepIssue(index, "not_equivalent"))
        elif index > 0:
            if previous == node:
                issues.append(StepIssue(index, "identical"))
            op = parse_op(steps[index - 1].op)
            if (
                op is not None
                and isinstance(previous, Eq)
                and isinstance(node, Eq)
                and not _op_matches(previous, op, node)
            ):
                issues.append(StepIssue(index, "op_mismatch"))
        previous = node

    if lines and (last := lines[-1]) is not None:
        issues.extend(_final_issues(problem, last.node, len(lines) - 1, solution.value))
    return issues


def _final_issues(
    problem: Problem, node: Node, index: int, value: sympy.Expr | None
) -> list[StepIssue]:
    if problem.kind == "solve":
        if not isinstance(node, Eq) or (iso := isolated(node)) is None:
            return [StepIssue(index, "not_simplified", "the last line must be `x = value`")]
        node = iso[1]
    if value is None:
        return []
    try:
        if not same_value(to_sympy(node), value):
            return [StepIssue(index, "wrong_answer")]
    except MathError:
        return [StepIssue(index, "wrong_answer")]
    if not is_canonical(node, allow_decimals=problem.allows_decimals):
        return [StepIssue(index, "not_simplified")]
    return []


LineReason = Literal["unparsable", "false_equality", "not_equivalent"]


@dataclass(frozen=True)
class LineFinding:
    index: int
    reason: LineReason


def first_line_that_doesnt_follow(
    lines: list[Step], problem: Problem | None = None
) -> LineFinding | None:
    """The first line that is not equivalent to the line before it, or None if all follow.

    With a problem, line 0 is compared with the problem. Copying a line again is fine here:
    only worked examples must change every line.
    """
    if problem is not None:
        kind: Kind = problem.kind
        previous: Node | None = problem.node()
        variable = solve(problem).variable if kind == "solve" else None
    else:
        kind = (
            "solve"
            if any(s.left.strip() and s.right.strip() and _has_letter(s) for s in lines)
            else "evaluate"
        )
        previous, variable = None, None
    for index, step in enumerate(lines):
        try:
            if variable is None and kind == "solve":
                variable = _single_var(step, kind)
            line = parse_line(step, kind, variable)
        except MathError:
            return LineFinding(index, "unparsable")
        if line.false_equality:
            return LineFinding(index, "false_equality")
        if previous is not None and not equivalent(previous, line.node):
            return LineFinding(index, "not_equivalent")
        previous = line.node
    return None


def _has_letter(step: Step) -> bool:
    try:
        return bool(free_vars(parse_text(step.left)) or free_vars(parse_text(step.right)))
    except MathError:
        return False
