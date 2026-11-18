"""Pure scoring functions for the evals: no model calls. Tested in backend/tests/test_evals.py."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from app.math import parse_text
from app.math.nodes import MathError
from app.math.steps import parse_op

# USD per 1M tokens, gpt-5.5 short context, from the Azure retail prices API
# (https://prices.azure.com/api/retail/prices, meters "5.5 ShortCo ... Dz|Gl", 2026-11-18).
# Reasoning tokens are part of completion_tokens and billed as output.
PRICES = {
    "data_zone": {"input": 5.50, "cached": 0.55, "output": 33.00},  # gpt-5.5-live
    "global": {"input": 5.00, "cached": 0.50, "output": 30.00},  # gpt-5.5-offline
}

LEVELS = ("no", "to some extent", "yes")  # the judge's ordinal scale


def cost(usage: dict[str, int], prices: dict[str, float]) -> float:
    """The USD cost of one call."""
    fresh = usage["prompt_tokens"] - usage["cached_tokens"]
    return (
        fresh * prices["input"]
        + usage["cached_tokens"] * prices["cached"]
        + usage["completion_tokens"] * prices["output"]
    ) / 1e6


def quantile(values: Sequence[float], q: float) -> float | None:
    """The q-quantile by linear interpolation (q=0.5 is the median); None when empty."""
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def rate(hits: Iterable[bool]) -> float | None:
    """The share of True, or None when there is nothing to count."""
    items = list(hits)
    return round(sum(items) / len(items), 3) if items else None


def weighted_kappa(
    a: Sequence[str], b: Sequence[str], levels: Sequence[str] = LEVELS
) -> float | None:
    """Cohen's kappa with linear weights, for two raters on an ordinal scale.
    1 is perfect agreement, 0 is chance. When both raters give one and the same label to
    everything, kappa is undefined (None): the sample can't show whether the judge tells
    the levels apart."""
    if len(a) != len(b) or not a:
        raise ValueError("two equally long, non-empty label lists are needed")
    k = len(levels)
    index = {level: i for i, level in enumerate(levels)}
    n = len(a)
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        observed[index[x]][index[y]] += 1 / n
    row = [sum(observed[i]) for i in range(k)]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]
    weight = [[abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]
    disagree_obs = sum(weight[i][j] * observed[i][j] for i in range(k) for j in range(k))
    disagree_exp = sum(weight[i][j] * row[i] * col[j] for i in range(k) for j in range(k))
    if disagree_exp == 0:
        return None
    return 1 - disagree_obs / disagree_exp


def _same_math(got: str, want: str) -> bool:
    got, want = got.strip(), want.strip()
    if not want:
        return not got
    try:
        return parse_text(got) == parse_text(want)
    except MathError:
        return "".join(got.split()) == "".join(want.split())


def _same_op(got: str, want: str) -> bool:
    try:
        return parse_op(got) == parse_op(want)
    except MathError:
        return "".join(got.split()) == "".join(want.split())


def line_matches(got: dict[str, Any], want: dict[str, str]) -> bool:
    """A transcribed line equals the truth after our normalisation: each side parsed by our
    parser (which keeps the written form: `3x` = `3*x`, but `2/4` != `1/2`), the op by
    `parse_op`. Text that doesn't parse is compared without spaces."""
    return (
        _same_math(got.get("left") or "", want["left"])
        and _same_math(got.get("right") or "", want["right"])
        and _same_op(got.get("op") or "", want["op"])
    )


def score_transcription(result: dict[str, Any], truth: list[dict[str, str]]) -> dict[str, Any]:
    """Per image: lines right (by position), whether the whole image is right, and how many
    wrong lines the API flagged as uncertain (the teacher confirms those)."""
    got = result.get("lines") or []
    if not truth:
        ok = result.get("status") == "unclear" or not got
        return {"lines": 0, "right": 0, "image_ok": ok, "wrong": 0, "wrong_flagged": 0}
    right = wrong = flagged = 0
    for i in range(max(len(got), len(truth))):
        if i < len(got) and i < len(truth) and line_matches(got[i], truth[i]):
            right += 1
            continue
        wrong += 1
        flagged += int(i < len(got) and bool(got[i].get("uncertain")))
    return {
        "lines": len(truth),
        "right": right,
        "image_ok": right == len(truth) and len(got) == len(truth),
        "wrong": wrong,
        "wrong_flagged": flagged,
    }


EXPECTED_STATUS = {"correct": "correct", "equivalent_not_simplified": "not_simplified"}


def score_mistake(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """One run of one case against its expected classification, status and misconception."""
    classification = expected["classification"]
    want_status = EXPECTED_STATUS.get(classification) or expected["status"]
    diagnosis = result.get("diagnosis") or {}
    ids = [m["id"] for m in diagnosis.get("misconceptions") or []]
    want_id = expected.get("misconception_id")
    return {
        "verdict_ok": result.get("verdict") == classification
        or (result.get("status") == "out_of_scope" and want_status == "out_of_scope"),
        "status_ok": result.get("status") == want_status,
        "false_mistake": classification != "wrong"
        and result.get("status") not in ("correct", "not_simplified"),
        "id_ok": None if want_id is None else bool(ids) and ids[0] == want_id,
        "id_in_top2": None if want_id is None else want_id in ids,
        "outcome": f"{result.get('status')}:{','.join(ids) or result.get('reason') or ''}",
    }


def consistent(outcomes_by_case: dict[str, list[str]]) -> float | None:
    """The share of cases whose runs all gave the same outcome."""
    return rate(len(set(v)) == 1 for v in outcomes_by_case.values() if v)


def counts(values: Iterable[str | None]) -> dict[str, int]:
    return dict(sorted(Counter(v for v in values if v).items()))
