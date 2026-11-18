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
    uv run --project backend python pipeline/verify.py --lang all [--judge]

- `translate.py` translates the committed English packs and the problem prompts
  (`backend/app/content/prompts.json`). Math fields are copied; every backtick span in the prose
  must come back character for character (`checks.py: translation_findings`).
- `translate_ui.py` translates `frontend/src/locales/en.json`; each message must compile as ICU
  for its locale with the same arguments and plural categories (`icu_check.mjs`, Node).
- Both use the same loop: check, judge (English against translation), then ask again for only
  the failing texts, up to 3 times. A language is written only when everything passes.
- `--budget` caps the total spend of both scripts together (stats in `evals/translation-*.json`,
  report in `evals/translation-report.md`). Units that passed are cached in `pipeline/.cache/`
  (git-ignored), so a retry pays only for what failed.
- A language is offered in the UI only when listed in `frontend/src/i18n/languages.ts`
  (`AVAILABLE`): complete UI strings and all three packs.
