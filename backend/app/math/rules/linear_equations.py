"""Rules for linear equations. Each gives the value of x that the wrong belief leads to.

The equation is read as `aL·x + bL = aR·x + bR` (sympy collects the terms); the right answer
is x = (bR - bL)/(aL - aR).
"""

from __future__ import annotations

from collections.abc import Callable

import sympy

from app.math.nodes import Bin, Eq, MathError, free_vars, to_sympy
from app.math.problems import LinearEquation, Problem, linear_form
from app.math.rules import Rule

TOPIC = "linear-equations"


def _candidates(
    build: Callable[[LinearEquation], list[tuple[sympy.Expr, sympy.Expr]]],
) -> Callable[[Problem], list[sympy.Expr]]:
    """Turn `build`, giving (A, C) pairs for wrong equations `A·x = C`, into values of x."""

    def candidates(problem: Problem) -> list[sympy.Expr]:
        if problem.kind != "solve":
            return []
        node = problem.node()
        assert isinstance(node, Eq)
        try:
            lin = linear_form(node)
        except MathError:
            return []
        if lin.variable is None:
            return []
        return [c / a for a, c in build(lin) if a != 0]

    return candidates


def _one_side(lin: LinearEquation) -> tuple[sympy.Expr, sympy.Expr, sympy.Expr] | None:
    """(A, B, C) for `A·x + B = C` when x is on one side only (either side)."""
    if lin.a_right == 0 and lin.a_left != 0:
        return lin.a_left, lin.b_left, lin.b_right
    if lin.a_left == 0 and lin.a_right != 0:
        return lin.a_right, lin.b_right, lin.b_left
    return None


def _sign_not_changed(lin: LinearEquation) -> list[tuple[sympy.Expr, sympy.Expr]]:
    a_l, b_l, a_r, b_r = lin.a_left, lin.b_left, lin.a_right, lin.b_right
    pairs = []
    if b_l != 0:  # the constant moved right without changing sign
        pairs.append((a_l - a_r, b_r + b_l))
    if a_r != 0 and a_l != 0:  # the x-term moved left without changing sign
        pairs.append((a_l + a_r, b_r - b_l))
        if b_l != 0:
            pairs.append((a_l + a_r, b_r + b_l))
    if a_l == 0 and b_r != 0:  # x on the right: the constant moved left without changing sign
        pairs.append((a_r, b_l + b_r))
    return pairs


def _divide_one_term(lin: LinearEquation) -> list[tuple[sympy.Expr, sympy.Expr]]:
    parts = _one_side(lin)
    if parts is None:
        return []
    a, b, c = parts
    if a == 1 or b == 0:
        return []
    # `x + B = C/A` (the constant not divided), or `x + B/A = C` (the other side not divided).
    return [(sympy.Integer(1), c / a - b), (sympy.Integer(1), c - b / a)]


def _subtract_instead_of_divide(lin: LinearEquation) -> list[tuple[sympy.Expr, sympy.Expr]]:
    parts = _one_side(lin)
    if parts is None:
        return []
    a, b, c = parts
    if not (a.is_Integer and abs(a) > 1):
        return []
    return [(sympy.Integer(1), (c - b) - a)]


def _wrong_inverse_order(problem: Problem) -> list[sympy.Expr]:
    """`(x + b)/a = c`: the student takes b away before undoing the division, so
    x/a = c - b and x = a(c - b). The right order gives x = a·c - b."""
    if problem.kind != "solve":
        return []
    node = problem.node()
    assert isinstance(node, Eq)
    results = []
    for side, other in ((node.left, node.right), (node.right, node.left)):
        if not (
            isinstance(side, Bin)
            and side.op == "/"
            and isinstance(side.left, Bin)
            and side.left.op in ("+", "-")
            and not free_vars(side.right)
            and not free_vars(other)
        ):
            continue
        top = side.left
        sign = 1 if top.op == "+" else -1
        if free_vars(top.left) and not free_vars(top.right):
            x_term, b = top.left, sign * to_sympy(top.right)
        elif free_vars(top.right) and not free_vars(top.left) and top.op == "+":
            x_term, b = top.right, to_sympy(top.left)
        else:
            continue
        try:
            a, c, k_x = to_sympy(side.right), to_sympy(other), to_sympy(x_term)
        except MathError:
            continue
        (name,) = free_vars(x_term)
        k = k_x.coeff(sympy.Symbol(name))
        if b == 0 or a == 0 or k == 0 or sympy.expand(k_x - k * sympy.Symbol(name)) != 0:
            continue
        results.append(a * (c - b) / k)
    return results


def _solve(expr: str) -> Problem:
    return Problem("solve", expr)


RULES = [
    Rule(
        "sign_not_changed",
        TOPIC,
        "A term moves to the other side without changing its sign: 2x + 6 = 10 gives 2x = 16.",
        _solve("2*x + 6 = 10"),
        "x = 8",
        _candidates(_sign_not_changed),
    ),
    Rule(
        "divide_one_term",
        TOPIC,
        "Only some terms are divided: 2x + 6 = 10 gives x + 6 = 5, so x = -1.",
        _solve("2*x + 6 = 10"),
        "x = -1",
        _candidates(_divide_one_term),
    ),
    Rule(
        "subtract_instead_of_divide",
        TOPIC,
        "The coefficient is subtracted instead of divided: 3x = 12 gives x = 9.",
        _solve("3*x = 12"),
        "x = 9",
        _candidates(_subtract_instead_of_divide),
    ),
    Rule(
        "wrong_inverse_order",
        TOPIC,
        "Operations are undone in the wrong order: (x + 6)/2 = 10 gives x/2 = 4, so x = 8.",
        _solve("(x + 6)/2 = 10"),
        "x = 8",
        _wrong_inverse_order,
    ),
]
