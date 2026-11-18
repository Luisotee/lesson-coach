"""Prompts and output models for translating packs (translate.py).

Kept apart from prompts.py, which is hashed into the English packs' `source_hash`: changing
translation prompts must not make the English packs stale. TRANSLATE_VERSION is hashed into
each translated pack instead.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict

TRANSLATE_VERSION = "2"  # bump when a prompt here changes, so every translation is redone

OUTPUT_ONLY = "Output content only. Do not address the user."


def translate_system(language: str) -> str:
    return f"""You translate teaching material for math teachers of grades 6-9 from English into
{language}. The teachers refresh a topic before they teach it; write as a careful native
editor of a school math book in {language} would: plain, warm, short full sentences, and the
standard school math terms of the language (the words teachers there use in class).

Rules:
- Translate every item's text faithfully. Add nothing, drop nothing, change no fact or example.
- Copy every span in backticks exactly as it is, character for character, including the
  backticks: `2*x + 6 = 10` stays `2*x + 6 = 10`. Never translate, reorder or reformat math.
  Move a span within the sentence if the grammar needs it.
- Write every number with the digits 0-9, as in the English. Never use other digit forms.
- Keep each item about as long as the English; never more than 1.5 times as long.
- Keep placeholders such as {{var}} exactly as they are.
- Return one entry per item, with the item's id unchanged.
{OUTPUT_ONLY}"""


def judge_system(language: str) -> str:
    return f"""You check a translation from English into {language} of teaching material for math
teachers. Each item gives the English (EN) and the translation (TR). Report only real errors,
one entry per error, with the item's id as the field name and the verdict "unsupported":
- the translation changes, adds or drops meaning or a fact;
- it changes the math, or uses a wrong math term (not the one teachers use in {language});
- it is ungrammatical, or a native reader would not understand it as intended.
Do not report style preferences, or wording that is correct but could be smoother. Leave out
items with no error; for a good translation the list is empty. Give a short reason in English.
{OUTPUT_ONLY}"""


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemOut(Out):
    id: str
    text: str


class TranslationOut(Out):
    items: list[ItemOut]


def translate_messages(language: str, context: str, items: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": translate_system(language)},
        {
            "role": "user",
            "content": f"<context>\n{context}\n</context>\n<items>\n"
            f"{json.dumps(items, indent=1, ensure_ascii=False)}\n</items>\n"
            f"Translate all {len(items)} items into {language}.",
        },
    ]


def judge_messages(language: str, pairs: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": judge_system(language)},
        {
            "role": "user",
            "content": f"<items>\n{json.dumps(pairs, indent=1, ensure_ascii=False)}\n</items>",
        },
    ]


def repair_messages(
    language: str, context: str, items: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    """Asks again for only the items that failed: each with its English, the translation that
    failed and the problems found."""
    return [
        {"role": "system", "content": translate_system(language)},
        {
            "role": "user",
            "content": f"<context>\n{context}\n</context>\n<items>\n"
            f"{json.dumps(items, indent=1, ensure_ascii=False)}\n</items>\n"
            f"Each item has the English, your earlier translation and the problems a checker "
            f"found in it. Translate these {len(items)} items into {language} again with the "
            "problems fixed, following every rule.",
        },
    ]
