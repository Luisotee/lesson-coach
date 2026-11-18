"""Translates the English packs into other languages, offline.

    uv run --project backend python pipeline/translate.py --lang fr de
    uv run --project backend python pipeline/translate.py --wave 1 --budget 50
    uv run --project backend python pipeline/translate.py --prune

A translated pack is the English pack with only its prose translated: every math field, id,
source and count is copied, and the problem prompts come from `PROMPTS[lang]`
(backend/app/content/prompts.json), translated here once per language. Each unit of text goes
through generate.py's loop: deterministic checks (every math span copied character for
character, no new numbers, digits 0-9), then the LLM judge comparing the English and the
translation (a majority of 3 when it flags anything); the texts that fail are asked for again
with their problems, up to 3 times. A unit that passed is cached under pipeline/.cache/, keyed by
the language, the English, its context and the bytes of translate_prompts.py (the same bytes
that are in every translated pack's `source_hash`), so a rerun redoes only what changed.

A language's packs are written only complete: its prompts and all three packs pass every check,
or nothing of it is written and the report says why. A language is offered only when its UI
strings ship too (translate_ui.py); after translate_ui.py, `--prune` removes from
content/generated and prompts.json the packs whose UI strings failed, so the API never serves a
language the app does not offer (tests tie the two together). Per-language numbers go to
evals/translation-stats.json, rendered as evals/translation-report.md.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a script: make `pipeline` and `app` importable
    sys.path[:0] = [str(Path(__file__).resolve().parents[1] / p) for p in ("", "backend")]

from app.content.schema import PROMPTS, TOPIC_IDS, Pack, TopicId

from pipeline import ROOT
from pipeline.checks import (
    item_findings,
    prose_paths,
    set_path,
    translation_findings,
)
from pipeline.core import LLM, StepsFor, offline_llm, worked_steps
from pipeline.generate import CONCURRENCY, Failing, Runner, Stats
from pipeline.languages import LANGUAGES, WAVE_1, WAVE_2
from pipeline.prompts import example_facts
from pipeline.sources import (
    load_pack,
    pack_path,
    translate_prompts_hash,
    translation_hash,
    write_pack,
)
from pipeline.translate_prompts import (
    TranslationOut,
    judge_messages,
    repair_messages,
    translate_messages,
)

CACHE = ROOT / "pipeline" / ".cache" / "translate"  # units that passed, so a rerun skips them
PROMPTS_FILE = ROOT / "backend" / "app" / "content" / "prompts.json"
STATS_FILE = ROOT / "evals" / "translation-stats.json"
REPORT_FILE = ROOT / "evals" / "translation-report.md"
UI_STATS_FILE = ROOT / "evals" / "translation-ui-stats.json"
AT_ONCE = 3  # languages translated at the same time
REPAIRS = 3  # times the texts that fail are asked for again
GUESS_USD = 1.8  # the cost of one language before any has been measured


class TranslationError(Exception):
    """A language could not be translated completely."""


@dataclass
class LanguageResult:
    lang: str
    shipped: bool
    usd: float
    stats: dict[str, Any]
    failing: list[str] = field(default_factory=list)


ItemCheck = Callable[[dict[str, str]], Failing]  # translated texts by path -> problems


def prompt_problems(path: str, text: str) -> list[str]:
    """A problem prompt is short, has no digits, and only the solve prompt has `{var}`."""
    problems = []
    if any(c.isdigit() for c in text):
        problems.append("no digits in a prompt")
    wants = 1 if path == "prompts.solve" else 0
    if text.count("{var}") != wants or text.count("{") != wants:
        problems.append("`{var}` exactly once in the solve prompt, nowhere else")
    if len(text) > 60:
        problems.append("at most 60 characters")
    return problems


def prompts_check(got: dict[str, str]) -> Failing:
    return {p: why for p, text in got.items() if (why := prompt_problems(p, text))}


def item_problems(
    english: dict[str, str],
    got: dict[str, str],
    extra: ItemCheck | None,
    limit: Callable[[str, str], int] | None = None,
) -> Failing:
    failing: Failing = {}
    present = {p: got[p] for p in english if p in got}
    for path, text in english.items():
        if path not in got:
            failing[path] = ["missing"]
            continue
        cap = limit(path, text) if limit else None
        found = item_findings(path, text, got[path], cap)
        if found:
            failing[path] = [f"{f.check}: {f.detail}" for f in found]
    for path, why in (extra(present) if extra and present else {}).items():
        failing.setdefault(path, []).extend(why)
    return failing


async def review(
    runner: Runner,
    language: str,
    english: dict[str, str],
    got: dict[str, str],
    extra: ItemCheck | None = None,
    limit: Callable[[str, str], int] | None = None,
) -> Failing:
    """The problems of translations `got` of `english`: the item checks, then the judge on the
    texts that pass them."""
    failing = item_problems(english, got, extra, limit)
    pairs = {p: f"EN: {english[p]}\nTR: {got[p]}" for p in english if p not in failing}
    judged = await runner.judge("", "", pairs, messages=judge_messages(language, pairs))
    if judged is None:
        raise TranslationError("the judge gave no verdict")
    if "*" in judged:  # a judge field that names no item: ask for every judged text
        judged = {p: judged["*"] for p in pairs}
    return {**judged, **failing}


async def translate_unit(
    runner: Runner,
    language: str,
    context: str,
    english: dict[str, str],
    extra: ItemCheck | None = None,
    limit: Callable[[str, str], int] | None = None,
    log: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """One unit of texts: translated in one call, then every text is checked and judged; the
    texts that fail are asked for again on their own, with their problems, up to REPAIRS
    times. Raises when any text still fails: a language ships complete or not at all. Each
    repair is appended to `log` (path, before, after, why)."""

    key = hashlib.sha256(
        json.dumps(
            [language, translate_prompts_hash(), context, english], ensure_ascii=False
        ).encode()
    ).hexdigest()
    cached = CACHE / f"{key}.json"
    if cached.exists():  # checked and judged before; the checks are cheap, so run them again
        got: dict[str, str] = json.loads(cached.read_text(encoding="utf-8"))
        if not item_problems(english, got, extra, limit):
            return got

    async def evaluate(paths: list[str]) -> Failing:
        return await review(runner, language, {p: english[p] for p in paths}, got, extra, limit)

    out = None
    for _ in range(2):
        out = await runner.call(
            "generate", translate_messages(language, context, english), TranslationOut
        )
        if out is not None:
            break
    if out is None:
        raise TranslationError("no output")
    got = {item.id: item.text.strip() for item in out.items if item.id in english}
    failing = await evaluate(list(english))
    for _ in range(REPAIRS):
        if not failing:
            break
        runner.stats.retries += 1
        asked = {
            p: {"english": english[p], "earlier": got.get(p, ""), "problems": "; ".join(why)}
            for p, why in failing.items()
        }
        again = await runner.call(
            "generate", repair_messages(language, context, asked), TranslationOut
        )
        if again is not None:
            for item in again.items:
                if item.id in asked:
                    if log is not None:
                        why = asked[item.id]["problems"]
                        before = got.get(item.id, "")
                        log.append(
                            {
                                "path": item.id,
                                "before": before,
                                "after": item.text.strip(),
                                "why": why,
                            }
                        )
                    got[item.id] = item.text.strip()
        failing = await evaluate(list(failing))
    if failing:
        raise TranslationError("\n".join(f"{p}: {'; '.join(why)}" for p, why in failing.items()))
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    return got


def failure_lines(err: Exception) -> list[str]:
    """Why a language failed, for the stats: a TranslationError's lines, or the error itself."""
    why = str(err) if isinstance(err, TranslationError) else f"{type(err).__name__}: {err}"
    return why.splitlines()


