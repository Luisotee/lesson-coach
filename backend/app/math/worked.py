"""The correct solution as written lines, built by sympy (never by the LLM).

Shapes our topics use get real steps: a linear equation in one letter, a sum or difference of
two fractions, and `a - (-b)`. Anything else gets the problem and its answer. Every list is
checked with `check_steps` before it is returned, so a generator bug falls back instead of
showing wrong math.
"""

from __future__ import annotations

from math import gcd

import sympy

from app.math.nodes import Bin, Eq, MathError, Neg, Node, Num, render, to_sympy
from app.math.problems import Problem, Solution, Step, format_value, linear_form, solve
from app.math.steps import check_steps


def worked_solution(problem: Problem) -> list[Step]:
    """Verified steps from the problem to its answer. Raises MathError if it can't be solved."""
    solution = solve(problem)
    node = problem.node()
    fallback = _fallback(node, solution)
    try:
        steps = _generate(node, solution)
    except MathError:
        steps = None
    if steps and not check_steps(problem, steps):
        return steps
    return fallback if not check_steps(problem, fallback) else []


def _fallback(node: Node, solution: Solution) -> list[Step]:
    if isinstance(node, Eq):
        if solution.variable is None or solution.value is None:
            return []
        return [
            Step(render(node.left), render(node.right)),
            Step(solution.variable, format_value(solution.value)),
        ]
    return [Step(render(node), solution.answer_text)]


def _generate(node: Node, solution: Solution) -> list[Step] | None:
    if isinstance(node, Eq):
        return _linear_steps(node, solution)
    if solution.value is None or solution.value.free_symbols:
        return None
    return _fraction_steps(node) or _minus_negative_steps(node)


def _num(value: sympy.Expr) -> str:
    return format_value(value)


def _term(coeff: sympy.Expr, var: str) -> str:
    """`3*x`, `x`, `-x`, `x/2`, `3*x/2`, as plain text."""
    return format_value(coeff * sympy.Symbol(var))


def _side(coeff: sympy.Expr, const: sympy.Expr, var: str) -> str:
    return format_value(coeff * sympy.Symbol(var) + const)


def _subtract_op(value: sympy.Expr, var: str | None = None) -> str:
    """The margin op that takes `value` (a number, or value·var) away: `-6`, `+4`, `-3*x`."""
    text = _term(abs(value), var) if var else _num(abs(value))
    return f"+{text}" if value < 0 else f"-{text}"


def _divide_op(a: sympy.Expr) -> str:
    if a.is_Integer:
        return f"/{a}" if a > 0 else f"/({a})"
    inverse = 1 / a
    text = _num(inverse)
    return f"*{text}" if inverse.is_Integer and inverse > 0 else f"*({text})"


def _linear_steps(eq: Eq, solution: Solution) -> list[Step] | None:
    if solution.kind != "value" or solution.variable is None:
        return None
    lin = linear_form(eq)
    x = solution.variable
    a_l, b_l, a_r, b_r = lin.a_left, lin.b_left, lin.a_right, lin.b_right
    lines: list[tuple[str, str]] = [(render(eq.left), render(eq.right))]
    ops: list[str] = []
    if a_l != 0 and a_r != 0:
        ops.append(_subtract_op(a_r, x))
        a_l, a_r = a_l - a_r, sympy.Integer(0)
        lines.append((_side(a_l, b_l, x), _side(a_r, b_r, x)))
    # Now x is on one side only: keep track of which.
    x_left = a_l != 0
    a = a_l if x_left else a_r
    b_x = b_l if x_left else b_r  # the constant next to x
    if b_x != 0:
        ops.append(_subtract_op(b_x))
        if x_left:
            b_l, b_r = sympy.Integer(0), b_r - b_x
        else:
            b_r, b_l = sympy.Integer(0), b_l - b_x
        lines.append((_side(a_l, b_l, x), _side(a_r, b_r, x)))
    if a != 1:
        ops.append(_divide_op(a))
        value = solution.value
        assert value is not None
        lines.append((x, _num(value)) if x_left else (_num(value), x))
    if not x_left:
        lines.append((x, _num(solution.value)))  # read `5 = x` as `x = 5`
        ops.append("")
    ops.append("")
    return [Step(left, right, op) for (left, right), op in zip(lines, ops, strict=False)]


def _fraction(node: Node) -> tuple[int, int] | None:
    if isinstance(node, Neg) and (inner := _fraction(node.arg)) is not None:
        return -inner[0], inner[1]
    if isinstance(node, Bin) and node.op == "/":
        top, bottom = node.left, node.right
        if isinstance(top, Neg) and isinstance(top.arg, Num):
            top_value = -int(top.arg.text) if top.arg.is_integer else None
        elif isinstance(top, Num) and top.is_integer:
            top_value = int(top.text)
        else:
            top_value = None
        if top_value is not None and isinstance(bottom, Num) and bottom.is_integer:
            return top_value, int(bottom.text)
    return None


def _fraction_steps(node: Node) -> list[Step] | None:
    """`a/b ± c/d`: rewrite over the common denominator, combine, then simplify."""
    if not (isinstance(node, Bin) and node.op in ("+", "-")):
        return None
    left, right = _fraction(node.left), _fraction(node.right)
    if left is None or right is None or 0 in (left[1], right[1]):
        return None
    (a, b), (c, d) = left, right
    common = b * d // gcd(b, d)
    lines = [render(node)]
    if b != d:
        lines.append(f"{a * common // b}/{common} {node.op} {c * common // d}/{common}")
    top = a * common // b + (c if node.op == "+" else -c) * common // d
    lines.append(f"{top}/{common}")
    value = sympy.Rational(top, common)
    if value.q != common or value.p != top:
        lines.append(_num(value))
    return [Step(line) for line in lines]


def _minus_negative_steps(node: Node) -> list[Step] | None:
    """`a - (-b)` becomes `a + b`."""
    if not (isinstance(node, Bin) and node.op == "-" and isinstance(node.right, Neg)):
        return None
    plus = Bin("+", node.left, node.right.arg)
    return [Step(render(node)), Step(render(plus)), Step(_num(to_sympy(node)))]
