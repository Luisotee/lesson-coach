"""A small parser for grade 6-9 math in plain text. It never calls `eval`.

Grammar (`-` binds looser than `^`, so `-2^2 = -4`):

    equation := expr ("=" expr)?
    expr     := term (("+" | "-") term)*
    term     := unary (("*" | "/") unary | implicit power)*
    unary    := ("-" | "+") unary | power
    power    := atom ("^" exponent)?          exponent: a whole number, |e| <= MAX_EXPONENT
    atom     := number | mixed | letter | "(" expr ")"

Implicit multiplication covers `2x`, `2(x+1)`, `xy` and `(x+1)(x-1)`. Variables are single
letters, and three letters in a row are rejected as a word. Unicode `−`, `×`, `·`, `÷`
and `**` are accepted, as is a decimal comma (`0,5`).
A mixed number is written `1 1/2`, or `1⁤1/2` with U+2064 INVISIBLE PLUS (what the LaTeX
converter emits for `1\\frac{1}{2}`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.math.nodes import (
    Bin,
    BinOp,
    Eq,
    MathParseError,
    Mixed,
    Neg,
    Node,
    Num,
    Pow,
    UnsupportedProblem,
    Var,
    free_vars,
)

MAX_LENGTH = 200
MAX_DEPTH = 20
MAX_DIGITS = 12
MAX_EXPONENT = 10
# Grades 6-9 need one or two letters. With at most 2 letters and degree 20, an expanded
# polynomial has at most 231 terms, which sympy handles in milliseconds.
MAX_LETTERS = 2
MAX_DEGREE = 20
MAX_BITS = 20_000
MIXED_MARK = "⁤"

REPLACEMENTS = {
    "−": "-",
    "–": "-",
    "×": "*",
    "·": "*",
    "⋅": "*",
    "∙": "*",
    "÷": "/",
    ":": "/",
}
# Three letters in a row is a word ("half"), not a product of unknowns.
_WORD = re.compile(r"[A-Za-z]{3}")
_TOKEN = re.compile(
    rf"(?P<num>\d+(?:[.,]\d+)?)|(?P<var>[A-Za-z])|(?P<pow>\*\*)|(?P<op>[-+*/^=()])|(?P<mix>{MIXED_MARK})"
)


@dataclass(frozen=True)
class Token:
    kind: Literal["num", "var", "op", "mix", "end"]
    text: str
    space_before: bool


def tokenize(text: str) -> list[Token]:
    if len(text) > MAX_LENGTH:
        raise MathParseError(f"input is longer than {MAX_LENGTH} characters")
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    if _WORD.search(text):
        raise MathParseError("words are not math: use one letter per unknown")
    tokens: list[Token] = []
    pos = 0
    space = False
    while pos < len(text):
        if text[pos].isspace():
            space = True
            pos += 1
            continue
        m = _TOKEN.match(text, pos)
        if m is None:
            raise MathParseError(f"unexpected character {text[pos]!r}")
        kind = m.lastgroup
        value = m.group()
        if kind == "num":
            value = value.replace(",", ".")
            if len(value.replace(".", "")) > MAX_DIGITS:
                raise MathParseError(f"numbers may have at most {MAX_DIGITS} digits")
            tokens.append(Token("num", value, space))
        elif kind == "var":
            tokens.append(Token("var", value, space))
        elif kind == "pow":
            tokens.append(Token("op", "^", space))
        elif kind == "mix":
            tokens.append(Token("mix", value, space))
        else:
            tokens.append(Token("op", value, space))
        space = False
        pos = m.end()
    tokens.append(Token("end", "", space))
    return tokens


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def next(self) -> Token:
        tok = self.peek()
        self.pos += 1
        return tok

    def at_op(self, *ops: str) -> bool:
        tok = self.peek()
        return tok.kind == "op" and tok.text in ops

    def expect_op(self, op: str) -> None:
        if not self.at_op(op):
            raise MathParseError(f"expected {op!r}")
        self.pos += 1

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise MathParseError("the expression is nested too deeply")

    def equation(self) -> Node:
        left = self.expr()
        if self.at_op("="):
            self.pos += 1
            right = self.expr()
            node: Node = Eq(left, right)
        else:
            node = left
        if self.peek().kind != "end":
            raise MathParseError(f"unexpected {self.peek().text!r}")
        return node

    def expr(self) -> Node:
        node = self.term()
        while self.at_op("+", "-"):
            op: BinOp = "+" if self.next().text == "+" else "-"
            node = Bin(op, node, self.term())
        return node

    def term(self) -> Node:
        node = self.unary()
        while True:
            if self.at_op("*", "/"):
                op: BinOp = "*" if self.next().text == "*" else "/"
                node = Bin(op, node, self.unary())
            elif self.peek().kind == "var" or self.at_op("("):
                node = Bin("*", node, self.power())
            else:
                return node

    def unary(self) -> Node:
        if self.at_op("-", "+"):
            sign = self.next().text
            self.enter()
            arg = self.unary()
            self.depth -= 1
            return Neg(arg) if sign == "-" else arg
        return self.power()

    def power(self) -> Node:
        base = self.atom()
        if self.at_op("^"):
            self.pos += 1
            if _is_power(base):
                # (2^10)^10 nested 20 deep would be 2^(10^20). Other large powers are caught
                # by check_size.
                raise MathParseError("a power of a power is not supported")
            return Pow(base, self.exponent())
        return base

    def exponent(self) -> int:
        bracketed = self.at_op("(")
        if bracketed:
            self.pos += 1
        sign = 1
        if self.at_op("-", "+"):
            sign = -1 if self.next().text == "-" else 1
        tok = self.next()
        if tok.kind != "num" or "." in tok.text:
            raise MathParseError("an exponent must be a whole number")
        if bracketed:
            self.expect_op(")")
        value = sign * int(tok.text)
        if abs(value) > MAX_EXPONENT:
            raise MathParseError(f"exponents may be at most {MAX_EXPONENT}")
        return value

    def atom(self) -> Node:
        tok = self.next()
        if tok.kind == "num":
            mixed = self.mixed_rest(tok)
            return mixed if mixed is not None else Num(tok.text)
        if tok.kind == "var":
            return Var(tok.text)
        if tok.kind == "op" and tok.text == "(":
            self.enter()
            node = self.expr()
            self.expect_op(")")
            self.depth -= 1
            return node
        raise MathParseError("expected a number, a letter or '('" if tok.kind != "end" else "")

    def mixed_rest(self, whole: Token) -> Mixed | None:
        """`1 1/2` or `1⁤1/2` after the whole number `whole`; None when it isn't one."""
        first = self.peek()
        marked = first.kind == "mix"
        offset = 1 if marked else 0
        num, slash, den = self.peek(offset), self.peek(offset + 1), self.peek(offset + 2)
        shape = (
            num.kind == "num"
            and slash.kind == "op"
            and slash.text == "/"
            and den.kind == "num"
            and (marked or num.space_before)
        )
        if not shape:
            if marked:
                raise MathParseError("a mixed number needs a fraction after the whole number")
            return None
        if not all(t.text.isdigit() for t in (whole, num, den)):
            raise MathParseError("a mixed number is written with whole numbers")
        if int(den.text) == 0:
            raise MathParseError("a fraction can't have 0 at the bottom")
        self.pos += offset + 3
        return Mixed(int(whole.text), int(num.text), int(den.text))