async def named[T](name: str, job: Awaitable[T]) -> T:
    """`job`, with `name` (the topic) put before each line of its TranslationError."""
    try:
        return await job
    except TranslationError as err:
        lines = "\n".join(f"{name}: {line}" for line in str(err).splitlines())
        raise TranslationError(lines) from err


def units(english: Pack) -> list[tuple[str, dict[str, str]]]:
    """A pack's texts in units of one call: the pack text, each worked example's
    explanations, the misconception cards and the practice hints, each with its context."""
    texts = prose_paths(english)
    groups: dict[str, dict[str, str]] = {}
    for path, text in texts.items():
        head = path.split(".")[0]
        if head.startswith("worked_examples["):
            key = head
        elif head.startswith("misconceptions["):
            key = "misconceptions"
        elif head.startswith("practice["):
            key = "practice"
        else:
            key = "text"
        groups.setdefault(key, {})[path] = text
    topic = f"Topic: {english.title} (grades {', '.join(map(str, english.grades))})."
    out = []
    for key, group in groups.items():
        context = topic
        if key.startswith("worked_examples["):
            example = english.worked_examples[int(key[len("worked_examples[") : -1])]
            context += "\nThe worked example these explanations belong to:\n"
            context += example_facts(example)
        elif key == "misconceptions":
            context += "\nCards about student misconceptions, read by the teacher."
        elif key == "practice":
            context += "\nHints for practice problems, shown one by one to the teacher."
        out.append((context, group))
    return out


