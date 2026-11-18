# pipeline

Offline generation and verification of the lesson packs (`content/generated/<lang>/<topic>.json`).

```bash
cp /path/to/.env .env   # Azure OpenAI endpoint and key; never committed
uv run --project backend python pipeline/generate.py --topic all --lang en
uv run --project backend python pipeline/verify.py --lang en --judge --report evals/verify-report.md
```

- **Who writes what:** sympy (`app.math.worked_solution`) writes every step and answer. The LLM (`MODEL_OFFLINE`, through `app.llm`) writes only prose: the pack text, and each step's why, another way and picture caption. Misconceptions and practice are copied from `content/source/` and `content/practice/`.
- **Every piece of prose is checked:** the deterministic checks in `checks.py` run first, then an LLM judge, which decides by a majority of 3 when it flags anything.
- **On failure:** one targeted retry that quotes the findings, then up to 3 fresh samples. What still fails ships as `null` and is listed in the pack's `unavailable`; it is never shipped unverified.
- **`verify.py`:** re-runs every check on the committed packs, and `make test` runs it too. A pack built from older sources is stale: `source_hash` covers the lesson, misconceptions, practice, `examples.py` and `prompts.py`.

## Translations (T9)

    uv run --project backend python pipeline/translate.py --lang fr de   # or --wave 1|2
    uv run --project backend python pipeline/translate_ui.py --lang fr de  # or --packs
    uv run --project backend python pipeline/translate_ui.py --packs --recheck   # after en.json changes
    uv run --project backend python pipeline/translate_ui.py --lang ru --review math.speech.fractionSimple
    uv run --project backend python pipeline/verify.py --lang all [--judge]

- `translate.py` translates the committed English packs and the problem prompts
  (`backend/app/content/prompts.json`). Math fields are copied; every backtick span in the prose
  must come back character for character (`checks.py: translation_findings`).
- `translate_ui.py` translates `frontend/src/locales/en.json`; each message must compile as ICU
  for its locale with the same arguments and plural categories (`icu_check.mjs`, Node), and
  say a plural's count wherever the English does. A CLDR category is not a number (French `one`
  is also 0, Russian `one` also 21), so en.json writes a literal "one" as `=1 {one}`, and only an
  `=N` branch (or Arabic's `zero`, which is only 0) may put the number in words.
- `--recheck` translates again only the strings of a locale file that fail today's checks or
  were translated from different English (per-key hashes in
  `evals/translation-ui-sources.json`; `--seed-sources` records today's English, no calls);
  `--review KEY...` only checks and judges committed strings, e.g. after a hand fix. Both are
  recorded in the stats and the report like any run.
- Both use the same loop: check, judge (English against translation), then ask again for only
  the failing texts, up to 3 times. A language is written only when everything passes.
- `--budget` caps the total spend of both scripts together (stats in `evals/translation-*.json`,
  report in `evals/translation-report.md`). Units that passed are cached in `pipeline/.cache/`
  (git-ignored), so a retry pays only for what failed. The cache key and every translated
  pack's `source_hash` both hash `translate_prompts.py`, so editing it (even a comment) makes
  every translation stale and redoes it.
- A language is offered in the UI only when listed in `frontend/src/i18n/languages.ts`
  (`AVAILABLE`): complete UI strings and all three packs. Packs whose UI strings did not ship
  are removed from `content/generated/` and `prompts.json`, so the API serves only offered
  languages. Tests tie `AVAILABLE`, the packs on disk and `prompts.json` to the `shipped` flags
  in both stats files.
