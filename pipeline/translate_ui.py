"""Translates the UI strings (frontend/src/locales/en.json) into other languages, offline.

    uv run --project backend python pipeline/translate_ui.py --lang fr de
    uv run --project backend python pipeline/translate_ui.py --packs --budget 50
    uv run --project backend python pipeline/translate_ui.py --packs --recheck

`--packs` takes the languages whose packs translate.py shipped. Strings go in units of about
50 through translate.py's loop: deterministic checks (every ICU message compiles for its
locale, keeps its arguments and uses the locale's plural categories; digits 0-9), then the
judge comparing the English and the translation; the strings that fail are asked for again
with the problems, up to 3 times. That review is the second pass: every change it made is
recorded in evals/translation-report.md. A language's locale file is written only when all of
its strings pass. `--recheck` translates again only the strings of an existing locale file that
fail today's checks (after en.json changed a message, say) and keeps the rest. `--review KEY...`
only checks and judges those committed strings, e.g. after a hand fix; its result and cost are
recorded like a run's.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a script: make `pipeline` and `app` importable
    sys.path[:0] = [str(Path(__file__).resolve().parents[1] / p) for p in ("", "backend")]

from pipeline import ROOT
from pipeline.core import LLM, offline_llm
from pipeline.generate import CONCURRENCY, Failing, Runner, Stats
from pipeline.languages import LANGUAGES
from pipeline.translate import (
    AT_ONCE,
    UI_STATS_FILE,
    TranslationError,
    _plain,
    failure_lines,
    load_stats,
    merged,
    named,
    review,
    translate_unit,
)

LOCALES = ROOT / "frontend" / "src" / "locales"
UNIT = 50  # strings per call
GUESS_USD = 0.6
# Locales Intl knows better under another code (for plural rules).
INTL_LOCALE = {"prs": "fa-AF"}


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out.update(flatten(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


def unflatten(flat: dict[str, str], shape: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """`flat` in the key order and nesting of `shape` (the English file)."""
    out: dict[str, Any] = {}
    for key, value in shape.items():
        if isinstance(value, dict):
            out[key] = unflatten(flat, value, f"{prefix}{key}.")
        else:
            out[key] = flat[f"{prefix}{key}"]
    return out


def node(script: str, payload: dict[str, Any]) -> Any:
    done = subprocess.run(
        ["node", str(ROOT / "pipeline" / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return json.loads(done.stdout)


@functools.cache
def plural_categories(lang: str) -> list[str]:
    locale = INTL_LOCALE.get(lang, lang)
    done = subprocess.run(
        [
            "node",
            "-e",
            f"console.log(JSON.stringify(new Intl.PluralRules({json.dumps(locale)})"
            ".resolvedOptions().pluralCategories))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    categories: list[str] = json.loads(done.stdout)
    return categories


def icu_check(lang: str, english: dict[str, str]) -> Callable[[dict[str, str]], Failing]:
    def check(got: dict[str, str]) -> Failing:
        items = {k: [english[k], v] for k, v in got.items()}
        found: Failing = node(
            "icu_check.mjs", {"locale": INTL_LOCALE.get(lang, lang), "items": items}
        )
        return found

    return check


def context(lang: str, section: str, texts: dict[str, str] | None = None) -> str:
    categories = ", ".join(plural_categories(lang))
    text = f"""User interface strings of Lesson Coach, a web app where math teachers of grades 6-9
refresh a topic and prepare lessons. Buttons and links are short; labels are plain; the tone is
calm and never judges. This unit is the `{section}` section of the app.

The strings are ICU MessageFormat:
- Keep every {{argument}} name, `#`, and the words plural, select and other exactly.
- Translate only the text. In a plural, use exactly this language's CLDR categories:
  {categories} (plus any `=N` branches the English has), each with the right word forms.
- Keep nested braces balanced. Do not add or drop arguments."""
    if any(re.search(r"=\d", t) for t in (texts or {}).values()):
        # Only the units with `=N` branches get this, so the others stay cached.
        text += """
