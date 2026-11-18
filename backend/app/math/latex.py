"""MathLive LaTeX to plain text, then the plain-text parser.

Only the subset a math field produces for grade 6-9 algebra is accepted; any other command is
an error rather than a guess. `\\frac{2}{4}` stays `2/4` (not `1/2`), and `1\\frac{1}{2}` is a
mixed number.
"""

from __future__ import annotations

import re

from app.math.nodes import MathParseError, Node
from app.math.parse import MAX_LENGTH, MIXED_MARK, parse_text

MAX_LATEX_LENGTH = 2 * MAX_LENGTH

_SYMBOLS = {
    "cdot": "*",
    "times": "*",
    "div": "/",
    "left": "",
    "right": "",
    ",": " ",
    ";": " ",
    ":": " ",
    "!": "",
    " ": " ",
    "quad": " ",
    "qquad": " ",
    "lparen": "(",
    "rparen": ")",
}
_FRACTIONS = {"frac", "dfrac", "tfrac"}
# A whole number (not an exponent or the end of a decimal) right before \frac.
_WHOLE_BEFORE = re.compile(r"(?:^|[^\d.^])\d+$")


class _Converter:
    def __init__(self, src: str) -> None:
        self.src = src
        self.pos = 0

    def command(self) -> str:
        """Read the command name after a backslash."""
        start = self.pos
        if self.pos < len(self.src) and self.src[self.pos].isalpha():
            while self.pos < len(self.src) and self.src[self.pos].isalpha():
                self.pos += 1
        elif self.pos < len(self.src):
            self.pos += 1
        name = self.src[start : self.pos]
        if not name:
            raise MathParseError("a backslash at the end of the input")
        return name

    def argument(self) -> str:
        """One argument of \\frac: a braced group, a command such as \\pi, or a single character."""
        while self.pos < len(self.src) and self.src[self.pos] == " ":
            self.pos += 1
        if self.pos >= len(self.src):
            raise MathParseError("\\frac needs two parts")
        ch = self.src[self.pos]
        if ch == "{":
            self.pos += 1
            return self.group(closing="}")
        if ch == "\\":
            raise MathParseError("write \\frac with braces: \\frac{a}{b}")
        self.pos += 1
        return ch

    def group(self, closing: str | None) -> str:
        out: list[str] = []
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if closing is not None and ch == closing:
                self.pos += 1
                return "".join(out)
            self.pos += 1
            if ch == "{" and self.src.startswith(",}", self.pos):
                # MathLive writes a decimal comma as `0{,}5`.
                self.pos += 2
                out.append(".")
            elif ch == "{":
                out.append("(" + self.group(closing="}") + ")")
            elif ch == "}":
                raise MathParseError("unbalanced braces")
            elif ch == "\\":
                out.append(self.translate(self.command(), "".join(out)))
            else:
                out.append(ch)
        if closing is not None:
            raise MathParseError("unbalanced braces")
        return "".join(out)

    def translate(self, name: str, before: str) -> str:
        if name in _SYMBOLS:
            return _SYMBOLS[name]
        if name in _FRACTIONS:
            top, bottom = self.argument().strip(), self.argument().strip()
            if top.isdigit() and bottom.isdigit():
                # A whole number written right before the fraction makes a mixed number.
                if _WHOLE_BEFORE.search(before):
                    return f"{MIXED_MARK}{top}/{bottom}"
                return f"({top}/{bottom})"
            return f"(({top})/({bottom}))"
        if name == "placeholder":
            raise MathParseError("the math has an empty box")
        raise MathParseError(f"unsupported LaTeX command \\{name}")


def latex_to_text(latex: str) -> str:
    if len(latex) > MAX_LATEX_LENGTH:
        raise MathParseError(f"input is longer than {MAX_LATEX_LENGTH} characters")
    return _Converter(latex).group(closing=None)


def parse_latex(latex: str) -> Node:
    """Parse MathLive LaTeX into a tree that keeps its written form."""
    return parse_text(latex_to_text(latex))