def _is_power(node: Node) -> bool:
    return isinstance(node, Pow) or (isinstance(node, Neg) and _is_power(node.arg))


def _size(node: Node) -> tuple[int, float]:
    """An upper bound on the expanded degree, and on the bits of the largest number."""
    match node:
        case Num(text):
            return 0, len(text) * 3.33
        case Mixed(whole, num, den):
            return 0, (len(str(whole)) + len(str(num)) + 2 * len(str(den))) * 3.33
        case Var():
            return 1, 1.0
        case Neg(arg):
            return _size(arg)
        case Bin(op, left, right):
            (dl, bl), (dr, br) = _size(left), _size(right)
            if op in ("+", "-"):
                return max(dl, dr), max(bl, br) + 1
            return dl + dr, bl + br
        case Pow(base, exp):
            d, b = _size(base)
            return d * abs(exp), b * abs(exp)
        case Eq(left, right):
            (dl, bl), (dr, br) = _size(left), _size(right)
            return max(dl, dr), max(bl, br)


def check_size(node: Node) -> None:
    """Refuse math whose expansion would be too slow: too many letters, degree or digits."""
    letters = free_vars(node)
    if len(letters) > MAX_LETTERS:
        raise UnsupportedProblem(f"use at most {MAX_LETTERS} different letters")
    degree, bits = _size(node)
    if degree > MAX_DEGREE or bits > MAX_BITS:
        raise UnsupportedProblem("the expression is too large to work out")


def parse_text(text: str) -> Node:
    """Parse plain-text math into a tree that keeps its written form."""
    tokens = tokenize(text)
    if tokens[0].kind == "end":
        raise MathParseError("the input is empty")
    try:
        node = _Parser(tokens).equation()
    except MathParseError as err:
        if not str(err):
            raise MathParseError("the input ends too early") from None
        raise
    check_size(node)
    return node
