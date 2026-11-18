"""Prompts and output schemas for the live LLM calls: the mistake diagnosis, the moves for a
rule-matched mistake (the same `mistake` task) and transcription.

Layout for prompt caching: the fixed instructions first, then the topic's misconception list
and follow-up options (the same for every request on a topic), then the request itself in
delimiters, with the target language last. The math in the request is our parser's normalised
text, not free text, and sympy's verified findings travel with it.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

OUTPUT_ONLY = "Output content only. Do not address the user."
# The packs' convention, which the page draws as handwritten math: anything else shows raw `*`.
MATH_IN_TEXT = """Put every piece of math in backticks, written as plain text that a math
parser reads: `1/2`, `2*x`, `x = 3`, `3*x + 5 = 20`, `-4`. That includes a number that is part
of the math (the `5` in `3*x + 5`); a line number or a count in words needs none. Never write
math outside backticks."""

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
- margin_note: at most 60 characters of words (no math, no backticks) to write next to the
  student's work, such as "added the bottoms too", or null.
- what_to_say: probe (a question the teacher can ask the student), nudge (a short hint or
  question that points the student at where to look, without naming the rule or the steps to
  fix it: the student should still find the method), tell (what to explain if the student is
  still stuck; only here may you state the method).
- follow_up_id: one id from the follow-up list that would check the student's understanding
  next, or null.

Use only the math you were given: the problem, the student's answer and working, the
verified answer and the worked solution. Never compute, simplify or invent a new number or
expression; refer to steps in words instead.
{MATH_IN_TEXT}
Be kind and specific; never judge the student or the teacher, and give no scores or praise.
Write every text field in the requested language.
{OUTPUT_ONLY}"""

RULE_SAY_SYSTEM = f"""You help math teachers (grades 6-9) talk with a student about a wrong answer.
A math engine (sympy) has already checked that a known misconception gives exactly the
student's answer. You get that misconception, with three moves a teacher could use, written
for the misconception's own example problem. Rewrite the moves for the student's problem:
- probe: a question the teacher can ask the student.
- nudge: a short hint or question that points the student at where to look, without naming
  the rule or the steps to fix it: the student should still find the method.
- tell: what to explain if the student is still stuck; only here may you state the method.

Follow the example moves' style and intent, but about this problem only. Use only the math of
the request: the problem, the student's answer and working, the verified answer and the
worked solution. Never use the example problem's numbers. Never compute, simplify or invent
a new number or expression; refer to steps in words instead.
{MATH_IN_TEXT}
Be kind and specific; never judge the student, and give no scores or praise.
Set abstain to true, with the moves empty, when you can't write them for this problem from
the math given. Write every text field in the requested language.
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


# The models accept any length, and `clip` trims after parsing: a reply just over a cap is
# shortened at a word boundary, not thrown away. The caps are not in the JSON schema: Azure
# strict mode accepts maxLength/maxItems but enforces them by cutting text mid-word and
# merging array items (checked against gpt-5.5-live).
MAX_EXPLANATION = 900
MAX_SAY = 400
MAX_TELL = 600
MAX_MARGIN_NOTE = 60
MAX_SIDE = 200
MAX_OP = 30
MAX_LINES = 30


def clip(text: str, limit: int) -> str:
    """`text` trimmed to `limit` characters, at the last sentence end or word boundary."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]  # room for the "…"
    for end in (". ", "! ", "? "):
        at = cut.rfind(end)
        if at >= limit // 2:
            return cut[: at + 1]
    at = cut.rfind(" ")
    return (cut[:at] if at >= limit // 2 else cut).rstrip(" ,;:") + "…"


class WhatToSayOut(Model):
    probe: str
    nudge: str
    tell: str


class MistakeOut(Model):
    status: Literal["diagnosed", "slip", "unclear", "out_of_scope"]
    misconception_ids: list[str]
    explanation: str
    margin_note: str | None
    what_to_say: WhatToSayOut
    follow_up_id: str | None

    def clipped(self) -> MistakeOut:
        # The note is drawn and spoken as plain text, so a stray backtick is dropped.
        raw = self.margin_note.replace("`", "") if self.margin_note else None
        note = clip(raw, MAX_MARGIN_NOTE) if raw else None
        return MistakeOut(
            status=self.status,
            misconception_ids=self.misconception_ids,  # mistake.py dedupes, then caps at 2
            explanation=clip(self.explanation, MAX_EXPLANATION),
            margin_note=note or None,
            what_to_say=WhatToSayOut(
                probe=clip(self.what_to_say.probe, MAX_SAY),
                nudge=clip(self.what_to_say.nudge, MAX_SAY),
                tell=clip(self.what_to_say.tell, MAX_TELL),
            ),
            follow_up_id=self.follow_up_id,
        )


class RuleSayOut(Model):
    abstain: bool
    probe: str
    nudge: str
    tell: str

    def clipped(self) -> WhatToSayOut:
        return WhatToSayOut(
            probe=clip(self.probe, MAX_SAY),
            nudge=clip(self.nudge, MAX_SAY),
            tell=clip(self.tell, MAX_TELL),
        )


class LineOut(Model):
    left: str
    right: str
    op: str
    confidence: float
    cut: bool = False  # set by `clipped` when a side was too long: the math may have changed


class TranscribeOut(Model):
    lines: list[LineOut]

    def clipped(self) -> TranscribeOut:
        return TranscribeOut(
            lines=[
                LineOut(
                    left=line.left.strip()[:MAX_SIDE],
                    right=line.right.strip()[:MAX_SIDE],
                    op=line.op.strip()[:MAX_OP],
                    confidence=min(1.0, max(0.0, line.confidence)),
                    cut=len(line.left.strip()) > MAX_SIDE
                    or len(line.right.strip()) > MAX_SIDE
                    or len(line.op.strip()) > MAX_OP,
                )
                for line in self.lines[:MAX_LINES]
            ]
        )


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


RULE_SAY_SCHEMA = _object(
    {"abstain": {"type": "boolean"}, "probe": _string(), "nudge": _string(), "tell": _string()}
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


def rule_say_messages(
    *, misconception: dict[str, Any], request: dict[str, Any], lang: str
) -> list[dict[str, Any]]:
    """System instructions, then the matched misconception, then the request. The prompt
    (about 680 tokens) is under Azure's 1024-token caching minimum, so none of it is cached."""
    card = json.dumps(misconception, ensure_ascii=False)
    findings = json.dumps(request, ensure_ascii=False)
    return [
        {"role": "system", "content": RULE_SAY_SYSTEM},
        {"role": "system", "content": f"<misconception>\n{card}\n</misconception>"},
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
