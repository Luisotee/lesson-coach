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
    no_math = {"status": "unclear", "reason": "no_math", "lines": []}
    assert metrics.score_transcription(no_math, [])["image_ok"]
    outage = {"status": "unclear", "reason": "ai_unavailable", "lines": []}
    assert not metrics.score_transcription(outage, [])["image_ok"]
    assert not metrics.score_transcription({"detail": "x"}, [], http=500)["image_ok"]
    assert not metrics.score_transcription(result, truth, http=500)["right"]


def test_text_hash() -> None:
    text = {"explanation": "e", "margin_note": None, "what_to_say": {"nudge": "n"}}
    assert metrics.text_hash(text) == metrics.text_hash(dict(reversed(text.items())))
    assert metrics.text_hash(text) != metrics.text_hash(text | {"explanation": "f"})


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
    assert metrics.weighted_kappa(["yes"] * 3, ["yes"] * 3) is None  # undefined
    # Every label one step off in one direction: positive, but below perfect.
    b = ["yes", "to some extent", "to some extent", "yes", "no"]
    kappa = metrics.weighted_kappa(a, b)
    assert kappa is not None and 0 < kappa < 1
    opposite = metrics.weighted_kappa(["yes", "no"], ["no", "yes"])
    assert opposite is not None and opposite < 0


def test_quantile_and_cost() -> None:
    assert metrics.quantile([], 0.5) is None
    assert metrics.quantile([1, 2, 3, 4], 0.5) == 2.5
    assert metrics.quantile(list(range(11)), 0.9) == 9
    usage = {"prompt_tokens": 1000, "cached_tokens": 800, "completion_tokens": 100}
    # 200 fresh * 5.50 + 800 cached * 0.55 + 100 out * 33, per million tokens
    assert metrics.cost(usage, metrics.PRICES["data_zone"]) == pytest.approx(0.00484)


def test_summarize_refuses_partial_or_stale_rows() -> None:
    from evals import run

    path = Path("transcription-none.jsonl")
    stamp = fingerprint(labels=False)
    one_of_three = [{"image": i, "runs": 3, "fingerprint": stamp} for i in ("a", "b")]
    with pytest.raises(SystemExit, match="partial"):  # a budget stop after run 1
        run._check_complete(path, one_of_three, {"a", "b"})
    run._check_complete(path, one_of_three * 3, {"a", "b"})
    stale = [r | {"fingerprint": "old"} for r in one_of_three * 3]
    with pytest.raises(SystemExit, match="other prompts, code or inputs"):
        run._check_complete(path, stale, {"a", "b"})


def test_rule_path_fallback_reasons() -> None:
    from evals import run

    def record(say_example: object, reply: object, error: object = None) -> dict[str, object]:
        call = {"reply": reply, "error": error}
        return {"result": {"diagnosis": {"say_example": say_example}}, "calls": [call]}

    example = {"kind": "solve", "expr": "2*x + 6 = 10"}
    moves = {"probe": "p", "nudge": "n", "tell": "t"}
    assert run._fallback(record(None, {"abstain": False} | moves)) is None
    assert run._fallback(record(example, None, "deadline")) == "error:deadline"
    assert run._fallback(record(example, {"abstain": True} | moves)) == "abstained"
    blank = {"abstain": False} | moves | {"nudge": " "}
    assert run._fallback(record(example, blank)) == "blank_move"
    assert run._fallback(record(example, {"abstain": False} | moves)) == "unverified_math"


def test_raw_math() -> None:
    say = {"probe": "Why?", "nudge": "Look at line 2.", "tell": "So `x = 5`."}
    clean = {"explanation": "They kept the sign of `+ 5`.", "what_to_say": say}
    assert not metrics.raw_math(clean)
    for raw in ("So 3*x = 15.", "Use 1/2 here.", "so x = 5", "8 - 3 is 5", "`x = 5"):
        assert metrics.raw_math(clean | {"explanation": raw}), raw
    assert not metrics.raw_math(clean | {"explanation": "grade six, one step, 3 runs"})
