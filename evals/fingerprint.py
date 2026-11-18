"""The hash that pins `evals/results.yaml` to what was evaluated.

It covers:
- the prompts and schemas as rendered from `app.llm.prompts`;
- the packs the eval cases read (English only: language packs added later don't make the
  results stale);
- the model-facing config defaults, and the judge's prompt, schema, model and effort;
- the raw bytes of the code that decides the results (`SOURCES`: the rules, the mistake
  pipeline and the math it uses, the two endpoints, the numbers guard, the Azure client, and
  the eval runner, judge and scoring), so even a comment-only change there needs a rerun;
- the eval inputs (cases, images, truth) and the hand labels.

`run` and `judge` stamp `fingerprint(labels=False)` on every output row; `summarize` refuses
rows whose stamp differs, then writes `fingerprint()` to results.yaml. The hand labels are
left out of the stamp because they only feed `summarize`: relabelling needs `summarize` only.
`backend/tests/test_evals.py` recomputes it without calling any model.

Not covered: `.env` or Container Apps overrides of the config (results.yaml records the
models and efforts that actually ran), and app code outside `SOURCES`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import Settings
from app.llm.prompts import (
    MISTAKE_SYSTEM,
    TRANSCRIBE_SCHEMA,
    TRANSCRIBE_SYSTEM,
    mistake_messages,
    mistake_schema,
    transcribe_messages,
)

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
PACK_LANGS = ("en",)  # every case is asked in English
CONFIG_FIELDS = (
    "model_live",
    "mistake_reasoning_effort",
    "mistake_max_completion_tokens",
    "transcribe_reasoning_effort",
    "transcribe_max_completion_tokens",
)
BACKEND = ROOT / "backend" / "app"
SOURCES = (
    *sorted((BACKEND / "math" / "rules").glob("*.py")),
    *(BACKEND / "math" / f"{m}.py" for m in ("pipeline", "steps", "worked", "canonical")),
    BACKEND / "math" / "problems.py",
    BACKEND / "api" / "mistake.py",
    BACKEND / "api" / "transcribe.py",  # holds the image checks before the model call
    BACKEND / "llm" / "guard.py",  # new_numbers
    BACKEND / "llm" / "azure.py",
    EVALS / "run.py",
    EVALS / "judge.py",
    EVALS / "metrics.py",
)


def _files(paths: list[Path]) -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
        if p.is_file()
    }


def parts(labels: bool = True) -> dict[str, Any]:
    from evals.judge import JUDGE_EFFORT, JUDGE_MODEL, JUDGE_SYSTEM, judge_schema

    sample = mistake_messages(
        topic="fractions",
        misconceptions=[{"id": "m", "belief": "b", "example": "1/2 + 1/3 -> 2/5"}],
        follow_ups=[{"id": "check:m", "problem": "1/4 + 1/4", "prompt": "p"}],
        request={"problem": {"kind": "evaluate", "expr": "1/2 + 1/3"}},
        lang="en",
    )
    content = ROOT / "content" / "generated"
    return {
        "prompts": {
            "mistake_system": MISTAKE_SYSTEM,
            "transcribe_system": TRANSCRIBE_SYSTEM,
            "mistake_messages": sample,
            "transcribe_messages": transcribe_messages("data:image/png;base64,"),
        },
        "schemas": {
            "mistake": mistake_schema(["m"], ["check:m"]),
            "transcribe": TRANSCRIBE_SCHEMA,
        },
        "packs": _files([p for lang in PACK_LANGS for p in (content / lang).glob("*.json")]),
        "config": {f: Settings.model_fields[f].default for f in CONFIG_FIELDS},
        "judge": {
            "system": JUDGE_SYSTEM,
            "schema": judge_schema(),
            "model": JUDGE_MODEL,
            "effort": JUDGE_EFFORT,
        },
        "sources": _files(list(SOURCES)),
        "inputs": _files(
            [
                EVALS / "mistakes.yaml",
                *([EVALS / "judge_labels.yaml"] if labels else []),
                *(EVALS / "transcription").glob("*.yaml"),
                *(EVALS / "transcription").glob("*.png"),
                *(EVALS / "transcription").glob("*.jpg"),
            ]
        ),
    }


def fingerprint(labels: bool = True) -> str:
    blob = json.dumps(parts(labels), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()
