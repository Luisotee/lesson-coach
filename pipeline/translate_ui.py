"""Translates the UI strings (frontend/src/locales/en.json) into other languages, offline.

    uv run --project backend python pipeline/translate_ui.py --lang fr de
    uv run --project backend python pipeline/translate_ui.py --packs --budget 50

`--packs` takes the languages whose packs translate.py shipped. Strings go in units of about
50 through translate.py's loop: deterministic checks (every ICU message compiles for its
locale, keeps its arguments and uses the locale's plural categories; digits 0-9), then the
judge comparing the English and the translation; the strings that fail are asked for again
with the problems, up to 3 times. That review is the second pass: every change it made is
recorded in evals/translation-report.md. A language's locale file is written only when all of
its strings pass.
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
    load_stats,
    named,
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


def context(lang: str, section: str) -> str:
    categories = ", ".join(plural_categories(lang))
    text = f"""User interface strings of Lesson Coach, a web app where math teachers of grades 6-9
refresh a topic and prepare lessons. Buttons and links are short; labels are plain; the tone is
calm and never judges. This unit is the `{section}` section of the app.

The strings are ICU MessageFormat:
- Keep every {{argument}} name, `#`, and the words plural, select and other exactly.
- Translate only the text. In a plural, use exactly this language's CLDR categories:
  {categories} (plus any `=N` branches the English has), each with the right word forms.
- Keep nested braces balanced. Do not add or drop arguments."""
    if section == "math":
        text += """
- `math.speech.*` and `math.op.*` are spoken aloud by screen readers to describe math: write
  the words a teacher of this language says aloud (plus, minus, times, over, equals, squared,
  one half, two thirds...), in the order the language says them."""
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


async def translate_ui(
    lang: str, llm: LLM, stats: Stats, log: list[dict[str, str]], slots: asyncio.Semaphore | None
) -> dict[str, Any]:
    """The language's locale data, every string checked; raises TranslationError if any
    string fails."""
    shape = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    english = flatten(shape)
    runner = Runner(llm, stats, slots=slots)
    check = icu_check(lang, english)
    jobs = [
        named(
            section,
            translate_unit(
                runner, LANGUAGES[lang], context(lang, section), texts, check, limit, log
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
    flat: dict[str, str] = {}
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


async def run(langs: list[str], budget: float) -> None:
    from pipeline.translate import write_report
    from pipeline.verify import cost_usd

    llm, model = offline_llm()
    results = load_ui_stats()
    slots = asyncio.Semaphore(CONCURRENCY + 4)
    todo = list(langs)
    while todo:
        measured = [r["last_usd"] for r in results.values() if r.get("last_usd")]
        per_lang = max(measured) if measured else GUESS_USD
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
                data = await translate_ui(lang, llm, stats, log, slots)
            except TranslationError as err:
                return {
                    "lang": lang,
                    "shipped": False,
                    "failing": str(err).splitlines(),
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
            result["usd"] = result["last_usd"] + results.get(lang, {}).get("usd", 0.0)
            results[lang] = result
            status = "shipped" if result["shipped"] else "LEFT OUT"
            print(
                f"{lang} ui: {status}, ${result['last_usd']:.2f}, {len(result['changes'])} changes"
            )
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
    args = parser.parse_args()
    langs = list(args.lang)
    if args.packs:
        langs += [lang for lang, r in load_stats().items() if r["shipped"] and lang not in langs]
    if not langs:
        parser.error("give --lang or --packs")
    asyncio.run(run(langs, args.budget))


if __name__ == "__main__":
    main()
