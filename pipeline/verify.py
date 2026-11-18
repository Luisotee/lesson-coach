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

if __package__ in (None, ""):  # run as a script: make `pipeline` and `app` importable
    sys.path[:0] = [str(Path(__file__).resolve().parents[1] / p) for p in ("", "backend")]

from app.content.schema import TOPIC_IDS, Pack, TopicId
from pydantic import ValidationError

from pipeline import ROOT
from pipeline.checks import Finding, pack_findings, prose_paths, translation_findings
from pipeline.core import LLM, StepsFor, offline_llm, worked_steps
from pipeline.prompts import example_facts, prose_texts, steps_texts
from pipeline.sources import load, load_pack, pack_path, translation_hash

# USD per million tokens. Defaults: Microsoft's published GPT-5.5 rate (Foundry announcement,
# azure.microsoft.com/en-us/blog/openais-gpt-5-5-in-microsoft-foundry-...). Override with
# PRICE_INPUT, PRICE_CACHED and PRICE_OUTPUT.
DEFAULT_PRICES = {"input": 5.00, "cached": 0.50, "output": 30.00}


def prices() -> dict[str, float]:
    """The default prices, each overridden by its PRICE_* variable when that is a number."""
    found = dict(DEFAULT_PRICES)
    for key in found:
        raw = os.environ.get(f"PRICE_{key.upper()}")
        if raw is None:
            continue
        try:
            found[key] = float(raw)
        except ValueError:
            print(f"warning: PRICE_{key.upper()}={raw!r} is not a number; using {found[key]}")
    return found


NO_VERDICT = {"*": ["the judge gave no verdict"]}
JUDGE_NOTE = "The judge columns come from an independent `verify.py --judge` run."
UNREADABLE = {"missing", "schema"}  # findings that leave no pack to judge


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
    if lang == "en":
        result.findings = pack_findings(pack, load(topic), steps_for)
    else:
        english = load_pack(topic, "en")
        expected = translation_hash(topic)
        result.findings = translation_findings(pack, english, expected, steps_for)
    result.unavailable = pack.unavailable
    for example in pack.worked_examples:
        result.steps += len(example.steps)
        result.explained_steps += sum(s.explanations is not None for s in example.steps)
    return result


async def judge_translation(topic: TopicId, lang: str, llm: LLM) -> dict[str, list[str]]:
    """The translation judge over every text of a translated pack, unit by unit, as
    translate.py runs it."""
    from pipeline.generate import Runner, Stats
    from pipeline.languages import LANGUAGES
    from pipeline.translate import units
    from pipeline.translate_prompts import judge_messages

    pack, english = load_pack(topic, lang), load_pack(topic, "en")
    runner = Runner(llm, Stats())
    ours = prose_paths(pack)
    jobs = []
    for _, group in units(english):
        pairs = {p: f"EN: {text}\nTR: {ours[p]}" for p, text in group.items() if p in ours}
        messages = judge_messages(LANGUAGES[lang], pairs)
        jobs.append(runner.judge("", "", pairs, messages=messages))
    flagged: dict[str, list[str]] = {}
    for found in await asyncio.gather(*jobs):
        flagged.update(found if found is not None else NO_VERDICT)
    return flagged


async def judge_topic(topic: TopicId, lang: str, llm: LLM) -> dict[str, list[str]]:
    """The LLM judge over the pack's prose, as generate.py runs it."""
    from pipeline.generate import Runner, Stats

    if lang != "en":
        return await judge_translation(topic, lang, llm)
    pack = Pack.model_validate_json(pack_path(topic, lang).read_text())
    lesson = load(topic).lesson
    runner = Runner(llm, Stats())
    facts = "\n\n".join(example_facts(e) for e in pack.worked_examples)
    jobs = [runner.judge(lesson, facts, prose_texts(pack))]
    for example in pack.worked_examples:
        texts = steps_texts([s.explanations for s in example.steps])
        jobs.append(runner.judge(lesson, example_facts(example), texts))
    flagged: dict[str, list[str]] = {}
    for i, found in enumerate(await asyncio.gather(*jobs)):
        prefix = "" if i == 0 else f"worked_examples[{i - 1}]."
        for key, why in (found if found is not None else NO_VERDICT).items():
            flagged[prefix + key] = why
    return flagged


def cost_usd(stats: object) -> float:
    price = prices()
    cached = getattr(stats, "cached_tokens", 0)
    fresh = getattr(stats, "prompt_tokens", 0) - cached
    out = getattr(stats, "completion_tokens", 0)
    return (fresh * price["input"] + cached * price["cached"] + out * price["output"]) / 1e6


def cost_line(stats: object) -> str:
    price = prices()
    usd = cost_usd(stats)
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
    results: list[TopicResult] | None = None,
) -> list[TopicResult]:
    results = results if results is not None else [verify_topic(t, lang) for t in TOPIC_IDS]
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
    if stats is None and path.exists():  # keep the last generation's numbers
        old = path.read_text()
        if "\n## Generation\n" in old:
            section = old.split("\n## Generation", 1)[1].split(f"\n{JUDGE_NOTE}")[0]
            lines += ["", "## Generation" + section.rstrip("\n")]
    if judged and stats is None:
        lines += ["", JUDGE_NOTE]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results


def judgeable(results: list[TopicResult]) -> list[TopicId]:
    """The topics whose pack exists and loads; the others already fail verify."""
    return [r.topic for r in results if not any(f.check in UNREADABLE for f in r.findings)]


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--lang", default="en", help="a language code, or `all`")
    parser.add_argument("--judge", action="store_true", help="also run the LLM judge")
    parser.add_argument("--report", help="write a markdown report to this path")
    args = parser.parse_args()
    langs = pack_langs() if args.lang == "all" else [args.lang]
    if args.report and len(langs) > 1:
        parser.error("--report takes one language")
    failed = False
    for lang in langs:
        failed |= verify_lang(lang, args.judge, args.report)
    sys.exit(1 if failed else 0)


def pack_langs() -> list[str]:
    """English, then every language with a directory of packs."""
    found = sorted(p.name for p in (ROOT / "content" / "generated").iterdir() if p.is_dir())
    return ["en", *[lang for lang in found if lang != "en"]]


def verify_lang(lang: str, judge: bool, report: str | None) -> bool:
    """Checks one language's packs and prints the result; True when anything failed."""
    results = [verify_topic(t, lang) for t in TOPIC_IDS]
    judged: dict[TopicId, dict[str, list[str]]] | None = None
    if judge:
        llm, _ = offline_llm()
        topics = judgeable(results)

        async def run() -> dict[TopicId, dict[str, list[str]]]:
            found = await asyncio.gather(*(judge_topic(t, lang, llm) for t in topics))
            return dict(zip(topics, found, strict=True))

        judged = asyncio.run(run())
    if report:
        write_report(Path(report), lang, judged=judged, results=results)
    failed = False
    for r in results:
        flags = (judged or {}).get(r.topic, {})
        status = "ok" if not r.findings and not flags else "FAILED"
        failed |= status != "ok"
        print(f"{lang} {r.topic}: {status} ({len(r.findings)} findings, {len(flags)} judge flags)")
        for f in r.findings:
            print(f"  {f}")
        for key, why in flags.items():
            print(f"  judge {key}: {'; '.join(why)}")
    return failed


if __name__ == "__main__":
    main()
