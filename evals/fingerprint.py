"""The hash that pins `evals/results.yaml` to what was evaluated.

It covers the prompts and schemas (rendered from `app.llm.prompts`, so formatting-only code
changes don't count), the packs the eval cases read (English only: language packs added later
don't make the results stale), the model-facing config defaults, the judge's prompt and model,
and the eval inputs (cases, images, truth, hand labels). `backend/tests/test_evals.py`
recomputes it without calling any model.
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


def _files(paths: list[Path]) -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
        if p.is_file()
    }


def parts() -> dict[str, Any]:
    from evals.judge import JUDGE_MODEL, JUDGE_SYSTEM, judge_schema

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
        "judge": {"system": JUDGE_SYSTEM, "schema": judge_schema(), "model": JUDGE_MODEL},
        "inputs": _files(
            [
                EVALS / "mistakes.yaml",
                EVALS / "judge_labels.yaml",
                *(EVALS / "transcription").glob("*.yaml"),
                *(EVALS / "transcription").glob("*.png"),
                *(EVALS / "transcription").glob("*.jpg"),
            ]
        ),
    }


def fingerprint() -> str:
    blob = json.dumps(parts(), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()
