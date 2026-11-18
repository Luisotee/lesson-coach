"""A deterministic check that the LLM's free text adds no math of its own.

"Never show unverified math": every number or simple fraction in the AI's text must have
the value of one in what it was given (the problem, the student's answer and working,
sympy's answer and worked steps, the misconception examples in the prompt, the chosen
follow-up), or be a line number. Signs are ignored, and so are 0 and 1, which are part of
ordinary words ("one step"). A text that fails is not shown.

It checks numbers only: a wrong claim built from given numbers ("1/2 + 1/3 = 2/5 is right")
still passes. The evals (T10) measure how often replies are held back.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import sympy

# Languages that write a decimal comma (0,5). Elsewhere "2,3" is two numbers.
DECIMAL_COMMA_LANGS = frozenset(
    {
        "de",
        "fr",
        "es",
        "pt",
        "it",
        "nl",
        "pl",
        "ru",
        "uk",
        "tr",
        "sv",
        "el",
        "kk",
        "fa",
        "prs",
        "ps",
    }
)
ALWAYS_ALLOWED = {sympy.Integer(0), sympy.Integer(1)}


def _pattern(decimal_comma: bool) -> re.Pattern[str]:
    """Numbers, decimals and simple fractions, including digits that touch a letter (`4x`,
    `x^2`), but not a digit run that continues another number (`1.2.3`)."""
    sep = "[.,]" if decimal_comma else r"\."
    number = rf"\d+(?:{sep}\d+)?"
    return re.compile(rf"(?<![\d.,])({number})(?:\s*/\s*({number}))?(?!\d)")


def decimal_comma(lang: str) -> bool:
    return lang.split("-")[0].lower() in DECIMAL_COMMA_LANGS


def _value(text: str) -> sympy.Rational:
    return sympy.Rational(text.replace(",", "."))


def numbers_in(text: str, comma: bool = False) -> set[sympy.Rational]:
    """The values of the numbers and simple fractions in `text`, and of each part of a
    fraction (so `3/6` in the input also allows `3` and `6`)."""
    values: set[sympy.Rational] = set()
    for match in _pattern(comma).finditer(text):
        top, bottom = match.group(1), match.group(2)
        values.add(abs(_value(top)))
        if bottom is not None:
            values.add(abs(_value(bottom)))
            if _value(bottom) != 0:
                values.add(abs(_value(top) / _value(bottom)))
    return values


def new_numbers(
    texts: Iterable[str], given: Iterable[str], *, lang: str = "en", line_count: int = 0
) -> set[sympy.Rational]:
    """Values in `texts` that appear nowhere in `given`. Empty means the text passes.
    `given` is our own plain-text math (decimal points); `texts` are in `lang`; the numbers
    1..`line_count` may name lines of the working."""
    allowed = set(ALWAYS_ALLOWED) | {sympy.Integer(n) for n in range(1, line_count + 1)}
    for text in given:
        allowed |= numbers_in(text)
    comma = decimal_comma(lang)
    found: set[sympy.Rational] = set()
    for text in texts:
        for match in _pattern(comma).finditer(text):
            top, bottom = match.group(1), match.group(2)
            if (
                bottom is not None
                and _value(bottom) != 0
                and abs(_value(top) / _value(bottom)) in allowed
            ):
                continue  # a fraction whose value was given (3/6 for 1/2 is fine)
            parts = [abs(_value(top))] + ([abs(_value(bottom))] if bottom else [])
            found |= {p for p in parts if p not in allowed}
    return found
