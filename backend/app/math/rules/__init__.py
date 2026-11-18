"""Misconception rules: each one reproduces the wrong answer a known wrong belief gives.

A rule that reproduces a student's answer is a diagnosis that needs no LLM call. Rules work on
any problem of their shape, not only on their example: an expression rule replaces the right
computation at the nodes it matches (at each one alone, and at all of them, since a student
may make the mistake once or every time).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import sympy

from app.math.nodes import (
    Bin,
    Eq,
    MathError,
    Mixed,
    Neg,
    Node,
    Num,
    Pow,
    Var,
    apply_op,
    checked,
    to_sympy,
)
from app.math.problems import (
    Format,
    Kind,
    Problem,
    isolated,
    parse_input,
    same_value,
    solution_set,
    solve,
)

Topic = str
TOPICS: tuple[Topic, ...] = ("negative-numbers", "fractions", "linear-equations")
MAX_MATCHED_NODES = 8
MAX_ALTERNATIVES = 4

Evaluate = Callable[[Node], sympy.Expr]


@dataclass(frozen=True)
class NodeRule:
    """Replaces the computation at nodes where `matches` is true by each of `alternatives`."""

    matches: Callable[[Node], bool]
    alternatives: Callable[[Node, Evaluate], list[sympy.Expr]]
    kinds: tuple[Kind, ...] = ("evaluate", "simplify")

    def candidates(self, problem: Problem) -> list[sympy.Expr]:
        if problem.kind not in self.kinds:
            return []
        root = problem.node()
        count = len(_matching(root, self.matches))
        if count == 0:
            return []
        results: list[sympy.Expr] = []
        targets: list[int | None] = [*range(min(count, MAX_MATCHED_NODES)), None]
        for alt in range(MAX_ALTERNATIVES):
            used = False
            for target in targets:
                try:
                    value, applied = self._evaluate(root, target, alt)
                except (MathError, _NoAlternative):
                    continue
                used = used or applied
                results.append(value)
            if not used:
                break  # no node has this many alternatives, so later ones won't either
        return results

    def _evaluate(self, root: Node, target: int | None, alt: int) -> tuple[sympy.Expr, bool]:
        """Evaluate with the rule at match number `target` (None: at every match).

        Each node is evaluated once (cached), so a long sum costs time linear in its length.
        Returns the value and whether an alternative was applied anywhere.
        """
        order = {id(node): i for i, node in enumerate(_matching(root, self.matches))}
        cache: dict[int, sympy.Expr] = {}
        applied = False

        def ev(node: Node) -> sympy.Expr:
            nonlocal applied
            key = id(node)
            if key in cache:
                return cache[key]
            index = order.get(key)
            value: sympy.Expr | None = None
            if index is not None and (target is None or target == index):
                options = self.alternatives(node, ev)
                if alt < len(options):
                    value = checked(options[alt])
                    applied = True
                elif target is not None:
                    raise _NoAlternative
            if value is None:
                value = _default(node, ev)
            cache[key] = value
            return value

        return ev(root), applied


class _NoAlternative(Exception):
    pass


def _matching(node: Node, matches: Callable[[Node], bool]) -> list[Node]:
    """The nodes a rule matches, in reading order (parents first)."""
    own = [node] if matches(node) else []
    match node:
        case Neg(arg) | Pow(arg, _):
            return own + _matching(arg, matches)
        case Bin(_, left, right) | Eq(left, right):
            return own + _matching(left, matches) + _matching(right, matches)
        case _:
            return own


def _default(node: Node, ev: Evaluate) -> sympy.Expr:
    match node:
        case Neg(arg):
            return -ev(arg)
        case Bin(op, left, right):
            return apply_op(op, ev(left), ev(right))
        case Pow(base, exp):
            return checked(sympy.Pow(ev(base), exp))
        case Num() | Var() | Mixed():
            return to_sympy(node)
        case Eq():
            raise MathError("an equation has no single value")


@dataclass(frozen=True)
class Rule:
    id: str
    topic: Topic
    summary: str
    example_problem: Problem
    example_wrong_answer: str
    candidates: Callable[[Problem], list[sympy.Expr]]


def _student_value(problem: Problem, node: Node) -> sympy.Expr | None:
    """The value the student's answer stands for: the expression's value, or x's value."""
    if problem.kind != "solve":
        return to_sympy(node.right if isinstance(node, Eq) else node)
    if isinstance(node, Eq):
        iso = isolated(node)
        if iso is not None:
            return to_sympy(iso[1])
        _, kind, value = solution_set(node)
        return value if kind == "value" else None
    return to_sympy(node)


def reproduces(rule: Rule, problem: Problem, answer: str, fmt: Format = "text") -> bool:
    """Whether the rule gives the student's answer, which must also differ from the right one."""
    try:
        correct = solve(problem).value
        student = _student_value(problem, parse_input(answer.strip().removeprefix("="), fmt))
        if student is None or (correct is not None and same_value(student, correct)):
            return False
        return any(
            not (correct is not None and same_value(c, correct)) and same_value(c, student)
            for c in rule.candidates(problem)
        )
    except MathError:
        return False


def _registry() -> dict[Topic, dict[str, Rule]]:
    from app.math.rules import fractions, linear_equations, negative_numbers

    registry: dict[Topic, dict[str, Rule]] = {}
    for module in (negative_numbers, fractions, linear_equations):
        for rule in module.RULES:
            registry.setdefault(rule.topic, {})[rule.id] = rule
    return registry


RULES: dict[Topic, dict[str, Rule]] = _registry()
ALL_RULES: dict[str, Rule] = {rid: r for rules in RULES.values() for rid, r in rules.items()}


def reproducing_rules(
    problem: Problem, answer: str, *, topic: Topic | None = None, fmt: Format = "text"
) -> list[str]:
    """The ids of the rules that reproduce the student's (wrong) answer, in registry order."""
    rules = ALL_RULES.values() if topic is None else RULES.get(topic, {}).values()
    return [rule.id for rule in rules if reproduces(rule, problem, answer, fmt)]


def rule_reproduces(rule_id: str, problem: Problem, answer: str, fmt: Format = "text") -> bool:
    """For `verify.py`: does the misconception's rule reproduce its example wrong answer?"""
    return reproduces(ALL_RULES[rule_id], problem, answer, fmt)
