"""Run the evals against the real app and the live model, then summarise them.

    uv run --project backend python evals/run.py run        # mistakes + transcription, live
    uv run --project backend python evals/run.py judge      # the LLM judge on the AI's text
    uv run --project backend python evals/run.py summarize  # results.yaml from the outputs

`run` sends every case through `POST /api/mistake` and every image through
`POST /api/transcribe` of `create_app()` (the real process pool, rules, guard and Azure
client), 3 times each, once per reasoning effort. It also runs an "AI only" mode on the
rule-labelled cases: the rule matches are hidden, so the LLM must name the misconception
itself. That measures the LLM, not the product (the product answers those cases by rule).

Each request's response, the LLM calls it made (tokens, latency, attempts) and the AI's raw
reply go to `evals/outputs/*.jsonl`. These hold only our synthetic cases and drawn images.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import datetime as dt
import json
import random
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, TypeVar, cast
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import app.api.mistake  # noqa: E402
from app.config import ReasoningEffort, Settings  # noqa: E402
from app.content.schema import RULE_IDS, TopicId  # noqa: E402
from app.llm.azure import AzureLLM  # noqa: E402
from app.llm.client import LLM, LLMResult, Task, Usage  # noqa: E402
from app.main import create_app  # noqa: E402
from app.math.pipeline import MistakeFindings, analyse_mistake  # noqa: E402
from evals import metrics  # noqa: E402
from evals.fingerprint import fingerprint  # noqa: E402
from evals.judge import DIMENSIONS, judge, judge_llm  # noqa: E402

EVALS = ROOT / "evals"
OUT = EVALS / "outputs"
IMAGES = EVALS / "transcription"
RESULTS = EVALS / "results.yaml"
LABELS = EVALS / "judge_labels.yaml"
TYPES = {".png": "image/png", ".jpg": "image/jpeg"}
T = TypeVar("T", bound=BaseModel)
INVALID = ("invalid_output", "refused")


class Budget(Exception):
    pass


class RecordingLLM:
    """Wraps the real LLM and keeps what each call cost, and the raw reply."""

    def __init__(self, inner: LLM, spent: list[float], budget: float, model: str) -> None:
        self.inner = inner
        self.model = model  # the deployment that actually runs (Settings, .env included)
        self.calls: list[dict[str, Any]] = []
        self.spent = spent
        self.budget = budget

    async def structured(
        self,
        *,
        task: Task,
        messages: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> LLMResult[T]:
        check_budget(self.spent, self.budget)
        start = time.perf_counter()
        result = await self.inner.structured(
            task=task, messages=messages, schema_name=schema_name, schema=schema, output=output
        )
        usage = dataclasses.asdict(result.usage)
        call_cost = metrics.cost(usage, metrics.PRICES["data_zone"])
        self.spent[0] += call_cost
        self.calls.append(
            {
                "task": task,
                "schema": schema_name,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "attempts": result.attempts,
                "error": result.error,
                "usage": usage,
                "cost": call_cost,
                "reply": result.value.model_dump() if result.value is not None else None,
            }
        )
        return result


def check_budget(spent: list[float], budget: float) -> None:
    if spent[0] >= budget:
        raise Budget(f"spent ${spent[0]:.2f}, the budget is ${budget:.2f}")


def without_rules(*args: Any) -> MistakeFindings:
    """`analyse_mistake` with the rule matches hidden (the "AI only" mode)."""
    found = analyse_mistake(*args)
    return dataclasses.replace(found, rule_ids=[])


@contextmanager
def client(
    effort: ReasoningEffort, spent: list[float], budget: float, ai_only: bool, content: Path | None
) -> Iterator[tuple[TestClient, RecordingLLM]]:
    overrides: dict[str, Any] = {
        "mistake_reasoning_effort": effort,
        "transcribe_reasoning_effort": effort,
        "rate_mistake_per_min": 0,
        "rate_transcribe_per_min": 0,
        "rate_check_working_per_min": 0,
    }
    if content is not None:
        overrides["content_dir"] = content
    if ai_only:
        overrides["math_workers"] = 0  # inline, so the patched function is the one called
    settings = Settings(**overrides)
    if not settings.llm_configured:
        sys.exit("No Azure credentials: put them in the repo's .env (see .env.example).")
    azure = AzureLLM(settings)
    llm = RecordingLLM(azure, spent, budget, settings.model_live)
    patch = (
        mock.patch.object(app.api.mistake, "analyse_mistake", without_rules)
        if ai_only
        else nullcontext()
    )
    with patch, TestClient(create_app(settings, llm=llm)) as test_client:
        try:
            yield test_client, llm
        finally:
            # Close the connections on the app's own event loop, before it ends.
            assert test_client.portal is not None  # set while the client is open
            test_client.portal.call(azure.client.close)


def mistake_body(case: dict[str, Any]) -> dict[str, Any]:
    working = [
        {k: v for k, v in step.items() if v} | {"left": step["left"]}
        for step in case.get("student_working") or []
    ]
    return {
        "problem": {"text": case["problem"]["expr"], "kind": case["problem"]["kind"]},
        "answer": {"text": case["student_answer"]},
        "working": working,
        "topic": case["topic"],
        "lang": "en",
    }


def timed(call: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, int]:
    start = time.perf_counter()
    response = call(*args, **kwargs)
    return response, round((time.perf_counter() - start) * 1000)


def run_mistakes(
    records: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    effort: ReasoningEffort,
    runs: int,
    ai_only: bool,
    stamp: dict[str, Any],
    **kw: Any,
) -> None:
    with client(effort, ai_only=ai_only, **kw) as (test_client, llm):
        for run in range(runs):
            for case in cases:
                before = len(llm.calls)
                body = mistake_body(case)
                response, ms = timed(test_client.post, "/api/mistake", json=body)
                result = response.json()
                calls = llm.calls[before:]
                diagnosis = result.get("diagnosis") or {}
                ai_text = None
                if diagnosis.get("source") == "ai":
                    ai_text = {
                        k: diagnosis.get(k) for k in ("explanation", "margin_note", "what_to_say")
                    }
                elif diagnosis.get("source") == "rule" and calls and not diagnosis["say_example"]:
                    # The moves the AI worded for this problem, judged with the card they follow
                    # (shown above them as the belief and why it feels right).
                    card = diagnosis["misconceptions"][0]
                    ai_text = {
                        "explanation": f"{card['belief']} {card['why_it_feels_right']}",
                        "margin_note": None,
                        "what_to_say": diagnosis["what_to_say"],
                    }
                records.append(
                    {
                        "id": f"{effort}/{'ai_only' if ai_only else 'product'}/{case['id']}/{run}",
                        "case": case["id"],
                        "effort": effort,
                        "mode": "ai_only" if ai_only else "product",
                        "run": run,
                        "http": response.status_code,
                        "latency_ms": ms,
                        "problem": case["problem"]["expr"],
                        "student_answer": case["student_answer"],
                        "working": case.get("student_working") or [],
                        "expected": case["expected"],
                        "status": result.get("status"),
                        "reason": result.get("reason"),
                        "verdict": result.get("verdict"),
                        "correct_answer": result.get("correct_answer"),
                        "source": diagnosis.get("source"),
                        "ids": [m["id"] for m in diagnosis.get("misconceptions") or []],
                        "ai_text": ai_text,
                        "result": result,
                        "calls": calls,
                        "model": llm.model,
                    }
                    | stamp
                )
                print(f"  {records[-1]['id']}: {result.get('status')} {result.get('reason')}")


def run_transcription(
    records: list[dict[str, Any]],
    images: list[dict[str, Any]],
    effort: ReasoningEffort,
    runs: int,
    stamp: dict[str, Any],
    **kw: Any,
) -> None:
    with client(effort, ai_only=False, **kw) as (test_client, llm):
        for run in range(runs):
            for image in images:
                path = IMAGES / image["file"]
                files = {"image": (path.name, path.read_bytes(), TYPES[path.suffix])}
                before = len(llm.calls)
                response, ms = timed(test_client.post, "/api/transcribe", files=files)
                result = response.json()
                records.append(
                    {
                        "id": f"{effort}/transcribe/{path.stem}/{run}",
                        "image": image["file"],
                        "kind": image["kind"],
                        "effort": effort,
                        "run": run,
                        "http": response.status_code,
                        "latency_ms": ms,
                        "result": result,
                        "score": metrics.score_transcription(
                            result, image["lines"], http=response.status_code
                        ),
                        "calls": llm.calls[before:],
                        "model": llm.model,
                    }
                    | stamp
                )
                print(f"  {records[-1]['id']}: {records[-1]['score']}")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = yaml.safe_load((EVALS / "mistakes.yaml").read_text())["cases"]
    return cases


def load_images() -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = yaml.safe_load((IMAGES / "truth.yaml").read_text())["images"]
    return images


def rule_labelled(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in cases if c["expected"].get("misconception_id") in RULE_IDS[c["topic"]]]


def cmd_run(args: argparse.Namespace) -> None:
    cases, images = load_cases(), load_images()
    # A filtered run (--cases) writes `*-subset.jsonl`, which `summarize` ignores, so it never
    # replaces the full outputs.
    suffix = ""
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in wanted]
        images = [i for i in images if Path(i["file"]).stem in wanted]
        suffix = "-subset"
    spent = [0.0]
    # Every row says what produced it: summarize refuses rows from other code or inputs, and
    # checks that each item ran exactly `runs` times.
    stamp = {"fingerprint": fingerprint(labels=False), "runs": args.runs}
    kw = {"spent": spent, "budget": args.budget, "content": args.content, "stamp": stamp}
    modes: list[tuple[str, str, Callable[..., None], list[dict[str, Any]], bool]] = [
        ("mistakes", "mistakes", run_mistakes, cases, False),
        ("ai_only", "ai-only", run_mistakes, rule_labelled(cases), True),
        ("transcription", "transcription", run_transcription, images, False),
    ]
    for effort in [cast(ReasoningEffort, e) for e in args.efforts.split(",")]:
        for mode, stem, run_mode, items, ai_only in modes:
            if mode not in args.only or not items:
                continue
            print(f"{mode}, {effort}")
            records: list[dict[str, Any]] = []
            extra = {"ai_only": ai_only} if run_mode is run_mistakes else {}
            try:
                run_mode(records, items, effort, args.runs, **extra, **kw)
            except Budget as stop:
                # Never over the full outputs: summarize refuses while a partial file exists.
                partial = OUT / f"{stem}-{effort}{suffix}-partial.jsonl"
                write_jsonl(partial, records)
                sys.exit(f"Stopped: {stop}. What ran is in {partial.name}; summarize refuses it.")
            write_jsonl(OUT / f"{stem}-{effort}{suffix}.jsonl", records)
        print(f"spent so far: ${spent[0]:.2f}")


def ai_records() -> list[dict[str, Any]]:
    """Every AI text that was shown, from both modes and both efforts."""
    records = []
    for path in sorted(OUT.glob("mistakes-*.jsonl")) + sorted(OUT.glob("ai-only-*.jsonl")):
        if not path.stem.endswith(("-subset", "-partial")):
            records += [r for r in read_jsonl(path) if r["ai_text"]]
    return records


def cmd_judge(args: argparse.Namespace) -> None:
    records = ai_records()
    if args.sample:
        rng = random.Random(10)
        by_stratum: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for r in records:
            by_stratum[(r["effort"], r["mode"], r["source"], r["status"])].append(r)
        sample: list[dict[str, Any]] = []
        while len(sample) < args.sample and any(by_stratum.values()):
            for group in by_stratum.values():
                if group and len(sample) < args.sample:
                    sample.append(group.pop(rng.randrange(len(group))))
        write_jsonl(OUT / "label-sample.jsonl", [r | {"text_hash": _hash(r)} for r in sample])
        print(f"wrote {len(sample)} outputs to label to {OUT / 'label-sample.jsonl'}")
        return
    llm = judge_llm()
    stamp = fingerprint(labels=False)
    # A text already scored (same id, same text, same code) is kept, not paid for again.
    done = {
        (j["id"], j["text_hash"]): j
        for j in read_jsonl(OUT / "judge.jsonl")
        if j.get("fingerprint") == stamp and j["scores"]
    }
    spent = [0.0]
    out: list[dict[str, Any]] = []

    async def go() -> None:
        for record in records:
            key = (record["id"], _hash(record))
            if key in done:
                out.append(done[key])
                continue
            check_budget(spent, args.budget)
            start = time.perf_counter()
            reply = await judge(llm, record)
            usage = dataclasses.asdict(reply.usage)
            out.append(
                {
                    "id": record["id"],
                    "text_hash": key[1],
                    "scores": reply.value.model_dump() if reply.value else None,
                    "error": reply.error,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                    "usage": usage,
                    "cost": metrics.cost(usage, metrics.PRICES["global"]),
                    "model": llm.settings.model_offline,
                    "reasoning_effort": llm.settings.judge_reasoning_effort,
                    "fingerprint": stamp,
                }
            )
            spent[0] += out[-1]["cost"]
            print(f"  {record['id']}: {out[-1]['scores'] or out[-1]['error']}")

    try:
        asyncio.run(go())
    except Budget as stop:
        write_jsonl(OUT / "judge.jsonl", out)
        sys.exit(f"Stopped: {stop}. {len(out)} texts judged; rerun `judge` to go on.")
    write_jsonl(OUT / "judge.jsonl", out)
    print(f"judged {len(out) - len(done)} new texts, kept {len(done)}, ${spent[0]:.2f}")


def _hash(record: dict[str, Any]) -> str:
    """Pins a judge score or hand label to the text it was given: ids repeat on every rerun."""
    return metrics.text_hash(record["ai_text"])


def _latency(values: list[int]) -> dict[str, float | None]:
    return {"p50": metrics.quantile(values, 0.5), "p90": metrics.quantile(values, 0.9)}


def _calls_summary(calls: list[dict[str, Any]]) -> dict[str, Any]:
    if not calls:
        return {"calls": 0}
    n = len(calls)
    mean = {k: round(sum(c["usage"][k] for c in calls) / n) for k in dataclasses.asdict(Usage())}
    return {
        "calls": n,
        "schema_valid": metrics.rate(c["error"] not in INVALID for c in calls),
        "errors": metrics.counts(c["error"] for c in calls),
        "retried": metrics.rate(c["attempts"] > 1 for c in calls),
        "latency_ms": _latency([c["latency_ms"] for c in calls]),
        "mean_tokens": mean,
        "cache_hit_share": round(
            sum(c["usage"]["cached_tokens"] for c in calls)
            / max(1, sum(c["usage"]["prompt_tokens"] for c in calls)),
            3,
        ),
        "cost_per_call_usd": round(sum(c["cost"] for c in calls) / n, 5),
        "cost_usd": round(sum(c["cost"] for c in calls), 4),
    }


def _raw_math(rows: list[dict[str, Any]]) -> str:
    return f"{sum(metrics.raw_math(r['ai_text']) for r in rows)}/{len(rows)}"


def _fallback(record: dict[str, Any]) -> str | None:
    """Why a rule match showed the card's own moves, or None when they were rewritten."""
    if record["result"]["diagnosis"]["say_example"] is None:
        return None
    call = record["calls"][-1]
    reply = call["reply"]
    if reply is None:
        return f"error:{call['error']}"
    if reply["abstain"]:
        return "abstained"
    if not all(reply[k].strip() for k in ("probe", "nudge", "tell")):
        return "blank_move"
    return "unverified_math"


