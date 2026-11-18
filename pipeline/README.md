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