async def translate_language(
    lang: str,
    llm: LLM,
    model: str,
    stats: Stats,
    slots: asyncio.Semaphore | None = None,
    steps_for: StepsFor = worked_steps,
) -> tuple[list[Pack], dict[str, str]]:
    """The language's prompts and three packs, all checked; raises TranslationError if any
    part fails. Nothing is written here; `stats` counts the calls either way."""
    language = LANGUAGES[lang]
    runner = Runner(llm, stats, slots=slots)
    english_prompts = {f"prompts.{kind}": text for kind, text in PROMPTS["en"].items()}
    prompt_job = translate_unit(
        runner,
        language,
        "Instructions shown above a math problem, such as `2*x + 6 = 10`. `{var}` is the "
        "letter to solve for. Keep them short and end each the way the English does.",
        english_prompts,
        prompts_check,
    )
    englishes = {topic: load_pack(topic, "en") for topic in TOPIC_IDS}
    owners: list[TopicId] = []
    jobs = []
    for topic in TOPIC_IDS:
        for context, group in units(englishes[topic]):
            owners.append(topic)
            jobs.append(named(topic, translate_unit(runner, language, context, group)))
    results = await asyncio.gather(named("prompts", prompt_job), *jobs, return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    if errors:
        if not all(isinstance(e, TranslationError) for e in errors):
            raise next(e for e in errors if not isinstance(e, TranslationError))
        raise TranslationError("\n".join(str(e) for e in errors))
    prompt_texts = results[0]
    assert isinstance(prompt_texts, dict)
    prompts = {path.split(".", 1)[1]: text for path, text in prompt_texts.items()}
    translated: dict[TopicId, dict[str, str]] = {topic: {} for topic in TOPIC_IDS}
    for topic, r in zip(owners, results[1:], strict=True):
        assert isinstance(r, dict)
        translated[topic].update(r)

    PROMPTS[lang] = prompts  # the schema validates prompts against PROMPTS
    try:
        packs = []
        for topic in TOPIC_IDS:
            english = englishes[topic]
            data = english.model_dump(mode="json")
            for path in prose_paths(english):
                set_path(data, path, translated[topic][path])
            pack = Pack.model_validate(
                {
                    **data,
                    "lang": lang,
                    "machine_translated": True,
                    "source_hash": translation_hash(topic),
                    "model": model,
                }
            )
            pack = with_prompts(pack, lang)
            found = translation_findings(pack, english, translation_hash(topic), steps_for)
            if found:
                raise TranslationError("\n".join(f"{topic}: {f}" for f in found))
            packs.append(pack)
    except Exception:
        PROMPTS.pop(lang, None)
        raise
    return packs, prompts


def with_prompts(pack: Pack, lang: str) -> Pack:
    """The pack with every problem prompt in `lang`."""
    from app.content.schema import prompt_for

    data = pack.model_dump(mode="json")
    for i, e in enumerate(pack.worked_examples):
        set_path(
            data, f"worked_examples[{i}].prompt", prompt_for(e.problem.kind, e.problem.expr, lang)
        )
    for i, m in enumerate(pack.misconceptions):
        p = m.check_question.problem
        set_path(
            data, f"misconceptions[{i}].check_question.prompt", prompt_for(p.kind, p.expr, lang)
        )
    for i, item in enumerate(pack.practice):
        p = item.problem
        set_path(data, f"practice[{i}].prompt", prompt_for(p.kind, p.expr, lang))
    return Pack.model_validate(data)


def save_prompts(lang: str, prompts: dict[str, str]) -> None:
    data = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    data[lang] = prompts
    ordered = {"en": data["en"], **{k: data[k] for k in sorted(data) if k != "en"}}
    PROMPTS_FILE.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")


def prune() -> list[str]:
    """Removes the packs and prompts of every language whose packs shipped but whose UI strings
    did not (translate_ui.py), and marks its packs not shipped, so the API serves only
    languages the app offers and `translate_ui.py --packs` skips it. Returns those languages."""
    results, ui = load_stats(), _load(UI_STATS_FILE)
    gone = [
        lang
        for lang, r in results.items()
        if r["shipped"] and lang in ui and not ui[lang]["shipped"]
    ]
    data = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    for lang in gone:
        data.pop(lang, None)
        PROMPTS.pop(lang, None)
        for topic in TOPIC_IDS:
            pack_path(topic, lang).unlink(missing_ok=True)
        folder = pack_path(TOPIC_IDS[0], lang).parent
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
        results[lang] |= {"shipped": False, "pruned": "its UI strings did not ship"}
    if gone:
        PROMPTS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        STATS_FILE.write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return gone


def load_stats() -> dict[str, dict[str, Any]]:
    if not STATS_FILE.exists():
        return {}
    data: dict[str, dict[str, Any]] = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    return data


def flag_rate(stats: dict[str, Any]) -> float:
    judged = stats.get("judged_items", 0)
    return sum(stats.get("judge_flags", {}).values()) / judged if judged else 0.0


def _load(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _row(lang: str, r: dict[str, Any] | None) -> str:
    if r is None:
        return "not run | | | | |"
    s = r["stats"]
    calls = s.get("calls", {})
    return (
        f"{'yes' if r['shipped'] else 'no'} | {calls.get('generate', 0)} / "
        f"{calls.get('judge', 0)} | {s.get('retries', 0)} | {flag_rate(s):.1%} | ${r['usd']:.2f}"
    )


def write_report(results: dict[str, dict[str, Any]], model: str) -> None:
    """evals/translation-report.md from the pack and UI stats files: per language, whether it
    ships, calls, repairs, judge flag rate and cost; then what failed, and every change the
    UI review pass made."""
    ui = _load(UI_STATS_FILE)
    langs = [lang for lang in LANGUAGES if lang in results or lang in ui]
    not_run = [lang for lang in LANGUAGES if lang not in results and lang not in ui]
    ships = [
        lang
        for lang in langs
        if results.get(lang, {}).get("shipped") and ui.get(lang, {}).get("shipped")
    ]
    total = sum(r["usd"] for r in results.values()) + sum(r["usd"] for r in ui.values())
    lines = [
        "# Translation report",
        "",
        f"Written by `pipeline/translate.py` and `pipeline/translate_ui.py` with model `{model}`.",
        "A language ships only when its prompts, its three packs and all its UI strings pass.",
        "",
        "- Packs are translated from the English packs. The math is copied and verified identical "
        "(`pipeline/checks.py: translation_findings`): every math field, and every backtick span "
        "inside the prose, character for character.",
        "- UI strings must compile as ICU for their locale with the same arguments and the "
        "locale's plural categories (`pipeline/icu_check.mjs`).",
        "- The judge compares each English text with its translation and reports errors (meaning, "
        "math terms, grammar). Flagged texts are asked for again with the problems, up to 3 "
        "times; that is the review pass. Its changes to UI strings are listed below.",
        "- Judge flag rate: the share of judged texts a judge majority flagged at least once.",
        "",
        f"Ships: {', '.join(ships) or 'none'}. Total cost: about ${total:.2f}.",
        f"Not run: {', '.join(not_run) or 'none'}.",
        "",
        "Cost, calls, repairs and flag rate add up every recorded run of a language. A rerun "
        "reuses the units that already passed, so it adds little.",
        "",
        "| Language | Packs ship | Calls | Repairs | Flag rate | Cost | UI ships | Calls | Repairs "
        "| Flag rate | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for lang in langs:
        lines.append(
            f"| {lang} ({LANGUAGES[lang]}) | {_row(lang, results.get(lang))} | "
            f"{_row(lang, ui.get(lang))} |"
        )
    for lang in langs:
        failing = [*results.get(lang, {}).get("failing", []), *ui.get(lang, {}).get("failing", [])]
        if failing and lang not in ships:
            lines += ["", f"## {lang}: left out", ""]
            if results.get(lang, {}).get("pruned"):
                lines += [
                    "Its packs passed, but they were removed (`translate.py --prune`): a "
                    "language's packs are kept only when its UI strings ship too.",
                    "",
                ]
            lines += [f"- {f}" for f in failing]
    for lang in langs:
        changes = ui.get(lang, {}).get("changes", [])
        if changes:
            lines += [
                "",
                f"## {lang}: UI review changes",
                "",
                "| Key | Before | After | Why |",
                "|---|---|---|---|",
            ]
            for c in changes:
                cells = [c["path"], c["before"], c["after"], c["why"]]
                lines.append(
                    "| "
                    + " | ".join(x.replace("|", "\\|").replace("\n", " ") for x in cells)
                    + " |"
                )
    REPORT_FILE.write_text("\n".join(lines) + "\n")


async def run(
    langs: list[str],
    budget: float,
    steps_for: StepsFor = worked_steps,
    per_lang_usd: float | None = None,
) -> None:
    """Translates `langs`, AT_ONCE at a time, stopping before the total cost (including
    earlier runs recorded in the stats file) would pass `budget`."""
    from pipeline.verify import cost_usd

    llm, model = offline_llm()
    results = load_stats()
    slots = asyncio.Semaphore(CONCURRENCY + 4)
    todo = list(langs)
    while todo:
        spent = sum(r["usd"] for r in results.values())
        spent += sum(r["usd"] for r in _load(UI_STATS_FILE).values())
        measured = [r.get("last_usd", r["usd"]) for r in results.values() if r["usd"] > 0]
        per_lang = float(max(measured)) if measured else GUESS_USD
        if per_lang_usd is not None:  # a retry from the cache costs far less than a language
            per_lang = per_lang_usd
        batch: list[str] = []
        while todo and len(batch) < AT_ONCE and spent + per_lang * (len(batch) + 1) <= budget:
            batch.append(todo.pop(0))
        if not batch:
            print(f"stopping: ${spent:.2f} spent, the next language could pass ${budget:.2f}")
            print(f"not translated: {', '.join(todo)}")
            break

        async def one(lang: str) -> LanguageResult:
            stats = Stats()
            try:
                packs, prompts = await translate_language(lang, llm, model, stats, slots, steps_for)
            except Exception as err:  # anything: its cost still goes in the stats
                failing = failure_lines(err)
                return LanguageResult(lang, False, cost_usd(stats), _plain(stats), failing)
            save_prompts(lang, prompts)
            for pack in packs:
                write_pack(pack)
            return LanguageResult(lang, True, cost_usd(stats), _plain(stats))

        for result in await asyncio.gather(*(one(lang) for lang in batch)):
            before = results.get(result.lang, {})  # a rerun adds to the earlier runs
            results[result.lang] = {
                **asdict(result),
                "stats": merged(before.get("stats", {}), result.stats),
                "usd": result.usd + before.get("usd", 0.0),
                "last_usd": result.usd,
            }
            print(
                f"{result.lang}: {'shipped' if result.shipped else 'LEFT OUT'}, ${result.usd:.2f}"
            )
            for line in result.failing[:10]:
                print(f"  {line}")
        STATS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        write_report(results, model)
    print(f"total: ${sum(r['usd'] for r in results.values()):.2f}")


def merged(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Two runs' stats added up, so a retry adds to a language's numbers."""
    out = dict(new)
    for key, value in old.items():
        if isinstance(value, (int, float)) and isinstance(new.get(key), (int, float)):
            out[key] = value + new[key]
        elif isinstance(value, dict) and isinstance(new.get(key), dict):
            out[key] = {k: value.get(k, 0) + new[key].get(k, 0) for k in {*value, *new[key]}}
    return out


def _plain(stats: Stats) -> dict[str, Any]:
    data = asdict(stats)
    data["calls"] = dict(stats.calls)
    data["judge_flags"] = dict(stats.judge_flags)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--lang", nargs="*", default=[], choices=list(LANGUAGES))
    parser.add_argument("--wave", type=int, choices=[1, 2])
    parser.add_argument("--budget", type=float, default=50.0, help="USD cap, all runs together")
    parser.add_argument(
        "--per-lang-usd", type=float, help="the cost to assume per language (a cached retry)"
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="remove the packs and prompts of languages whose UI strings did not ship",
    )
    args = parser.parse_args()
    if args.prune:
        gone = prune()
        print(f"pruned: {', '.join(gone) or 'none'}")
        from app.config import get_settings

        write_report(load_stats(), get_settings().model_offline)
        return
    langs = list(args.lang)
    if args.wave:
        langs += list(WAVE_1 if args.wave == 1 else WAVE_2)
    if not langs:
        parser.error("give --lang or --wave")
    asyncio.run(run(langs, args.budget, per_lang_usd=args.per_lang_usd))


if __name__ == "__main__":
    main()
