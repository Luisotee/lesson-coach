"""`POST /api/mistake`: why a student probably wrote this answer.

The order is fixed (PLAN, mistake pipeline): sympy solves the problem, classifies the answer,
finds the first line of working that doesn't follow and tries the misconception rules, all in
one worker process under a time limit. A right answer needs no AI. A rule that reproduces a
wrong answer gives the pack's card, with no AI. Only a wrong answer that no rule explains gets
one LLM call, and it is always given sympy's verified answer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.convert import bad_line, line_text, math_text, steps_out, working_out
from app.api.models import (
    Diagnosis,
    MisconceptionOut,
    MistakeRequest,
    MistakeResult,
    ProblemOut,
    TryNextOut,
    WhatToSayOut,
)
from app.content.schema import Misconception, Pack
from app.content.store import PackStore
from app.llm.client import LLM
from app.llm.guard import new_numbers
from app.llm.prompts import MistakeOut, mistake_messages, mistake_schema
from app.math.pipeline import MistakeFindings, analyse_mistake
from app.mathpool import MathFailure, MathPool, MathTimeout

router = APIRouter(prefix="/api", tags=["mistake"])

MAX_MISCONCEPTIONS = 2
CHECK_PREFIX = "check:"
PRACTICE_PREFIX = "practice:"


@router.post(
    "/mistake",
    response_model=MistakeResult,
)
async def post_mistake(body: MistakeRequest, request: Request) -> MistakeResult:
    pool: MathPool = request.app.state.pool
    try:
        found: MistakeFindings = await pool.run(
            analyse_mistake,
            math_text(body.problem),
            body.problem.kind,
            math_text(body.answer),
            [line_text(line) for line in body.working],
            body.topic,
        )
    except MathTimeout:
        return MistakeResult(status="out_of_scope", reason="timeout")
    except MathFailure:
        return MistakeResult(status="unclear", reason="math_error")
    result = _math_result(found)
    if found.error == "unsupported":
        return result.model_copy(update={"status": "out_of_scope", "reason": "unsupported"})
    if found.error is not None:
        return result.model_copy(update={"status": "unclear", "reason": found.error})
    if found.verdict == "correct":
        return result.model_copy(update={"status": "correct"})
    if found.verdict == "equivalent_not_simplified":
        return result.model_copy(update={"status": "not_simplified"})

    store: PackStore = request.app.state.store
    pack = store.get(found.topic, body.lang) if found.topic else None
    cards = _rule_cards(pack, found.rule_ids)
    if pack is not None and cards:
        return result.model_copy(
            update={"status": "diagnosed", "diagnosis": _rule_diagnosis(pack, cards)}
        )
    llm: LLM = request.app.state.llm
    return await _ai_result(llm, result, found, pack, body.lang)


def _math_result(found: MistakeFindings) -> MistakeResult:
    problem = (
        ProblemOut(kind=found.kind, expr=found.expr)
        if found.kind is not None and found.expr is not None
        else None
    )
    return MistakeResult(
        status="unclear",
        problem=problem,
        student_answer=found.student_answer,
        correct_answer=found.correct_answer,
        verdict=found.verdict,
        worked_solution=steps_out(found.worked),
        working=working_out(found.working),
        first_bad_line=bad_line(found.first_bad_line),
    )


def _rule_cards(pack: Pack | None, rule_ids: list[str]) -> list[Misconception]:
    if pack is None:
        return []
    by_id = {m.id: m for m in pack.misconceptions}
    return [by_id[r] for r in rule_ids if r in by_id][:MAX_MISCONCEPTIONS]


def _card_out(card: Misconception) -> MisconceptionOut:
    return MisconceptionOut(
        id=card.id, belief=card.belief, why_it_feels_right=card.why_it_feels_right
    )


def _rule_diagnosis(pack: Pack, cards: list[Misconception]) -> Diagnosis:
    first = cards[0]
    return Diagnosis(
        source="rule",
        rule_checked=True,
        misconceptions=[_card_out(c) for c in cards],
        explanation=f"{first.belief} {first.why_it_feels_right}",
        margin_note=None,
        what_to_say=WhatToSayOut(**first.what_to_say.model_dump()),
        try_next=TryNextOut(
            problem=first.check_question.problem, prompt=first.check_question.prompt
        ),
        lang=pack.lang,
        cards_lang=pack.lang,
        machine_translated=pack.machine_translated,
    )


def _follow_ups(pack: Pack | None) -> dict[str, TryNextOut]:
    if pack is None:
        return {}
    options = {
        f"{CHECK_PREFIX}{m.id}": TryNextOut(
            problem=m.check_question.problem, prompt=m.check_question.prompt
        )
        for m in pack.misconceptions
    }
    options.update(
        {
            f"{PRACTICE_PREFIX}{p.id}": TryNextOut(problem=p.problem, prompt=p.prompt)
            for p in pack.practice
        }
    )
    return options


async def _ai_result(
    llm: LLM, result: MistakeResult, found: MistakeFindings, pack: Pack | None, lang: str
) -> MistakeResult:
    cards = {m.id: m for m in pack.misconceptions} if pack is not None else {}
    follow_ups = _follow_ups(pack)
    request: dict[str, Any] = {
        "problem": {"kind": found.kind, "expr": found.expr},
        "student_answer": found.student_answer,
        "verified_answer": found.correct_answer,
        "verdict": found.verdict,
        "worked_solution": [vars(s) for s in found.worked],
        "first_line_that_does_not_follow": (
            vars(found.first_bad_line) if found.first_bad_line else None
        ),
        "rules_that_reproduce_the_answer": found.rule_ids,
    }
    messages = mistake_messages(
        topic=found.topic,
        misconceptions=[
            {
                "id": m.id,
                "belief": m.belief,
                "example": f"{m.example_problem.expr} -> {m.example_wrong_answer}",
            }
            for m in cards.values()
        ],
        follow_ups=[
            {"id": key, "problem": option.problem.expr, "prompt": option.prompt}
            for key, option in follow_ups.items()
        ],
        request=request,
        lang=lang,
    )
    reply = await llm.structured(
        task="mistake",
        messages=messages,
        schema_name="mistake_diagnosis",
        schema=mistake_schema(list(cards), list(follow_ups)),
        output=MistakeOut,
    )
    if reply.value is None:
        return result.model_copy(update={"status": "unclear", "reason": "ai_unavailable"})
    out = reply.value.clipped()
    try_next = follow_ups.get(out.follow_up_id) if out.follow_up_id else None
    texts = [out.explanation, out.margin_note or "", *out.what_to_say.model_dump().values()]
    if new_numbers(texts, _given_math(found, try_next)):
        # The AI wrote math sympy didn't give it: show nothing rather than unverified math.
        return result.model_copy(update={"status": "unclear", "reason": "ai_unverified_math"})
    ids = [i for i in dict.fromkeys(out.misconception_ids) if i in cards or i == "other"]
    misconceptions = [
        _card_out(cards[i]) if i in cards else MisconceptionOut(id="other")
        for i in ids[:MAX_MISCONCEPTIONS]
    ]
    status = out.status
    if status == "diagnosed" and not misconceptions:
        status = "unclear"  # a diagnosis must name a misconception
    if status != "diagnosed":
        misconceptions = []
    reason = {"unclear": "ai_unclear", "out_of_scope": "ai_out_of_scope"}.get(status)
    diagnosis = Diagnosis(
        source="ai",
        rule_checked=False,
        misconceptions=misconceptions,
        explanation=out.explanation,
        margin_note=out.margin_note,
        what_to_say=WhatToSayOut(**out.what_to_say.model_dump()),
        try_next=try_next,
        lang=lang,
        cards_lang=pack.lang if pack is not None else None,
        machine_translated=pack.machine_translated if pack is not None else False,
    )
    return result.model_copy(update={"status": status, "reason": reason, "diagnosis": diagnosis})


def _given_math(found: MistakeFindings, try_next: TryNextOut | None) -> list[str]:
    """Every piece of math the AI was given, which its text may quote."""
    given = [found.expr or "", found.student_answer or "", found.correct_answer or ""]
    given += [f"{s.left} {s.right} {s.op}" for s in found.worked]
    given += [f"{w.left} {w.right or ''} {w.op or ''}" for w in found.working]
    if try_next is not None:
        given.append(try_next.problem.expr)
    return given