def summarize_mistakes(records: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [(r, metrics.score_mistake(r["result"], r["expected"])) for r in records]
    controls = [s for r, s in scored if r["expected"]["classification"] != "wrong"]
    named = [(r, s) for r, s in scored if s["id_ok"] is not None]
    ai_path = [r for r in records if r["calls"] and r["source"] != "rule"]
    # A rule match makes one call too: it rewrites the card's moves for this problem.
    rule_moves = [r for r in records if r["calls"] and r["source"] == "rule"]
    outcomes: dict[str, list[str]] = defaultdict(list)
    for r, s in scored:
        outcomes[r["case"]].append(s["outcome"])

    def id_match(rows: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
        return {
            "n": len(rows),
            "first_id": metrics.rate(s["id_ok"] for _, s in rows),
            "in_top_2": metrics.rate(s["id_in_top2"] for _, s in rows),
        }

    return {
        "runs": len(records),
        "verdict_accuracy": metrics.rate(s["verdict_ok"] for _, s in scored),
        "status_match": metrics.rate(s["status_ok"] for _, s in scored),
        "false_mistake_rate_on_controls": metrics.rate(s["false_mistake"] for s in controls),
        "misconception_id": {
            "all": id_match(named),
            "rule_labelled": id_match(
                [(r, s) for r, s in named if r["expected"]["misconception_id"] in RULE_IDS[_t(r)]]
            ),
            "ai_labelled": id_match(
                [
                    (r, s)
                    for r, s in named
                    if r["expected"]["misconception_id"] not in RULE_IDS[_t(r)]
                ]
            ),
        },
        "consistent_over_runs": metrics.consistent(outcomes),
        # "ai_abstained": the LLM was called but nothing it wrote was shown.
        "answered_by": metrics.counts(
            r["source"] or ("ai_abstained" if r["calls"] else "sympy") for r in records
        ),
        "ai_path": {
            "runs": len(ai_path),
            "status": metrics.counts(r["status"] for r in ai_path),
            "abstain_reasons": metrics.counts(r["reason"] for r in ai_path),
            "held_back_unverified_math": metrics.rate(
                r["reason"] == "ai_unverified_math" for r in ai_path
            ),
        },
        # Shown AI texts with math outside backticks, which the page shows raw (`3*x`).
        "raw_math_in_shown_text": {
            "diagnoses": _raw_math([r for r in records if r["source"] == "ai" and r["ai_text"]]),
            "rule_moves": _raw_math([r for r in records if r["source"] == "rule" and r["ai_text"]]),
        },
        "rule_path_moves": {
            "runs": len(rule_moves),
            "written_for_the_problem": metrics.rate(
                r["result"]["diagnosis"]["say_example"] is None for r in rule_moves
            ),
            # The card's own moves were shown, framed by its example problem, because the call
            # failed, abstained or wrote a number sympy didn't give it.
            "fell_back": metrics.counts(f for f in map(_fallback, rule_moves) if f),
        },
        "request_latency_ms": {
            "no_ai": _latency([r["latency_ms"] for r in records if not r["calls"]]),
            "ai": _latency([r["latency_ms"] for r in ai_path]),
            "rule_moves": _latency([r["latency_ms"] for r in rule_moves]),
        },
        "llm": _calls_summary([c for r in records for c in r["calls"]]),
        "llm_by_call": {
            name: _calls_summary([c for r in records for c in r["calls"] if c["schema"] == name])
            for name in ("mistake_diagnosis", "rule_what_to_say")
        },
        "per_case": {case: sorted(set(v)) for case, v in outcomes.items()},
    }


_TOPIC: dict[str, TopicId] = {}


def _t(record: dict[str, Any]) -> TopicId:
    if not _TOPIC:
        _TOPIC.update({c["id"]: c["topic"] for c in load_cases()})
    return _TOPIC[record["case"]]


def summarize_transcription(records: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["score"] for r in records]
    by_kind: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        by_kind[r["kind"]].append(r["score"]["image_ok"])
    lines = sum(s["lines"] for s in scores)
    wrong = sum(s["wrong"] for s in scores)
    return {
        "runs": len(records),
        "line_accuracy": round(sum(s["right"] for s in scores) / max(1, lines), 3),
        "image_accuracy": metrics.rate(s["image_ok"] for s in scores),
        "image_accuracy_by_kind": {k: metrics.rate(v) for k, v in sorted(by_kind.items())},
        "wrong_lines": wrong,
        "wrong_lines_flagged_uncertain": round(sum(s["wrong_flagged"] for s in scores) / wrong, 3)
        if wrong
        else None,
        "request_latency_ms": _latency([r["latency_ms"] for r in records]),
        "llm": _calls_summary([c for r in records for c in r["calls"]]),
        "per_image": {
            img: sorted({json.dumps(r["score"]["image_ok"]) for r in records if r["image"] == img})
            for img in sorted({r["image"] for r in records})
        },
    }


def summarize_judge(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Judge scores and labels count only where their text hash matches the current outputs'
    text: a stale score or label (from an earlier run with the same id) is skipped and counted."""
    current = {r["id"]: _hash(r) for r in records if r["ai_text"]}
    all_judged = read_jsonl(OUT / "judge.jsonl")
    if not all_judged:
        return None
    judged = [j for j in all_judged if current.get(j["id"]) == j.get("text_hash")]
    _check_stamps(OUT / "judge.jsonl", judged)
    unjudged = set(current) - {j["id"] for j in judged}
    if unjudged:
        sys.exit(f"{len(unjudged)} AI texts have no judge score: run `judge` first.")
    labels = (yaml.safe_load(LABELS.read_text()) or {}).get("labels") if LABELS.exists() else None
    by_id = {j["id"]: j for j in judged}
    ok = [j for j in judged if j["scores"] and not j["scores"]["cannot_judge"]]
    calibration: dict[str, Any] = {}
    stale_labels = 0
    if labels:
        fresh = [lab for lab in labels if current.get(lab["id"]) == lab.get("text_hash")]
        stale_labels = len(labels) - len(fresh)
        pairs = [(lab, by_id[lab["id"]]) for lab in fresh if by_id.get(lab["id"], {}).get("scores")]
        for d in DIMENSIONS:
            human = [lab[d] for lab, _ in pairs]
            model = [j["scores"][d] for _, j in pairs]
            kappa = metrics.weighted_kappa(human, model) if pairs else None
            # Quoted only when the judge agrees with the hand labels beyond chance.
            calibration[d] = {
                "n": len(pairs),
                "agreement": metrics.rate(h == m for h, m in zip(human, model, strict=True)),
                "weighted_kappa": round(kappa, 3) if kappa is not None else None,
                "quoted": kappa is not None and kappa >= 0.6,
            }
    record_by_id = {r["id"]: r for r in records}
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for j in ok:
        r = record_by_id[j["id"]]
        # Rule-match moves are scored apart from the AI's own diagnoses.
        mode = r["mode"] if r["source"] == "ai" else f"{r['mode']}_rule_moves"
        groups[(r["effort"], mode)].append(j)
    scores: dict[str, dict[str, Any]] = defaultdict(dict)
    for (effort, mode), rows in sorted(groups.items()):
        scores[effort][mode] = {
            d: {
                "n": len(rows),
                "yes": metrics.rate(j["scores"][d] == "yes" for j in rows),
                "yes_or_some": metrics.rate(j["scores"][d] != "no" for j in rows),
            }
            for d in DIMENSIONS
        }
    return {
        "model": _one(j["model"] for j in judged),
        "reasoning_effort": _one(j["reasoning_effort"] for j in judged),
        "stale_scores_skipped": len(all_judged) - len(judged),
        "stale_labels_skipped": stale_labels,
        "judged": len(judged),
        "failures": len(judged) - len(ok),
        "failure_reasons": metrics.counts(
            j["error"] or ("cannot_judge" if j["scores"] else None) for j in judged if j not in ok
        ),
        "calibration": calibration,
        "scores_by_effort_and_mode": dict(scores),
        "cost_usd": round(sum(j["cost"] for j in judged), 4),
    }


def _one(values: Iterable[str]) -> str:
    """The one value every row shares (a model or effort), or all of them if they differ."""
    return ", ".join(sorted(set(values)))


def _check_stamps(path: Path, records: list[dict[str, Any]]) -> None:
    """Refuse rows made by other code or inputs than what is here now."""
    stamp = fingerprint(labels=False)
    stale = sum(r.get("fingerprint") != stamp for r in records)
    if stale:
        sys.exit(
            f"{path.name}: {stale} rows were made by other prompts, code or inputs than the "
            "current ones: rerun `run` (and `judge`) before `summarize`."
        )


def _check_complete(path: Path, records: list[dict[str, Any]], want: set[str]) -> None:
    """Refuse partial outputs: every item exactly as many times as the run asked for."""
    _check_stamps(path, records)
    key = "image" if path.stem.startswith("transcription") else "case"
    counts: dict[str, int] = defaultdict(int)
    for r in records:
        counts[r[key]] += 1
    asked = {r["runs"] for r in records}
    if set(counts) != want or len(asked) != 1 or set(counts.values()) != asked:
        missing = sorted(want - set(counts))
        sys.exit(f"{path.name} is partial (missing {missing[:5]}, or not every run): rerun `run`.")


def cmd_summarize(args: argparse.Namespace) -> None:
    partial = sorted(p.name for p in OUT.glob("*-partial.jsonl"))
    if partial:
        sys.exit(f"Partial outputs from a budget stop: {partial}. Rerun `run`, then delete them.")
    efforts = sorted(
        {
            p.stem.split("-")[-1]
            for p in OUT.glob("*.jsonl")
            if p.stem.split("-")[0] in ("mistakes", "ai", "transcription")
            and not p.stem.endswith("-subset")
        }
    )
    cases = load_cases()
    want = {
        "mistakes": {c["id"] for c in cases},
        "ai-only": {c["id"] for c in rule_labelled(cases)},
        "transcription": {i["file"] for i in load_images()},
    }
    all_mistakes: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    per_effort: dict[str, Any] = {}
    total = 0.0
    for effort in efforts:
        mistakes, ai_only, transcription = (
            read_jsonl(OUT / f"{stem}-{effort}.jsonl") for stem in want
        )
        for stem, records in zip(want, (mistakes, ai_only, transcription), strict=True):
            if records:
                _check_complete(OUT / f"{stem}-{effort}.jsonl", records, want[stem])
        all_mistakes += mistakes + ai_only
        per_effort[effort] = {
            "mistakes": summarize_mistakes(mistakes) if mistakes else None,
            "ai_only_not_product_accuracy": summarize_mistakes(ai_only) if ai_only else None,
            "transcription": summarize_transcription(transcription) if transcription else None,
        }
        total += sum(c["cost"] for r in mistakes + ai_only + transcription for c in r["calls"])
        all_rows += mistakes + ai_only + transcription
    judge_summary = summarize_judge(all_mistakes)
    if judge_summary:
        total += judge_summary["cost_usd"]
    recommendation = args.recommend
    if not recommendation and RESULTS.exists():  # keep the recorded one
        recommendation = (yaml.safe_load(RESULTS.read_text()) or {}).get("recommendation", "")
    results = {
        "fingerprint": fingerprint(),
        "date": dt.date.today().isoformat(),
        # What ran (Settings with .env), not the code defaults. The prices are gpt-5.5's.
        "model": _one(r["model"] for r in all_rows),
        "prices_usd_per_1m_tokens": metrics.PRICES,
        "reasoning_efforts": per_effort,
        "judge": judge_summary,
        "total_cost_usd": round(total, 3),
        "recommendation": recommendation,
    }
    RESULTS.write_text(
        "# Written by `evals/run.py summarize` from evals/outputs/. Don't edit by hand:\n"
        "# backend/tests/test_evals.py checks the fingerprint against the inputs.\n"
        + yaml.safe_dump(results, sort_keys=False, allow_unicode=True, width=100)
    )
    print(f"wrote {RESULTS}, total ${total:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="mistakes, AI only and transcription, live")
    run.add_argument("--efforts", default="none,low")
    run.add_argument("--runs", type=int, default=3)
    run.add_argument("--only", default="mistakes,ai_only,transcription")
    run.add_argument("--cases", default="", help="comma-separated case ids or image stems")
    run.add_argument("--budget", type=float, default=5.0, help="stop when this many USD are spent")
    run.add_argument("--content", type=Path, default=None, help="pack dir (default: the app's)")
    judge_cmd = sub.add_parser("judge", help="the LLM judge on the AI's shown text")
    judge_cmd.add_argument("--sample", type=int, default=0, help="only write a sample to label")
    judge_cmd.add_argument("--budget", type=float, default=2.0, help="stop at this many USD")
    summarize = sub.add_parser("summarize", help="write results.yaml from the outputs")
    summarize.add_argument(
        "--recommend", default="", help="the recommendation to record (default: keep the last)"
    )
    args = parser.parse_args()
    {"run": cmd_run, "judge": cmd_judge, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    main()
