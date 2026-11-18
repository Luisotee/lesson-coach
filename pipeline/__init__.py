"""Offline content pipeline: generate.py builds packs, verify.py checks them."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:  # so `app.*` (math core, schema, LLM client) imports work
    sys.path.insert(0, str(BACKEND))
