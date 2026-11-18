"""A deterministic check that the LLM's free text adds no math of its own.

"Never show unverified math": every number or simple fraction in the AI's text must have
the value of one that appears in what it was given (problem, student answer and working,
sympy's answer and worked steps, the chosen follow-up). Signs are ignored, and so are 0 and
1, which are part of ordinary words ("one step"). A text that fails is not shown.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import sympy

# 3, 3.5, 3,5, 1/2, 10 / 12 (not the 2 in x2 or the parts of a date-like 1.2.3).
NUMBER = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(?:\s*/\s*(\d+(?:[.,]\d+)?))?(?![\w])")
ALWAYS_ALLOWED = {sympy.Integer(0), sympy.Integer(1)}


def _value(text: str) -> sympy.Rational:
    return sympy.Rational(text.replace(",", "."))


def numbers_in(text: str) -> set[sympy.Rational]:
    """The values of the numbers and simple fractions in `text`, and of each part of a
    fraction (so `3/6` in the input also allows `3` and `6`)."""
    values: set[sympy.Rational] = set()
    for match in NUMBER.finditer(text):
        top, bottom = match.group(1), match.group(2)
        values.add(abs(_value(top)))
        if bottom is not None:
            values.add(abs(_value(bottom)))
            if _value(bottom) != 0:
                values.add(abs(_value(top) / _value(bottom)))
    return values


def new_numbers(texts: Iterable[str], given: Iterable[str]) -> set[sympy.Rational]:
    """Values in `texts` that appear nowhere in `given`. Empty means the text passes."""
    allowed = set(ALWAYS_ALLOWED)
    for text in given:
        allowed |= numbers_in(text)
    found: set[sympy.Rational] = set()
    for text in texts:
        for match in NUMBER.finditer(text):
            top, bottom = match.group(1), match.group(2)
            value = abs(_value(top) / _value(bottom)) if bottom and _value(bottom) != 0 else None
            if value is not None and value in allowed:
                continue  # a fraction whose value was given (3/6 for 1/2 is fine)
            parts = [abs(_value(top))] + ([abs(_value(bottom))] if bottom else [])
            found |= {p for p in parts if p not in allowed}
    return found
