"""`POST /api/mistake`: why a student probably wrote this answer.

The order is fixed (PLAN, mistake pipeline): sympy solves the problem, classifies the answer,
finds the first line of working that doesn't follow and tries the misconception rules, all in
one worker process under a time limit. A right answer needs no AI. A rule that reproduces a
wrong answer gives the pack's card, and one LLM call rewrites the card's moves (what to say)
for this problem; the card's own moves are about its example problem, so they are shown only
as such when the call fails. A wrong answer that no rule explains gets one LLM call to
diagnose it. Every call is given sympy's verified answer, and its numbers are checked.
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
from app.content.schema import CheckQuestion, Misconception, Pack, PracticeItem
from app.content.schema import Problem as PackProblem
from app.content.store import PackStore
from app.llm.client import LLM
from app.llm.guard import new_numbers
from app.llm.prompts import (
    RULE_SAY_SCHEMA,
    MistakeOut,
    RuleSayOut,
    mistake_messages,
    mistake_schema,
    rule_say_messages,
)
from app.math.nodes import MathError
from app.math.pipeline import MathText, MistakeFindings, analyse_mistake, read_problem
from app.math.problems import Kind
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
    llm: LLM = request.app.state.llm
    if pack is not None and cards:
        diagnosis = await _rule_diagnosis(llm, pack, cards, found, body.lang)
        return result.model_copy(update={"status": "diagnosed", "diagnosis": diagnosis})
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


def _normalised(text: str, kind: Kind) -> str | None:
    try:
        return read_problem(MathText(text, "text"), kind).expr
    except MathError:
        return None


def _same_problem(problem: PackProblem, found: MistakeFindings) -> bool:
    """Whether a pack problem is the one the teacher typed, once both are normalised.
    `evaluate` and `simplify` count as one: a problem typed without a kind is read as
    `evaluate`, and both are graded the same way."""
    if (problem.kind == "solve") != (found.kind == "solve") or found.expr is None:
        return False
    return _normalised(problem.expr, problem.kind) == found.expr


def _same_answer(answer: str, found: MistakeFindings) -> bool:
    if found.student_answer is None:
        return False
    return _normalised(answer, "evaluate") == _normalised(found.student_answer, "evaluate")


async def _rule_diagnosis(
    llm: LLM, pack: Pack, cards: list[Misconception], found: MistakeFindings, lang: str
) -> Diagnosis:
    first = cards[0]
    # The card's own example with its wrong answer: its moves fit as they are.
    same = _same_problem(first.example_problem, found) and _same_answer(
        first.example_wrong_answer, found
    )
    phrased = None if same else await _rule_say(llm, first, found, lang)
    if phrased is not None:
        say, say_lang, say_example = phrased, lang, None
    else:
        say, say_lang = WhatToSayOut(**first.what_to_say.model_dump()), pack.lang
        say_example = None if same else first.example_problem
    return Diagnosis(
        source="rule",
        rule_checked=True,
        misconceptions=[_card_out(c) for c in cards],
        explanation="",  # the card's belief and why it feels right are in `misconceptions`
        margin_note=None,
        what_to_say=say,
        say_example=say_example,
        try_next=_try_next(pack, first, found),
        lang=say_lang,
        cards_lang=pack.lang,
        machine_translated=pack.machine_translated,
    )


async def _rule_say(
    llm: LLM, card: Misconception, found: MistakeFindings, lang: str
) -> WhatToSayOut | None:
    """The card's moves rewritten for the teacher's problem, or None when the call is
    unavailable, abstains, leaves a move blank or writes a number sympy didn't give it."""
    messages = rule_say_messages(
        misconception={
            "belief": card.belief,
            "why_it_feels_right": card.why_it_feels_right,
            "example_problem": card.example_problem.expr,
            "example_wrong_answer": card.example_wrong_answer,
            "example_moves": card.what_to_say.model_dump(),
        },
        request=_request(found),
        lang=lang,
    )
    reply = await llm.structured(
        task="mistake_moves",  # a short deadline: a slow model falls back to the card fast
        messages=messages,
        schema_name="rule_what_to_say",
        schema=RULE_SAY_SCHEMA,
        output=RuleSayOut,
    )
    if reply.value is None or reply.value.abstain:
        return None
    say = reply.value.clipped()
    texts = list(say.model_dump().values())
    if not all(t.strip() for t in texts):
        return None
    line_count = max(len(found.working), len(found.worked))
    # Only the teacher's math is allowed: the example's numbers would be about another problem.
    if new_numbers(texts, _given_math(found, None), lang=lang, line_count=line_count):
        return None
    return WhatToSayOut(**say.model_dump())


def _try_next(pack: Pack, card: Misconception, found: MistakeFindings) -> TryNextOut | None:
    """The card's check question, or, when that is the problem the teacher just typed, a
    practice problem of the topic (it practises the same skill; another card's check question
    was built to detect another belief), then another card's; None when every one is it."""
    options: list[CheckQuestion | PracticeItem] = [
        card.check_question,
        *pack.practice,
        *(m.check_question for m in pack.misconceptions if m.id != card.id),
    ]
    for option in options:
        if not _same_problem(option.problem, found):
            return TryNextOut(problem=option.problem, prompt=option.prompt)
    return None


def _follow_ups(pack: Pack | None, found: MistakeFindings) -> dict[str, TryNextOut]:
    """The follow-ups the AI may pick from, without the problem the teacher just typed."""
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
    return {k: v for k, v in options.items() if not _same_problem(v.problem, found)}


def _request(found: MistakeFindings) -> dict[str, Any]:
    """sympy's findings, as both prompts get them."""
    return {
        "problem": {"kind": found.kind, "expr": found.expr},
        "student_answer": found.student_answer,
        "student_working": [vars(w) for w in found.working],
        "verified_answer": found.correct_answer,
        "verdict": found.verdict,
        "worked_solution": [vars(s) for s in found.worked],
        "first_line_that_does_not_follow": (
            vars(found.first_bad_line) if found.first_bad_line else None
        ),
        "rules_that_reproduce_the_answer": found.rule_ids,
    }


async def _ai_result(
    llm: LLM, result: MistakeResult, found: MistakeFindings, pack: Pack | None, lang: str
) -> MistakeResult:
    cards = {m.id: m for m in pack.misconceptions} if pack is not None else {}
    follow_ups = _follow_ups(pack, found)
    request = _request(found)
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
    examples = [f"{m.example_problem.expr} {m.example_wrong_answer}" for m in cards.values()]
    given = [*_given_math(found, try_next), *examples]
    line_count = max(len(found.working), len(found.worked))
    if new_numbers(texts, given, lang=lang, line_count=line_count):
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
