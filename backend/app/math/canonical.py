"""Is an answer written in its simplest form, and is it right?"""

from __future__ import annotations

from math import gcd
from typing import Literal

from app.math.nodes import (
    Bin,
    Eq,
    MathError,
    Mixed,
    Neg,
    Node,
    Num,
    Pow,
    UnsupportedProblem,
    Var,
    free_vars,
    to_sympy,
)
from app.math.problems import (
    Format,
    Problem,
    isolated,
    parse_input,
    same_value,
    solution_set,
    solve,
)

Verdict = Literal["correct", "equivalent_not_simplified", "wrong"]


def _int(node: Node) -> int | None:
    return int(node.text) if isinstance(node, Num) and node.is_integer else None


def _positive_number(node: Node, allow_decimals: bool) -> bool:
    """A non-zero number in simplest form, without a sign."""
    match node:
        case Num():
            return to_sympy(node) != 0 and (node.is_integer or allow_decimals)
        case Bin("/", top, bottom):
            p, q = _int(top), _int(bottom)
            return p is not None and q is not None and p > 0 and q > 1 and gcd(p, q) == 1
        case Mixed(whole, num, den):
            return whole >= 1 and 0 < num < den and gcd(num, den) == 1
        case _:
            return False


def _unsigned(node: Node) -> tuple[bool, Node]:
    """Pull a leading minus out: `-1/2` is read as `(-1)/2`, which is written as `-(1/2)`."""
    if isinstance(node, Neg):
        return True, node.arg
    if isinstance(node, Bin) and node.op in "*/":
        negative, left = _unsigned(node.left)
        if negative:
            return True, Bin(node.op, left, node.right)
    return False, node


def _number(node: Node, allow_decimals: bool) -> bool:
    if isinstance(node, Num) and to_sympy(node) == 0:
        return node.text == "0"
    negative, unsigned = _unsigned(node)
    if negative and to_sympy(unsigned) == 0:
        return False
    return _positive_number(unsigned, allow_decimals)


def _terms(node: Node) -> list[Node]:
    """The terms of a sum, with the sign of a subtracted term dropped."""
    if isinstance(node, Bin) and node.op in "+-":
        return [*_terms(node.left), node.right]
    return [_unsigned(node)[1]]


def _power_key(node: Node) -> tuple[str, int] | None:
    match node:
        case Var(name):
            return name, 1
        case Pow(Var(name), exp) if exp >= 2:
            return name, exp
        case _:
            return None


def _term_key(term: Node, allow_decimals: bool) -> tuple[str, int] | Literal[False] | None:
    """The letter and power of a simple term (`3x`, `x/2`, `3x/2`, `1/2 x`, `x^2`), None for a
    number, or False when the term isn't simple."""
    if _positive_number(term, allow_decimals):
        return None
    if (key := _power_key(term)) is not None:
        return key
    match term:
        case Bin("*", coeff, rest) if (
            _positive_number(coeff, allow_decimals) and to_sympy(coeff) != 1
        ):
            return _power_key(rest) or False
        case Bin("/", rest, Num() as den) if (q := _int(den) or 0) > 1:
            # `x/2`, or `3x/2` with a whole coefficient that shares no factor with 2.
            if isinstance(rest, Bin) and rest.op == "*" and (c := _int(rest.left)) is not None:
                return _power_key(rest.right) or False if c > 1 and gcd(c, q) == 1 else False
            return _power_key(rest) or False
        case _:
            return False


def is_canonical(node: Node, *, allow_decimals: bool = False) -> bool:
    """Whether an answer is in simplest form.

    Numbers: an integer, a reduced fraction with the sign in front (`-1/2`, not `1/-2` or
    `-2/4`), or a mixed number with a reduced proper fraction. Improper fractions count.
    Decimals count only when `allow_decimals`. With letters: a sum of simple terms (`3x`,
    `x/2`, `x^2`, a number) with no brackets and no two terms alike.
    """
    if isinstance(node, Eq):
        return False
    if not free_vars(node):
        return _number(node, allow_decimals)
    keys = []
    for index, term in enumerate(_terms(node)):
        if index > 0 and _unsigned(term)[0]:
            return False
        key = _term_key(term, allow_decimals)
        if key is False:
            return False
        keys.append(key)
    return len(keys) == len(set(keys))


def classify_answer(problem: Problem, answer: str, fmt: Format = "text") -> Verdict:
    """`correct`, `equivalent_not_simplified` or `wrong`.

    Raises MathParseError on unreadable input and UnsupportedProblem on math out of scope
    (in the problem or the answer); the caller abstains.

    For a solve problem, `x = 3`, `3 = x` and `3` are all correct; an equivalent equation that
    is not solved yet (`2x = 6`, `x = 6/2`) is `equivalent_not_simplified`. Problems with no
    solution or with every value as a solution raise UnsupportedProblem: there is no math
    syntax for "no solution", so the caller abstains.
    """
    solution = solve(problem)
    if solution.kind != "value":
        raise UnsupportedProblem(
            "answers to equations with no solution or every value as a solution are not graded"
        )
    node = parse_input(answer.strip().removeprefix("="), fmt)
    expected = solution.value
    assert expected is not None
    try:
        if problem.kind == "solve" and isinstance(node, Eq):
            iso = isolated(node)
            if iso is None:
                # An equation not solved yet: right when it has the same solution.
                var, kind, value = solution_set(node)
                same = kind == "value" and var == solution.variable and value is not None
                return (
                    "equivalent_not_simplified" if same and same_value(value, expected) else "wrong"
                )
            name, node = iso
            if name != solution.variable:
                return "wrong"
        elif isinstance(node, Eq):
            node = node.right  # `1/2 + 1/3 = 5/6`: the answer is the last side
        if problem.kind == "solve" and free_vars(node):
            return "wrong"
        if not same_value(to_sympy(node), expected):
            return "wrong"
    except UnsupportedProblem:
        raise  # an answer out of scope (a non-linear or rational equation): the caller abstains
    except MathError:
        return "wrong"  # an answer with no value, such as a division by zero
    simplest = is_canonical(node, allow_decimals=problem.allows_decimals)
    return "correct" if simplest else "equivalent_not_simplified"