- An `=N` branch (`=1`, `=2`) means exactly that number: keep it, and only there may the number
  be said in words ("one", "half"). A CLDR category covers more numbers than its name (`one` is
  also 0 in French and 21, 31... in Russian), so in a category branch say the number with `#`
  and use the category only to choose the word forms that agree with it."""
    if section == "math":
        text += """
- `math.speech.*` and `math.op.*` are spoken aloud by screen readers to describe math: write
  the words a teacher of this language says aloud (plus, minus, times, over, equals, squared,
  one half, two thirds...), in the order the language says them.
- `math.speech.fractionSimple` may be restructured, keeping its arguments and `=N` branches, so
  that every count reads naturally: if the language says "one half" as one word, its `=1`
  branch is that word alone."""
    return text


def units(english: dict[str, str]) -> list[tuple[str, dict[str, str]]]:
    sections: dict[str, dict[str, str]] = {}
    for key, text in english.items():
        sections.setdefault(key.split(".")[0], {})[key] = text
    out = []
    for section, texts in sections.items():
        items = list(texts.items())
        for start in range(0, len(items), UNIT):
            out.append((section, dict(items[start : start + UNIT])))
    return out


def limit(_path: str, english: str) -> int:
    return max(200, 3 * len(english))


def failing_keys(lang: str) -> set[str]:
    """The keys of a committed locale file that are missing or fail today's checks, e.g. after
    en.json changed a message."""
    english = flatten(json.loads((LOCALES / "en.json").read_text(encoding="utf-8")))
    current = flatten(json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")))
    have = {k: current[k] for k in english if k in current}
    return set(english) - set(have) | set(icu_check(lang, english)(have))


async def translate_ui(
    lang: str,
    llm: LLM,
    stats: Stats,
    log: list[dict[str, str]],
    slots: asyncio.Semaphore | None,
    keys: set[str] | None = None,
    review_only: bool = False,
) -> dict[str, Any]:
    """The language's locale data, every string checked; raises TranslationError if any
    string fails. With `keys`, only those strings are translated and the rest are kept from
    the committed locale file; with `review_only` too, those committed strings are only
    checked and judged, not translated."""
    shape = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    english = flatten(shape)
    runner = Runner(llm, stats, slots=slots)
    check = icu_check(lang, english)
    flat: dict[str, str] = {}
    if keys is not None:
        flat = flatten(json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")))
        english = {k: v for k, v in english.items() if k in keys}
    if review_only:  # judge the committed strings as they are (e.g. after a hand fix)
        assert keys is not None
        found = await review(runner, LANGUAGES[lang], english, flat, check, limit)
        if found:
            raise TranslationError("\n".join(f"{p}: {'; '.join(w)}" for p, w in found.items()))
        return unflatten(flat, shape)
    jobs = [
        named(
            section,
            translate_unit(
                runner, LANGUAGES[lang], context(lang, section, texts), texts, check, limit, log
            ),
        )
        for section, texts in units(english)
    ]
    results = await asyncio.gather(*jobs, return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    if errors:
        if not all(isinstance(e, TranslationError) for e in errors):
            raise next(e for e in errors if not isinstance(e, TranslationError))
        raise TranslationError("\n".join(str(e) for e in errors))
    for r in results:
        assert isinstance(r, dict)
        flat.update(r)
    return unflatten(flat, shape)


def load_ui_stats() -> dict[str, dict[str, Any]]:
    if not UI_STATS_FILE.exists():
        return {}
    data: dict[str, dict[str, Any]] = json.loads(UI_STATS_FILE.read_text(encoding="utf-8"))
    return data


def spent() -> float:
    packs: float = sum(r["usd"] for r in load_stats().values())
    ui: float = sum(r["usd"] for r in load_ui_stats().values())
    return packs + ui


async def run(
    langs: list[str],
    budget: float,
    recheck: bool = False,
    per_lang_usd: float | None = None,
    review_keys: list[str] | None = None,
) -> None:
    """Translates `langs`' UI strings, AT_ONCE at a time, stopping before the total cost would
    pass `budget`. With `recheck`, a language that has a locale file gets only its failing
    strings translated again (`failing_keys`), and one with none failing is skipped. With
    `review_keys`, those committed strings are only checked and judged (a hand fix's review)."""
    from pipeline.translate import write_report
    from pipeline.verify import cost_usd

    llm, model = offline_llm()
    results = load_ui_stats()
    slots = asyncio.Semaphore(CONCURRENCY + 4)
    redo: dict[str, set[str] | None] = {
        lang: set(review_keys) if review_keys else None for lang in langs
    }
    if recheck:
        for lang in langs:
            if (LOCALES / f"{lang}.json").exists():
                redo[lang] = failing_keys(lang)
                if not redo[lang]:
                    print(f"{lang} ui: every string passes")
                    del redo[lang]
    todo = list(redo)
    while todo:
        measured = [r["last_usd"] for r in results.values() if r.get("last_usd")]
        per_lang = max(measured) if measured else GUESS_USD
        if per_lang_usd is not None:  # a recheck or a retry from the cache costs far less
            per_lang = per_lang_usd
        batch: list[str] = []
        while todo and len(batch) < AT_ONCE and spent() + per_lang * (len(batch) + 1) <= budget:
            batch.append(todo.pop(0))
        if not batch:
            print(f"stopping: ${spent():.2f} spent; not translated: {', '.join(todo)}")
            break

        async def one(lang: str) -> dict[str, Any]:
            stats: Stats = Stats()
            log: list[dict[str, str]] = []
            try:
                data = await translate_ui(
                    lang, llm, stats, log, slots, redo[lang], review_only=bool(review_keys)
                )
            except Exception as err:  # anything: its cost still goes in the stats
                return {
                    "lang": lang,
                    "shipped": False,
                    "failing": failure_lines(err),
                    "stats": _plain(stats),
                    "last_usd": cost_usd(stats),
                    "changes": log,
                }
            path = LOCALES / f"{lang}.json"
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            return {
                "lang": lang,
                "shipped": True,
                "failing": [],
                "stats": _plain(stats),
                "last_usd": cost_usd(stats),
                "changes": log,
            }

        for result in await asyncio.gather(*(one(lang) for lang in batch)):
            lang = result["lang"]
            before = results.get(lang, {})  # a rerun adds to the earlier runs
            result["usd"] = result["last_usd"] + before.get("usd", 0.0)
            result["stats"] = merged(before.get("stats", {}), result["stats"])
            result["changes"] = before.get("changes", []) + result["changes"]
            results[lang] = result
            status = "shipped" if result["shipped"] else "LEFT OUT"
            print(f"{lang} ui: {status}, ${result['last_usd']:.2f}")
            for line in result["failing"][:10]:
                print(f"  {line}")
        UI_STATS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        write_report(load_stats(), model)
    print(f"total spent on translation: ${spent():.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--lang", nargs="*", default=[], choices=list(LANGUAGES))
    parser.add_argument("--packs", action="store_true", help="every language with shipped packs")
    parser.add_argument("--budget", type=float, default=50.0, help="USD cap, packs and UI")
    parser.add_argument(
        "--review", nargs="+", metavar="KEY", help="only check and judge these committed strings"
    )
    parser.add_argument("--per-lang-usd", type=float, help="cost to expect per language")
    parser.add_argument(
        "--recheck",
        action="store_true",
        help="for a language with a locale file, translate only the strings that fail the checks",
    )
    args = parser.parse_args()
    langs = list(args.lang)
    if args.packs:
        langs += [lang for lang, r in load_stats().items() if r["shipped"] and lang not in langs]
    if not langs:
        parser.error("give --lang or --packs")
    asyncio.run(run(langs, args.budget, args.recheck, args.per_lang_usd, args.review))


if __name__ == "__main__":
    main()
