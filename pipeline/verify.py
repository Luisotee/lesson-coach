"""Checks the committed packs. Exits non-zero when any check fails.

    uv run --project backend python pipeline/verify.py --lang en
    uv run --project backend python pipeline/verify.py --lang en --judge \
        --report evals/verify-report.md

Deterministic checks always run (see checks.py): the schema, stale sources, content copied
unchanged, sympy's steps and answers, numbers in explanations, claims, prompts, and that
`unavailable` lists exactly what was dropped. `--judge` adds the LLM judge over every piece of
prose, by majority of 3 when it flags anything.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content.schema import TOPIC_IDS, Pack, TopicId
from pydantic import ValidationError

from pipeline import ROOT
from pipeline.checks import Finding, pack_findings
from pipeline.core import LLM, StepsFor, offline_llm, worked_steps
from pipeline.prompts import example_facts
from pipeline.sources import load, pack_path

# USD per million tokens, from the environment, e.g. PRICE_INPUT=1.25. Unset: no cost line.
PRICES = {k: os.environ.get(f"PRICE_{k.upper()}") for k in ("input", "cached", "output")}


@dataclass
class TopicResult:
    topic: TopicId
    findings: list[Finding] = field(default_factory=list)
    judged: dict[str, list[str]] = field(default_factory=dict)
    unavailable: list[str] = field(default_factory=list)
    explained_steps: int = 0
    steps: int = 0


def verify_topic(topic: TopicId, lang: str, steps_for: StepsFor = worked_steps) -> TopicResult:
    result = TopicResult(topic)
    path = pack_path(topic, lang)
    if not path.exists():
        result.findings.append(Finding(str(path), "missing", "no pack"))
        return result
    try:
        pack = Pack.model_validate_json(path.read_text())
    except ValidationError as err:
        result.findings.append(Finding(str(path), "schema", str(err)))
        return result
    result.findings = pack_findings(pack, load(topic), steps_for)
    result.unavailable = pack.unavailable
    for example in pack.worked_examples:
        result.steps += len(example.steps)
        result.explained_steps += sum(s.explanations is not None for s in example.steps)
    return result


async def judge_topic(topic: TopicId, lang: str, llm: LLM) -> dict[str, list[str]]:
    """The LLM judge over the pack's prose, as generate.py runs it."""
    from pipeline.generate import Runner, Stats

    pack = Pack.model_validate_json(pack_path(topic, lang).read_text())
    lesson = load(topic).lesson
    runner = Runner(llm, Stats())
    facts = "\n\n".join(example_facts(e) for e in pack.worked_examples)
    texts = {k: v for k in ("summary", "idea", "why_it_works") if (v := getattr(pack, k))}
    for i, q in enumerate(pack.questions):
        texts[f"questions[{i}]"] = f"Q: {q.question}\nA: {q.answer}"
    for i, o in enumerate(pack.outline):
        texts[f"outline[{i}]"] = f"{o.title} ({o.minutes} min): {o.activity}"
    jobs = [runner.judge(lesson, facts, texts)]
    for example in pack.worked_examples:
        step_texts = {
            f"steps[{j}]": f"why: {s.explanations.why}\nanother way: "
            f"{s.explanations.another_way}\npicture: {s.explanations.visual}"
            for j, s in enumerate(example.steps)
            if s.explanations is not None
        }
        jobs.append(runner.judge(lesson, example_facts(example), step_texts))
    flagged: dict[str, list[str]] = {}
    for i, found in enumerate(await asyncio.gather(*jobs)):
        prefix = "" if i == 0 else f"worked_examples[{i - 1}]."
        for key, why in found.items():
            flagged[prefix + key] = why
    return flagged


