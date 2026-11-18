"""Rules for negative numbers."""

from __future__ import annotations

import sympy

from app.math.nodes import Bin, Neg, Node
from app.math.problems import Problem
from app.math.rules import Evaluate, NodeRule, Rule

TOPIC = "negative-numbers"


def _signed_operands(node: Node, ev: Evaluate) -> tuple[sympy.Expr, sympy.Expr] | None:
    """The two numbers a `+` or `-` combines, as signed numbers (`3 - 7` is 3 and -7), when
    their signs differ."""
    if not isinstance(node, Bin) or node.op not in ("+", "-"):
        return None
    a, b = ev(node.left), ev(node.right)
    if node.op == "-":
        b = -b
    if not (a.is_Rational and b.is_Rational) or a * b >= 0:
        return None
    return a, b


def _is_sum(node: Node) -> bool:
    return isinstance(node, Bin) and node.op in ("+", "-")


def _add_magnitudes(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    pair = _signed_operands(node, ev)
    if pair is None:
        return []
    a, b = pair
    total = abs(a) + abs(b)
    larger = a if abs(a) >= abs(b) else b
    return [sympy.sign(a) * total, sympy.sign(larger) * total]


def _subtract_smaller(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    pair = _signed_operands(node, ev)
    if pair is None:
        return []
    a, b = pair
    return [abs(abs(a) - abs(b))]


def _is_minus_negative(node: Node) -> bool:
    return isinstance(node, Bin) and node.op == "-" and isinstance(node.right, Neg)


def _minus_negative(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    assert isinstance(node, Bin) and isinstance(node.right, Neg)
    return [ev(node.left) - ev(node.right.arg)]


def _is_neg_times_neg(node: Node) -> bool:
    return (
        isinstance(node, Bin)
        and node.op in ("*", "/")
        and isinstance(node.left, Neg)
        and isinstance(node.right, Neg)
    )


def _neg_times_neg(node: Node, ev: Evaluate) -> list[sympy.Expr]:
    assert isinstance(node, Bin) and isinstance(node.left, Neg) and isinstance(node.right, Neg)
    a, b = ev(node.left.arg), ev(node.right.arg)
    return [-(a * b) if node.op == "*" else -(a / b)]


def _evaluate(expr: str) -> Problem:
    return Problem("evaluate", expr)


RULES = [
    Rule(
        "minus_negative_stays_minus",
        TOPIC,
        "Subtracting a negative number is treated as subtracting its size: a - (-b) = a - b.",
        _evaluate("5 - (-3)"),
        "2",
        NodeRule(_is_minus_negative, _minus_negative).candidates,
    ),
    Rule(
        "neg_times_neg_is_neg",
        TOPIC,
        "A negative times (or divided by) a negative is taken to be negative.",
        _evaluate("(-2) * (-3)"),
        "-6",
        NodeRule(_is_neg_times_neg, _neg_times_neg).candidates,
    ),
    Rule(
        "add_magnitudes_keep_sign",
        TOPIC,
        "With different signs, the sizes are added and a sign is kept: -5 + 3 = -8.",
        _evaluate("-5 + 3"),
        "-8",
        NodeRule(_is_sum, _add_magnitudes).candidates,
    ),
    Rule(
        "subtract_smaller_from_larger",
        TOPIC,
        "The smaller size is taken from the larger and the sign is dropped: 3 - 7 = 4.",
        _evaluate("3 - 7"),
        "4",
        NodeRule(_is_sum, _subtract_smaller).candidates,
    ),
]
