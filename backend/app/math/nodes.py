"""The written form of a math expression, and its exact value through sympy.

The tree keeps what the person wrote: `2/4` is not `1/2`, `1/2 + 1/3` is not `5/6`, and
`5 - (-3)` is not `5 + 3`. Brackets are not nodes, so `(2)+3` and `2+3` are the same tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import sympy

BinOp = Literal["+", "-", "*", "/"]


class MathError(ValueError):
    """Math input that can't be used: unparsable, too large, or undefined (division by zero)."""


class MathParseError(MathError):
    """The input is not math we can read, or it breaks a size guard."""


class UndefinedValue(MathError):
    """The expression has no value, for example a division by zero."""


@dataclass(frozen=True)
class Num:
    """A non-negative number literal as written: digits, optionally with a decimal point."""

    text: str

    @property
    def is_integer(self) -> bool:
        return "." not in self.text


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Neg:
    arg: Node


@dataclass(frozen=True)
class Bin:
    op: BinOp
    left: Node
    right: Node


@dataclass(frozen=True)
class Pow:
    base: Node
    exp: int


@dataclass(frozen=True)
class Mixed:
    """A mixed number such as 1 1/2."""

    whole: int
    num: int
    den: int


@dataclass(frozen=True)
class Eq:
    left: Node
    right: Node


Node = Num | Var | Neg | Bin | Pow | Mixed | Eq

_UNDEFINED = (sympy.zoo, sympy.nan, sympy.oo, -sympy.oo)


def checked(value: sympy.Expr) -> sympy.Expr:
    """Raise UndefinedValue when sympy's result is infinite or undefined."""
    if value.has(*_UNDEFINED):
        raise UndefinedValue("the expression has no value (division by zero)")
    return value


def to_sympy(node: Node) -> sympy.Expr:
    """The exact value of an expression (not an equation)."""
    match node:
        case Num(text):
            return sympy.Rational(text)
        case Var(name):
            return sympy.Symbol(name)
        case Neg(arg):
            return -to_sympy(arg)
        case Bin(op, left, right):
            return apply_op(op, to_sympy(left), to_sympy(right))
        case Pow(base, exp):
            return checked(sympy.Pow(to_sympy(base), exp))
        case Mixed(whole, num, den):
            return sympy.Integer(whole) + sympy.Rational(num, den)
        case Eq():
            raise MathError("an equation has no single value")


def apply_op(op: BinOp, a: sympy.Expr, b: sympy.Expr) -> sympy.Expr:
    """Apply one of + - * / to two exact values."""
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if b == 0:
        raise UndefinedValue("division by zero")
    return checked(a / b)


def free_vars(node: Node) -> set[str]:
    match node:
        case Var(name):
            return {name}
        case Neg(arg):
            return free_vars(arg)
        case Bin(_, left, right) | Eq(left, right):
            return free_vars(left) | free_vars(right)
        case Pow(base, _):
            return free_vars(base)
        case _:
            return set()


_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2}


def render(node: Node) -> str:
    """Plain text with only the brackets the tree needs."""
    match node:
        case Num(text):
            return text
        case Var(name):
            return name
        case Mixed(whole, num, den):
            return f"{whole} {num}/{den}"
        case Eq(left, right):
            return f"{render(left)} = {render(right)}"
        case Neg(arg):
            inner = render(arg)
            return f"-({inner})" if isinstance(arg, Bin | Neg | Mixed) else f"-{inner}"
        case Pow(base, exp):
            b = render(base)
            if not isinstance(base, Num | Var):
                b = f"({b})"
            return f"{b}^{exp}" if exp >= 0 else f"{b}^({exp})"
        case Bin(op, left, right):
            prec = _PRECEDENCE[op]
            ls = render(left)
            if isinstance(left, Bin) and _PRECEDENCE[left.op] < prec:
                ls = f"({ls})"
            rs = render(right)
            if isinstance(right, Neg | Mixed) or (
                isinstance(right, Bin) and _PRECEDENCE[right.op] <= prec
            ):
                rs = f"({rs})"
            return f"{ls} {op} {rs}"
