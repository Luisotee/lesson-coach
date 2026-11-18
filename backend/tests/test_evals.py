"""The eval results are current, and the eval scoring is right. No model calls."""

from pathlib import Path

import pytest
import yaml
from evals import metrics
from evals.fingerprint import fingerprint

from app.math import parse_text

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals" / "results.yaml"


def test_results_are_current() -> None:
    if not RESULTS.exists():
        pytest.fail("evals/results.yaml is missing: run evals/run.py (see evals/README.md)")
    pinned = yaml.safe_load(RESULTS.read_text())["fingerprint"]
    assert pinned == fingerprint(), (
        "prompts, schemas, packs, config or eval inputs changed since the evals ran: rerun "
        "`uv run --project backend python evals/run.py run`, then `judge` and `summarize`"
    )


def test_truth_lines_parse() -> None:
    truth = yaml.safe_load((ROOT / "evals" / "transcription" / "truth.yaml").read_text())
    for image in truth["images"]:
        assert (ROOT / "evals" / "transcription" / image["file"]).is_file(), image["file"]
        for line in image["lines"]:
            parse_text(line["left"])
            if line["right"]:
                parse_text(line["right"])


@pytest.mark.parametrize(
    ("got", "want", "same"),
    [
        ({"left": "3x + 5", "right": "20", "op": "| -5"}, ("3*x + 5", "20", "-5"), True),
        ({"left": "(2/3)*9", "right": "6", "op": ""}, ("2/3*9", "6", ""), True),
        ({"left": "2/4", "right": "", "op": ""}, ("1/2", "", ""), False),  # written form kept
        ({"left": "3x + 5", "right": "20", "op": ""}, ("3*x + 5", "20", "-5"), False),
        ({"left": "3x + 5 =", "right": "", "op": ""}, ("3x + 5 =", "", ""), True),  # unparsable
        ({"left": "x", "right": "5", "op": None}, ("x", "5", ""), True),
    ],
)
def test_line_matches(got: dict[str, str], want: tuple[str, str, str], same: bool) -> None:
    left, right, op = want
    assert metrics.line_matches(got, {"left": left, "right": right, "op": op}) is same


def test_score_transcription() -> None:
    truth = [{"left": "3*x", "right": "15", "op": "/3"}, {"left": "x", "right": "5", "op": ""}]
    result = {
        "status": "ok",
        "lines": [
            {"left": "3x", "right": "15", "op": "/3", "uncertain": False},
            {"left": "x", "right": "6", "op": "", "uncertain": True},
            {"left": "y", "right": "1", "op": "", "uncertain": False},
        ],
    }
    score = metrics.score_transcription(result, truth)
    assert score == {"lines": 2, "right": 1, "image_ok": False, "wrong": 2, "wrong_flagged": 1}
    empty = metrics.score_transcription({"status": "unclear", "lines": []}, [])
    assert empty["image_ok"]


def test_score_mistake() -> None:
    expected = {"classification": "wrong", "status": "diagnosed", "misconception_id": "a"}
    result = {
        "status": "diagnosed",
        "verdict": "wrong",
        "diagnosis": {"misconceptions": [{"id": "b"}, {"id": "a"}]},
    }
    score = metrics.score_mistake(result, expected)
    assert (score["status_ok"], score["id_ok"], score["id_in_top2"]) == (True, False, True)
    control = metrics.score_mistake(
        {"status": "unclear", "verdict": "correct"}, {"classification": "correct"}
    )
    assert control["false_mistake"] and control["verdict_ok"] and not control["status_ok"]


def test_weighted_kappa() -> None:
    a = ["yes", "yes", "no", "to some extent", "no"]
    assert metrics.weighted_kappa(a, a) == 1.0
    assert metrics.weighted_kappa(["yes"] * 3, ["yes"] * 3) == 1.0
    # Every label one step off in one direction: positive, but below perfect.
    b = ["yes", "to some extent", "to some extent", "yes", "no"]
    assert 0 < metrics.weighted_kappa(a, b) < 1
    assert metrics.weighted_kappa(["yes", "no"], ["no", "yes"]) < 0


def test_quantile_and_cost() -> None:
    assert metrics.quantile([], 0.5) is None
    assert metrics.quantile([1, 2, 3, 4], 0.5) == 2.5
    assert metrics.quantile(list(range(11)), 0.9) == 9
    usage = {"prompt_tokens": 1000, "cached_tokens": 800, "completion_tokens": 100}
    # 200 fresh * 5.50 + 800 cached * 0.55 + 100 out * 33, per million tokens
    assert metrics.cost(usage, metrics.PRICES["data_zone"]) == pytest.approx(0.00484)
