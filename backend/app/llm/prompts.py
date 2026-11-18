"""Prompts and output schemas for the two live LLM tasks.

Layout for prompt caching: the fixed instructions first, then the topic's misconception list
and follow-up options (the same for every request on a topic), then the request itself in
delimiters, with the target language last. The math in the request is our parser's normalised
text, not free text, and sympy's verified findings travel with it.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OUTPUT_ONLY = "Output content only. Do not address the user."

MISTAKE_SYSTEM = f"""You help math teachers (grades 6-9) understand a student's wrong answer.
A math engine (sympy) has already solved the problem and checked the student's work. Its
findings are always right: never compute the math yourself, never state a different answer,
and never contradict the engine.

Decide what most likely happened and reply with:
- status: "diagnosed" when a misconception explains the answer; "slip" for a one-off careless
  error (copying, a small arithmetic slip) rather than a belief; "unclear" when one answer is
  not enough to tell (prefer this to guessing); "out_of_scope" when the input is not a grade
  6-9 math problem with a student answer.
- misconception_ids: at most 2, best first, from the listed misconceptions, or "other" when a
  misconception explains it but none of the listed ones does. Empty unless "diagnosed".
- explanation: 1-3 short sentences for the teacher on what the student probably did.
- margin_note: at most 60 characters to write next to the student's work, such as "added the
  bottoms too", or null.
- what_to_say: probe (a question the teacher can ask the student), nudge (a hint that keeps the
  student thinking), tell (what to explain if the student is still stuck).
- follow_up_id: one id from the follow-up list that would check the student's understanding
  next, or null.

Write math as plain text (1/2, 2*x, x = 3). Be kind and specific; never judge the student or
the teacher, and give no scores or praise. Write every text field in the requested language.
{OUTPUT_ONLY}"""

TRANSCRIBE_SYSTEM = f"""Transcribe the lines of math in the image, top to bottom.
For each line give left and right (the two sides of "="; right is empty when there is no "="),
op (the operation written in the margin for that line, such as -5 or /3; empty when there is
none) and confidence (0 to 1, how sure you are of the reading).
Write plain text math: 2*x, 1/2, (x + 1), x^2, -3. Copy exactly what is written, mistakes
included: never correct, finish or solve anything. Ignore words, names and drawings that are
not math. If there is no math, return no lines.
{OUTPUT_ONLY}"""


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WhatToSayOut(Model):
    probe: str = Field(max_length=400)
    nudge: str = Field(max_length=400)
    tell: str = Field(max_length=600)


class MistakeOut(Model):
    status: Literal["diagnosed", "slip", "unclear", "out_of_scope"]
    misconception_ids: list[str]
    explanation: str = Field(max_length=900)
    margin_note: str | None
    what_to_say: WhatToSayOut
    follow_up_id: str | None


class LineOut(Model):
    left: str = Field(max_length=200)
    right: str = Field(max_length=200)
    op: str = Field(max_length=30)
    confidence: float = Field(ge=0, le=1)


class TranscribeOut(Model):
    lines: list[LineOut] = Field(max_length=30)


def _string() -> dict[str, Any]:
    return {"type": "string"}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def mistake_schema(misconception_ids: list[str], follow_up_ids: list[str]) -> dict[str, Any]:
    """A strict schema whose ids can only be the topic's own (plus "other")."""
    follow_up: dict[str, Any] = (
        {"anyOf": [{"type": "string", "enum": follow_up_ids}, {"type": "null"}]}
        if follow_up_ids
        else {"type": "null"}
    )
    return _object(
        {
            "status": {"type": "string", "enum": ["diagnosed", "slip", "unclear", "out_of_scope"]},
            "misconception_ids": {
                "type": "array",
                "items": {"type": "string", "enum": [*misconception_ids, "other"]},
            },
            "explanation": _string(),
            "margin_note": {"type": ["string", "null"]},
            "what_to_say": _object({"probe": _string(), "nudge": _string(), "tell": _string()}),
            "follow_up_id": follow_up,
        }
    )


TRANSCRIBE_SCHEMA = _object(
    {
        "lines": {
            "type": "array",
            "items": _object(
                {
                    "left": _string(),
                    "right": _string(),
                    "op": _string(),
                    "confidence": {"type": "number"},
                }
            ),
        }
    }
)


def mistake_messages(
    *,
    topic: str | None,
    misconceptions: list[dict[str, str]],
    follow_ups: list[dict[str, str]],
    request: dict[str, Any],
    lang: str,
) -> list[dict[str, Any]]:
    """System instructions, then the topic context (stable, cacheable), then the request."""
    context = json.dumps(
        {"topic": topic, "misconceptions": misconceptions, "follow_ups": follow_ups},
        ensure_ascii=False,
    )
    findings = json.dumps(request, ensure_ascii=False)
    return [
        {"role": "system", "content": MISTAKE_SYSTEM},
        {"role": "system", "content": f"<topic_context>\n{context}\n</topic_context>"},
        {
            "role": "user",
            "content": f"<request>\n{findings}\n</request>\n<language>{lang}</language>",
        },
    ]


def transcribe_messages(image_data_url: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": TRANSCRIBE_SYSTEM},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_url}}]},
    ]
