"""Rules for fractions."""

from __future__ import annotations

import sympy

from app.math.nodes import Bin, Neg, Node, Num
from app.math.problems import Problem
from app.math.rules import Evaluate, NodeRule, Rule

TOPIC = "fractions"


def _whole(node: Node) -> int | None:
    if isinstance(node, Num) and node.is_integer:
        return int(node.text)
    if isinstance(node, Neg) and (value := _whole(node.arg)) is not None:
        return -value
    return None


def _fraction(node: Node) -> tuple[int, int] | None:
    """`a/b` with whole numbers, as (a, b); a sign in front goes on a."""
    if isinstance(node, Neg) and (inner := _fraction(node.arg)) is not None:
        return -inner[0], inner[1]
    if isinstance(node, Bin) and node.op == "/":
        top, bottom = _whole(node.left), _whole(node.right)
        if top is not None and bottom is not None:
            return top, bottom
    return None


def _fraction_or_whole(node: Node) -> tuple[int, int] | None:
    whole = _whole(node)
    return (whole, 1) if whole is not None else _fraction(node)


# add_tops_and_bottoms: a/b ± c/d = (a ± c)/(b ± d)


def _is_fraction_sum(node: Node) -> bool:
    return (
        isinstance(node, Bin)
        and node.op in ("+", "-")
        and _fraction(node.left) is not None
        and _fraction(node.right) is not None
    )


def _add_tops_and_bottoms(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    assert isinstance(node, Bin)
    (a, b), (c, d) = _fraction(node.left) or (0, 1), _fraction(node.right) or (0, 1)
    sign = 1 if node.op == "+" else -1
    bottom = b + sign * d
    return [sympy.Rational(a + sign * c, bottom)] if bottom != 0 else []


# multiply_both_by_whole: n × a/b = (n·a)/(n·b)


def _whole_times_fraction(node: Node) -> tuple[int, int, int] | None:
    """(n, a, b) for `n * a/b`, `a/b * n` or `n * a / b` (read as `(n*a)/b`)."""
    if not isinstance(node, Bin):
        return None
    if node.op == "*":
        for whole_node, frac_node in ((node.left, node.right), (node.right, node.left)):
            n, frac = _whole(whole_node), _fraction(frac_node)
            if n is not None and frac is not None:
                return n, frac[0], frac[1]
    if node.op == "/" and isinstance(node.left, Bin) and node.left.op == "*":
        n, a, b = _whole(node.left.left), _whole(node.left.right), _whole(node.right)
        if n is not None and a is not None and b is not None:
            return n, a, b
    return None


def _multiply_both(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    parts = _whole_times_fraction(node)
    if parts is None or parts[2] == 0:
        return []
    n, a, b = parts
    return [sympy.Rational(n * a, n * b)] if n != 0 else []


# flip_first_when_dividing: a/b ÷ c/d = b/a × c/d


def _is_fraction_division(node: Node) -> bool:
    if not isinstance(node, Bin) or node.op != "/":
        return False
    left, right = _fraction_or_whole(node.left), _fraction_or_whole(node.right)
    # Two whole numbers are just a fraction, not a division of fractions.
    return (
        left is not None
        and right is not None
        and not (_whole(node.left) is not None and _whole(node.right) is not None)
    )


def _flip_first(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    assert isinstance(node, Bin)
    (a, b), (c, d) = (
        _fraction_or_whole(node.left) or (0, 1),
        _fraction_or_whole(node.right) or (0, 1),
    )
    if a == 0 or d == 0:
        return []
    return [sympy.Rational(b, a) * sympy.Rational(c, d)]


# cancel_across_addition: (p ± q)/c = p/c ± q, or p ± q/c


def _is_sum_over(node: Node) -> bool:
    return (
        isinstance(node, Bin)
        and node.op == "/"
        and isinstance(node.left, Bin)
        and node.left.op in ("+", "-")
    )


def _cancel_one_term(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    assert isinstance(node, Bin) and isinstance(node.left, Bin)
    p, q, c = ev(node.left.left), ev(node.left.right), ev(node.right)
    if c == 0:
        return []
    sign = 1 if node.left.op == "+" else -1
    return [p / c + sign * q, p + sign * q / c]


RULES = [
    Rule(
        "add_tops_and_bottoms",
        TOPIC,
        "Fractions are added by adding the tops and adding the bottoms: 1/2 + 1/3 = 2/5.",
        Problem("evaluate", "1/2 + 1/3"),
        "2/5",
        NodeRule(_is_fraction_sum, _add_tops_and_bottoms).candidates,
    ),
    Rule(
        "multiply_both_by_whole",
        TOPIC,
        "A whole number multiplies both the top and the bottom: 3 × 2/5 = 6/15.",
        Problem("evaluate", "3 * 2/5"),
        "6/15",
        NodeRule(lambda n: _whole_times_fraction(n) is not None, _multiply_both).candidates,
    ),
    Rule(
        "flip_first_when_dividing",
        TOPIC,
        "When dividing fractions, the first fraction is flipped instead of the second.",
        Problem("evaluate", "(3/4) / (1/2)"),
        "2/3",
        NodeRule(_is_fraction_division, _flip_first).candidates,
    ),
    Rule(
        "cancel_across_addition",
        TOPIC,
        "Only one term of a sum is divided: (2 + 4)/2 = 2 + 2.",
        Problem("evaluate", "(2 + 4)/2"),
        "4",
        NodeRule(_is_sum_over, _cancel_one_term).candidates,
    ),
]