def cost_line(stats: object) -> str:
    if None in PRICES.values():
        return "- Cost: not computed (set PRICE_INPUT, PRICE_CACHED and PRICE_OUTPUT, USD/1M)"
    price = {k: float(v or 0) for k, v in PRICES.items()}
    cached = getattr(stats, "cached_tokens", 0)
    fresh = getattr(stats, "prompt_tokens", 0) - cached
    out = getattr(stats, "completion_tokens", 0)
    usd = (fresh * price["input"] + cached * price["cached"] + out * price["output"]) / 1e6
    return (
        f"- Cost: about ${usd:.2f} at ${price['input']} input, ${price['cached']} cached and "
        f"${price['output']} output per million tokens (reasoning tokens bill as output)"
    )


def write_report(
    path: Path,
    lang: str,
    *,
    stats: object | None = None,
    model: str = "",
    judged: dict[TopicId, dict[str, list[str]]] | None = None,
) -> list[TopicResult]:
    results = [verify_topic(t, lang) for t in TOPIC_IDS]
    lines = [
        "# Pack verification report",
        "",
        f"Language `{lang}`. Written by `pipeline/{'generate' if stats else 'verify'}.py`"
        + (f" with model `{model}`." if model else "."),
        "",
        "Deterministic checks (sympy, through `app.math`): schema, sources unchanged and not",
        "stale, worked steps equal to sympy's and passing `check_steps`, answers, every number",
        'in a step explanation present in its step, every "`A` is `B`" claim true, prompts.',
        "",
        "| Topic | Deterministic findings | Steps explained | Unavailable | Judge flags |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        flags = judged.get(r.topic) if judged else None
        lines.append(
            f"| {r.topic} | {len(r.findings)} | {r.explained_steps}/{r.steps} | "
            f"{', '.join(r.unavailable) or 'none'} | "
            f"{'not run' if flags is None else len(flags)} |"
        )
    for r in results:
        for f in r.findings:
            lines.append(f"- `{r.topic}` {f}")
    if judged:
        for topic, flags in judged.items():
            for key, why in flags.items():
                lines.append(f"- judge, `{topic}` `{key}`: {'; '.join(why)}")
    if stats is not None:
        s = stats
        lines += [
            "",
            "## Generation",
            "",
            f"- LLM calls: {dict(getattr(s, 'calls', {}))}, "
            f"failed: {getattr(s, 'failed_calls', 0)}",
            f"- Targeted retries: {getattr(s, 'retries', 0)}; fresh samples: "
            f"{getattr(s, 'samples', 0)}",
            f"- Judge majorities that flagged a field: {dict(getattr(s, 'judge_flags', {}))}",
            f"- Dropped (shipped as unavailable): {getattr(s, 'dropped', []) or 'none'}",
            f"- Tokens: prompt {getattr(s, 'prompt_tokens', 0)} (cached "
            f"{getattr(s, 'cached_tokens', 0)}), completion {getattr(s, 'completion_tokens', 0)} "
            f"(reasoning {getattr(s, 'reasoning_tokens', 0)})",
            cost_line(s),
        ]
    path = path if path.is_absolute() else ROOT / path
    path.write_text("\n".join(lines) + "\n")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--lang", default="en")
    parser.add_argument("--judge", action="store_true", help="also run the LLM judge")
    parser.add_argument("--report", help="write a markdown report to this path")
    args = parser.parse_args()
    judged: dict[TopicId, dict[str, list[str]]] | None = None
    if args.judge:
        llm, _ = offline_llm()

        async def run() -> dict[TopicId, dict[str, list[str]]]:
            found = await asyncio.gather(*(judge_topic(t, args.lang, llm) for t in TOPIC_IDS))
            return dict(zip(TOPIC_IDS, found, strict=True))

        judged = asyncio.run(run())
    if args.report:
        results = write_report(Path(args.report), args.lang, judged=judged)
    else:
        results = [verify_topic(t, args.lang) for t in TOPIC_IDS]
    failed = False
    for r in results:
        flags = (judged or {}).get(r.topic, {})
        status = "ok" if not r.findings and not flags else "FAILED"
        failed |= status != "ok"
        print(f"{r.topic}: {status} ({len(r.findings)} findings, {len(flags)} judge flags)")
        for f in r.findings:
            print(f"  {f}")
        for key, why in flags.items():
            print(f"  judge {key}: {'; '.join(why)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
