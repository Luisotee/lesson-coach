"""The LLM judge for the AI's free text (explanation, margin note, what to say).

Four dimensions, each "yes", "to some extent" or "no". It runs on the offline deployment
(GlobalStandard: the inputs are our own synthetic cases, no teacher data) through the app's
`AzureLLM` and its offline `judge` task, so it gets the same retries and token log. Its
scores are quoted only for the dimensions where it agrees with the hand labels (`judge_labels.yaml`, kappa >= 0.6).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.config import Settings
from app.llm.azure import AzureLLM
from app.llm.client import LLMResult

JUDGE_MODEL = Settings.model_fields["model_offline"].default
JUDGE_EFFORT = Settings.model_fields["judge_reasoning_effort"].default
DIMENSIONS = ("located", "actionable", "not_revealing", "non_judgmental")
Level = Literal["yes", "to some extent", "no"]

JUDGE_SYSTEM = """You review feedback that an assistant wrote for a math teacher about one
student's wrong answer. The math facts (the problem, the student's answer, the verified answer)
were checked by a computer algebra system; judge only the feedback text.

Rate four things, each "yes", "to some extent" or "no":
- located: does it say specifically where or in which idea the student went wrong (the step,
  the operation, the rule), rather than only that the answer is wrong?
- actionable: does it give the teacher something concrete to say or do next?
- not_revealing: do the probe and the nudge leave the work to the student, without giving
  away the correct answer or the finished method? (The "tell" may reveal it.)
- non_judgmental: is it free of blame, labels or remarks about the student's ability?

If the feedback says it can't tell what went wrong, rate located and actionable on whether
that is honest and still useful. Set cannot_judge to true only if the text is empty or
unreadable. Return only the JSON object."""


class JudgeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cannot_judge: bool
    located: Level
    actionable: Level
    not_revealing: Level
    non_judgmental: Level


def judge_schema() -> dict[str, Any]:
    level = {"type": "string", "enum": ["yes", "to some extent", "no"]}
    return {
        "type": "object",
        "properties": {"cannot_judge": {"type": "boolean"}, **{d: level for d in DIMENSIONS}},
        "required": ["cannot_judge", *DIMENSIONS],
        "additionalProperties": False,
    }


def judge_llm() -> AzureLLM:
    """The app's client; its `judge` task runs on `model_offline` with the judge settings."""
    return AzureLLM(Settings())


def judge_input(record: dict[str, Any]) -> str:
    text = record["ai_text"]
    return json.dumps(
        {
            "problem": record["problem"],
            "student_answer": record["student_answer"],
            "verified_answer": record["correct_answer"],
            "student_working": record.get("working") or [],
            "feedback": {
                "status": record["status"],
                "explanation": text["explanation"],
                "margin_note": text.get("margin_note"),
                "what_to_say": text["what_to_say"],
            },
        },
        ensure_ascii=False,
    )


async def judge(llm: AzureLLM, record: dict[str, Any]) -> LLMResult[JudgeOut]:
    return await llm.structured(
        task="judge",
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": judge_input(record)},
        ],
        schema_name="feedback_review",
        schema=judge_schema(),
        output=JudgeOut,
    )
