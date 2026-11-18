"""Problems, solutions and equivalence. sympy computes every value here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import sympy

from app.math.latex import parse_latex
from app.math.nodes import Eq, MathError, Node, Var, checked, free_vars, to_sympy
from app.math.parse import parse_text

Kind = Literal["evaluate", "simplify", "solve"]
Format = Literal["text", "latex"]
KINDS: tuple[Kind, ...] = ("evaluate", "simplify", "solve")


class UnsupportedProblem(MathError):
    """A problem the core can't solve exactly, such as a non-linear equation."""


@dataclass(frozen=True)
class Problem:
    """`{"kind": "solve", "expr": "2*x + 6 = 10"}`: the shared contract with content and API."""

    kind: Kind
    expr: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Problem:
        kind, expr = data.get("kind"), data.get("expr")
        if kind not in KINDS or not isinstance(expr, str):
            raise UnsupportedProblem(f"not a problem: {data!r}")
        return cls(kind, expr)

    def node(self) -> Node:
        node = parse_text(self.expr)
        if (self.kind == "solve") != isinstance(node, Eq):
            raise UnsupportedProblem(
                f"a {self.kind} problem needs {'an' if self.kind == 'solve' else 'no'} equation"
            )
        return node

    @property
    def allows_decimals(self) -> bool:
        return "." in self.expr or "," in self.expr


@dataclass(frozen=True)
class Step:
    """One written line: `left = right`, or one side only, with the margin op applied to it."""

    left: str
    right: str = ""
    op: str = ""


@dataclass(frozen=True)
class Solution:
    """`kind` is "value" for one answer, "none" when no value works, "all" when all do."""

    kind: Literal["value", "none", "all"]
    value: sympy.Expr | None
    variable: str | None
    answer_text: str


def parse_input(text: str, fmt: Format = "text") -> Node:
    return parse_latex(text) if fmt == "latex" else parse_text(text)


def format_value(value: sympy.Expr) -> str:
    """Plain text that sympy and our parser both read: `-1/2`, `5*x + 3`."""
    return str(value).replace("**", "^")


@dataclass(frozen=True)
class LinearEquation:
    """`a_left*x + b_left = a_right*x + b_right`. `variable` is None when there is no letter."""

    variable: str | None
    a_left: sympy.Expr
    b_left: sympy.Expr
    a_right: sympy.Expr
    b_right: sympy.Expr

    @property
    def solution(self) -> tuple[Literal["value", "none", "all"], sympy.Expr | None]:
        a = self.a_left - self.a_right
        c = self.b_right - self.b_left
        if a != 0:
            return "value", checked(c / a)
        return ("all", None) if c == 0 else ("none", None)


def linear_form(eq: Eq) -> LinearEquation:
    names = free_vars(eq)
    if len(names) > 1:
        raise UnsupportedProblem("equations with more than one letter are not supported")
    name = next(iter(names), None)
    left, right = to_sympy(eq.left), to_sympy(eq.right)
    if name is None:
        return LinearEquation(None, sympy.Integer(0), left, sympy.Integer(0), right)
    x = sympy.Symbol(name)
    coeffs = []
    for side in (left, right):
        try:
            poly = sympy.Poly(side, x)
        except sympy.PolynomialError as err:
            raise UnsupportedProblem("only linear equations are supported") from err
        if poly.degree() > 1:
            raise UnsupportedProblem("only linear equations are supported")
        coeffs.append((poly.coeff_monomial(x), poly.coeff_monomial(1)))
    (a_l, b_l), (a_r, b_r) = coeffs
    return LinearEquation(name, a_l, b_l, a_r, b_r)


def solve(problem: Problem) -> Solution:
    """The exact answer. Evaluate and simplify give a value; solve gives x's value (or none/all)."""
    node = problem.node()
    if not isinstance(node, Eq):
        value = to_sympy(node)
        if free_vars(node):
            value = sympy.expand(sympy.cancel(value))
        return Solution("value", value, None, format_value(value))
    lin = linear_form(node)
    kind, value = lin.solution
    if lin.variable is None:
        raise UnsupportedProblem("a solve problem needs a letter to solve for")
    if value is not None:
        return Solution(kind, value, lin.variable, f"{lin.variable} = {format_value(value)}")
    return Solution(kind, None, lin.variable, "no solution" if kind == "none" else "every value")


def same_value(a: sympy.Expr, b: sympy.Expr) -> bool:
    return bool(sympy.cancel(a - b) == 0)


def isolated(eq: Eq) -> tuple[str, Node] | None:
    """`x = c` or `c = x` with no letter in c: the letter and c."""
    for var, other in ((eq.left, eq.right), (eq.right, eq.left)):
        if isinstance(var, Var) and not free_vars(other):
            return var.name, other
    return None


def solution_set(eq: Eq) -> tuple[str | None, str, sympy.Expr | None]:
    lin = linear_form(eq)
    kind, value = lin.solution
    return lin.variable, kind, value


def equivalent(a: Node, b: Node) -> bool:
    """Same value (expressions) or same solutions (equations). `x = 3` is equivalent to `3`."""
    try:
        if isinstance(a, Eq) and isinstance(b, Eq):
            return _equations_equivalent(a, b)
        if isinstance(a, Eq) or isinstance(b, Eq):
            eq, expr = (a, b) if isinstance(a, Eq) else (b, a)
            assert isinstance(eq, Eq) and not isinstance(expr, Eq)
            iso = isolated(eq)
            return (
                iso is not None
                and not free_vars(expr)
                and same_value(to_sympy(iso[1]), to_sympy(expr))
            )
        return same_value(to_sympy(a), to_sympy(b))
    except MathError:
        return False


def _equations_equivalent(a: Eq, b: Eq) -> bool:
    try:
        var_a, kind_a, val_a = solution_set(a)
        var_b, kind_b, val_b = solution_set(b)
    except UnsupportedProblem:
        # Beyond linear: equivalent when lhs - rhs differ by a non-zero constant factor.
        da = to_sympy(a.left) - to_sympy(a.right)
        db = to_sympy(b.left) - to_sympy(b.right)
        if db == 0:
            return bool(da == 0)
        ratio = sympy.cancel(da / db)
        return not ratio.free_symbols and ratio != 0
    if kind_a != kind_b:
        return False
    if kind_a == "value":
        return (
            var_a == var_b and val_a is not None and val_b is not None and same_value(val_a, val_b)
        )
    return True
