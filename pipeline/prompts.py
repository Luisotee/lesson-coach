"""Prompts and structured-output models for the offline LLM calls.

Layout for prompt caching: fixed instructions first, then the source lesson (the same for every
call on a topic), then the verified math, then the request. The LLM is always given sympy's
steps and answers and is told never to compute. Lengths are enforced after parsing, by the
pack schema and the checks.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from app.content.schema import WorkedExample
from pydantic import BaseModel, ConfigDict

OUTPUT_ONLY = "Output content only. Do not address the user."

MATH_RULES = """Math rules:
- A math engine (sympy) has computed and checked every step and answer you are given. Never
  compute anything yourself, never state a result that is not in the given steps, and never
  contradict them.
- Write every math expression in backticks as plain text: `2*x + 6 = 10`, `1/2 + 1/3`, `-3`.
  Use only numbers that appear in the given steps.
- When you say two expressions are equal, use one of these forms inside a grammatical
  sentence: "`A` is `B`", "`A` equals `B`" or "`A` becomes `B`" (for a rewrite). For example:
  "Subtracting a negative is adding, so `5 - (-3)` becomes `5 + 3`." Make sure the engine's
  steps show the equality."""

AUDIENCE = """You write for math teachers of grades 6-9 who are refreshing a topic before they
teach it. They work alone, dislike chatbots and want no judgment. Write plainly, in short full
sentences, warm but not chatty. Never praise, score or address the teacher as "you" more than
needed."""

PACK_SYSTEM = f"""{AUDIENCE}

From the source lesson and the verified worked examples, write:
- summary: one sentence (at most 150 characters) for the topic's card on the home page.
- idea: the core idea in 2-4 short paragraphs (at most 1500 characters).
- why_it_works: why the methods work, in 2-4 short paragraphs (at most 1500 characters).
- questions: 4-6 questions students often ask about the topic, each with a short answer a
  teacher can give (at most 500 characters).
- outline: a lesson outline of 4-6 parts; each has minutes (whole minutes, all parts together
  at most 50), a short title and the activity (at most 500 characters).
Stay faithful to the source lesson: add no new methods or facts it does not support.

{MATH_RULES}
{OUTPUT_ONLY}"""

STEPS_SYSTEM = f"""{AUDIENCE}

You are given one worked example: its lines, in order, as the engine wrote them. A line's margin
operation (op) is what is done to that line to get the next one. For every line, in order,
write:
- why: why this line is done this way, or for the last line, why it is the answer
  (1-2 sentences, at most 400 characters).
- another_way: another way to see or do the same move (1-2 sentences, at most 400 characters).
- visual: one sentence (at most 180 characters) describing the picture of this line on a
  balance scale (equations), a bar model (fractions) or counters on a number line (negative
  numbers). The picture itself is drawn from the line's math; you write only its caption.
Give exactly one entry per line.

{MATH_RULES}
{OUTPUT_ONLY}"""

JUDGE_SYSTEM = f"""You check teaching text against verified math. You are given the facts (the
source lesson, and steps and answers computed by a math engine, always right) and a text with
named fields. List every factual claim in the text, one per entry, with its field name and a
verdict:
- supported: the facts support it, or it is a fair teaching statement consistent with them;
- unsupported: it contradicts the facts, states math the facts don't show, or is wrong;
- unsure: you cannot tell.
Also list every sentence that is ungrammatical or reads awkwardly (such as "that makes `A` is
`B`") as a claim with the verdict unsupported and the reason "wording". Use the text's field
names exactly as given. Give a short reason for anything not supported. Do not judge style
otherwise.
{OUTPUT_ONLY}"""


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionOut(Out):
    question: str
    answer: str


class OutlineOut(Out):
    minutes: int
    title: str
    activity: str


class PackProseOut(Out):
    summary: str
    idea: str
    why_it_works: str
    questions: list[QuestionOut]
    outline: list[OutlineOut]


class StepOut(Out):
    why: str
    another_way: str
    visual: str


class StepsOut(Out):
    steps: list[StepOut]


class ClaimOut(Out):
    field: str
    claim: str
    verdict: Literal["supported", "unsupported", "unsure"]
    reason: str


class JudgeOut(Out):
    claims: list[ClaimOut]


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """The model's JSON schema in the form strict structured output needs: every property
    required and no extra properties, at every level."""
    schema = model.model_json_schema()

    def fix(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
                node["additionalProperties"] = False
            if isinstance(node.get("title"), str):  # an annotation, not a property
                node.pop("title")
            for value in node.values():
                fix(value)
        elif isinstance(node, list):
            for value in node:
                fix(value)

    fix(schema)
    return schema


def example_facts(example: WorkedExample) -> str:
    lines = []
    for i, step in enumerate(example.steps):
        line = f"{step.left} = {step.right}" if step.right else step.left
        op = f"   | {step.op}" if step.op else ""
        lines.append(f"  line {i}: {line}{op}")
    return (
        f"Problem ({example.problem.kind}): {example.problem.expr}\n"
        + "\n".join(lines)
        + f"\n  answer: {example.answer}"
    )


def _source(lesson: str) -> str:
    return f"<source_lesson>\n{lesson.strip()}\n</source_lesson>"


def pack_messages(lesson: str, examples: list[WorkedExample]) -> list[dict[str, Any]]:
    facts = "\n\n".join(example_facts(e) for e in examples)
    return [
        {"role": "system", "content": PACK_SYSTEM},
        {"role": "user", "content": _source(lesson)},
        {
            "role": "user",
            "content": f"<verified_examples>\n{facts}\n</verified_examples>\nWrite the pack text.",
        },
    ]


def steps_messages(lesson: str, example: WorkedExample) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": STEPS_SYSTEM},
        {"role": "user", "content": _source(lesson)},
        {
            "role": "user",
            "content": f"<verified_example>\n{example_facts(example)}\n</verified_example>\n"
            f"Write the explanations for all {len(example.steps)} lines.",
        },
    ]


def judge_messages(lesson: str, facts: str, text: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": _source(lesson)},
        {
            "role": "user",
            "content": f"<verified_math>\n{facts}\n</verified_math>\n"
            f"<text>\n{json.dumps(text, indent=1, ensure_ascii=False)}\n</text>",
        },
    ]


def retry_message(findings: list[str]) -> dict[str, Any]:
    listed = "\n".join(f"- {f}" for f in findings)
    return {
        "role": "user",
        "content": "The math engine and the checker found these problems in your answer:\n"
        f"{listed}\nWrite the whole answer again with these fixed. Change nothing else.",
    }
