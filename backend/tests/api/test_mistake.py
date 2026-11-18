import json
from pathlib import Path
from typing import Any

import pytest

from app.mathpool import MathTimeout
from tests.api.conftest import FakeLLM, MakeClient

FRACTIONS = {"problem": {"text": "1/2 + 1/3"}, "topic": "fractions"}


def ai_reply(**overrides: Any) -> dict[str, Any]:
    reply: dict[str, Any] = {
        "status": "diagnosed",
        "misconception_ids": ["add_tops_and_bottoms"],
        "explanation": "They added the tops and the bottoms.",
        "margin_note": "added the bottoms too",
        "what_to_say": {
            "probe": "Bigger or smaller than 1/2?",
            "nudge": "Draw bars.",
            "tell": "Use sixths.",
        },
        "follow_up_id": "check:add_tops_and_bottoms",
    }
    reply.update(overrides)
    return reply


def post(client: Any, **body: Any) -> dict[str, Any]:
    response = client.post("/api/mistake", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_correct_answer_needs_no_ai(make_client: MakeClient) -> None:
    client, llm = make_client()
    result = post(client, **FRACTIONS, answer={"text": "5/6"})
    assert (result["status"], result["verdict"], result["correct_answer"]) == (
        "correct",
        "correct",
        "5/6",
    )
    assert result["diagnosis"] is None and llm.calls == []


def test_not_simplified(make_client: MakeClient) -> None:
    client, llm = make_client()
    result = post(client, **FRACTIONS, answer={"latex": r"\frac{10}{12}"})
    assert result["status"] == "not_simplified" and llm.calls == []


def test_rule_match_uses_the_pack_card_without_ai(make_client: MakeClient) -> None:
    client, llm = make_client()
    result = post(client, **FRACTIONS, answer={"text": "2/5"})
    assert result["status"] == "diagnosed" and llm.calls == []
    diagnosis = result["diagnosis"]
    assert diagnosis["source"] == "rule" and diagnosis["rule_checked"] is True
    assert [m["id"] for m in diagnosis["misconceptions"]] == ["add_tops_and_bottoms"]
    assert diagnosis["explanation"] == ""  # the card's text is in `misconceptions`
    assert diagnosis["try_next"]["problem"] == {"kind": "evaluate", "expr": "1/4 + 1/2"}
    assert diagnosis["margin_note"] is None
    assert (diagnosis["lang"], diagnosis["cards_lang"]) == ("en", "en")
    assert [s["left"] for s in result["worked_solution"]] == ["1/2 + 1/3", "3/6 + 2/6", "5/6"]


def test_rule_match_without_topic_infers_it(make_client: MakeClient) -> None:
    client, _ = make_client()
    result = post(client, problem={"text": "1/2 + 1/3"}, answer={"text": "2/5"})
    assert result["diagnosis"]["source"] == "rule"


def test_card_language_and_fallback(make_client: MakeClient) -> None:
    client, _ = make_client()
    german = post(client, **FRACTIONS, answer={"text": "2/5"}, lang="de")["diagnosis"]
    assert (german["lang"], german["cards_lang"], german["machine_translated"]) == (
        "de",
        "de",
        True,
    )
    french = post(client, **FRACTIONS, answer={"text": "2/5"}, lang="fr")["diagnosis"]
    assert french["cards_lang"] == "en"


def test_unexplained_wrong_answer_makes_one_ai_call(make_client: MakeClient) -> None:
    client, llm = make_client(FakeLLM(ai_reply()))
    result = post(client, **FRACTIONS, answer={"text": "7/9"}, lang="fr")
    assert len(llm.calls) == 1
    assert result["status"] == "diagnosed"
    diagnosis = result["diagnosis"]
    assert diagnosis["source"] == "ai" and diagnosis["rule_checked"] is False
    assert diagnosis["misconceptions"][0]["belief"].startswith("To add fractions")
    assert diagnosis["margin_note"] == "added the bottoms too"
    assert diagnosis["try_next"]["prompt"] == "Work out:"
    assert (diagnosis["lang"], diagnosis["cards_lang"]) == ("fr", "en")
    # The AI is told sympy's verified answer, and the request comes last.
    messages = llm.calls[0]["messages"]
    assert '"verified_answer": "5/6"' in messages[-1]["content"]
    assert "<language>fr</language>" in messages[-1]["content"]
    assert "Output content only. Do not address the user." in messages[0]["content"]
    ids = llm.calls[0]["schema"]["properties"]["misconception_ids"]["items"]["enum"]
    assert "add_tops_and_bottoms" in ids and "other" in ids


def test_ai_ids_outside_the_pack_are_dropped(make_client: MakeClient) -> None:
    reply = ai_reply(misconception_ids=["made_up", "other"], follow_up_id="practice:nope")
    client, _ = make_client(FakeLLM(reply))
    diagnosis = post(client, **FRACTIONS, answer={"text": "7/9"})["diagnosis"]
    assert diagnosis["misconceptions"] == [
        {"id": "other", "belief": None, "why_it_feels_right": None}
    ]
    assert diagnosis["try_next"] is None


def test_diagnosis_without_a_misconception_is_unclear(make_client: MakeClient) -> None:
    client, _ = make_client(FakeLLM(ai_reply(misconception_ids=["made_up"])))
    result = post(client, **FRACTIONS, answer={"text": "7/9"})
    assert result["status"] == "unclear" and result["diagnosis"]["misconceptions"] == []


@pytest.mark.parametrize("status", ["slip", "unclear", "out_of_scope"])
def test_ai_abstains(make_client: MakeClient, status: str) -> None:
    client, _ = make_client(FakeLLM(ai_reply(status=status)))
    result = post(client, **FRACTIONS, answer={"text": "7/9"})
    assert result["status"] == status and result["diagnosis"]["misconceptions"] == []


def test_ai_unavailable_keeps_the_math(make_client: MakeClient) -> None:
    client, _ = make_client(FakeLLM(error="deadline"))
    result = post(client, **FRACTIONS, answer={"text": "7/9"})
    assert (result["status"], result["reason"]) == ("unclear", "ai_unavailable")
    assert result["correct_answer"] == "5/6" and result["worked_solution"]


def test_topic_without_a_pack_goes_to_the_ai_with_the_rule_ids(make_client: MakeClient) -> None:
    client, llm = make_client(FakeLLM(ai_reply(misconception_ids=["other"])))
    result = post(client, problem={"text": "2x + 6 = 10"}, answer={"text": "x = 8"})
    assert result["status"] == "diagnosed"
    assert (
        '"rules_that_reproduce_the_answer": ["sign_not_changed"]'
        in llm.calls[0]["messages"][-1]["content"]
    )
    assert llm.calls[0]["schema"]["properties"]["follow_up_id"] == {"type": "null"}


def test_working_finds_the_first_bad_line(make_client: MakeClient) -> None:
    client, _ = make_client()
    working = [{"text": "2x + 6 = 10"}, {"left": "2x", "right": "16"}, {"latex": "x=8"}]
    result = post(client, problem={"text": "2x + 6 = 10"}, answer={"text": "8"}, working=working)
    assert result["first_bad_line"] == {"index": 1, "reason": "not_equivalent"}


@pytest.mark.parametrize(
    ("body", "status", "reason"),
    [
        ({"problem": {"text": "2 +"}, "answer": {"text": "1"}}, "unclear", "problem_unreadable"),
        (
            {"problem": {"text": "1/2 + 1/3"}, "answer": {"text": "half"}},
            "unclear",
            "answer_unreadable",
        ),
        ({"problem": {"text": "x^2 = 4"}, "answer": {"text": "2"}}, "out_of_scope", "unsupported"),
        (
            {"problem": {"text": "2x = 6"}, "answer": {"text": "6/x = 2"}},
            "out_of_scope",
            "unsupported",
        ),
    ],
)
def test_math_abstains(
    make_client: MakeClient, body: dict[str, Any], status: str, reason: str
) -> None:
    client, llm = make_client()
    result = post(client, **body)
    assert (result["status"], result["reason"]) == (status, reason) and llm.calls == []


def test_answer_unreadable_still_gives_the_worked_answer(make_client: MakeClient) -> None:
    client, _ = make_client()
    result = post(client, problem={"text": "1/2 + 1/3"}, answer={"text": "half"})
    assert result["correct_answer"] == "5/6"


def test_timeout_abstains(make_client: MakeClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = make_client()

    async def too_slow(*args: Any) -> None:
        raise MathTimeout

    monkeypatch.setattr(client.app.state.pool, "run", too_slow)  # type: ignore[attr-defined]
    result = post(client, **FRACTIONS, answer={"text": "2/5"})
    assert (result["status"], result["reason"]) == ("out_of_scope", "timeout")


@pytest.mark.parametrize(
    "body",
    [
        {"problem": {"text": "1", "latex": "1"}, "answer": {"text": "1"}},
        {"problem": {}, "answer": {"text": "1"}},
        {"problem": {"text": "1" * 201}, "answer": {"text": "1"}},
        {"problem": {"text": "1"}, "answer": {"text": "1"}, "lang": "english!"},
        {"problem": {"text": "1"}, "answer": {"text": "1"}, "topic": "algebra"},
        {"problem": {"text": "1"}, "answer": {"text": "1"}, "working": [{"left": "1"}] * 21},
        {"problem": {"text": "1"}, "answer": {"text": "1"}, "extra": 1},
    ],
)
def test_bad_requests_are_422(make_client: MakeClient, body: dict[str, Any]) -> None:
    client, _ = make_client()
    assert client.post("/api/mistake", json=body).status_code == 422


# The bug from the live app: `sign_not_changed` matched, and the card's moves, written for its
# example `2*x + 6 = 10`, were shown as if about this problem.
LINEAR = {
    "problem": {"text": "3x+5=20"},
    "answer": {"text": "25/3"},
    "working": [{"text": "3x=25"}],
    "topic": "linear-equations",
}
CARD_MOVES = {
    "probe": "What did you do to both sides to get rid of the `+ 6`?",
    "nudge": 'Write the operation in the margin, "| -6", and apply it to both sides.',
    "tell": "Subtract six from both sides: `2*x = 4`, so `x = 2`. Substituting checks it: "
    "`2*2 + 6` is `10`.",
}


def say_reply(**overrides: Any) -> dict[str, Any]:
    reply: dict[str, Any] = {
        "abstain": False,
        "probe": "What did you do to both sides to get rid of the + 5?",
        "nudge": "Look at what happened to the 5 in your first line.",
        "tell": "Subtract 5 from both sides: 3*x = 15, so x = 5.",
    }
    reply.update(overrides)
    return reply


def linear_client(make_client: MakeClient, llm: FakeLLM) -> Any:
    client, _ = make_client(llm, content_dir=Path(__file__).parents[3] / "content" / "generated")
    return client


def test_rule_moves_are_written_for_this_problem(make_client: MakeClient) -> None:
    llm = FakeLLM(say_reply())
    result = post(linear_client(make_client, llm), **LINEAR)
    diagnosis = result["diagnosis"]
    assert (result["status"], diagnosis["source"]) == ("diagnosed", "rule")
    assert [m["id"] for m in diagnosis["misconceptions"]] == ["sign_not_changed"]
    say = " ".join(diagnosis["what_to_say"].values())
    assert "5" in say and "6" not in say
    assert diagnosis["say_example"] is None and diagnosis["lang"] == "en"
    # One phrasing call, given sympy's findings and the card's moves as the example.
    assert len(llm.calls) == 1 and llm.calls[0]["task"] == "mistake_moves"
    prompt = json.dumps(llm.calls[0]["messages"])
    assert "3*x + 5 = 20" in prompt and "Subtract six" in prompt


@pytest.mark.parametrize(
    "llm",
    [
        FakeLLM(error="deadline"),
        FakeLLM(say_reply(abstain=True, probe="", nudge="", tell="")),
        FakeLLM(say_reply(tell="Subtract 6 from both sides.")),  # the example's number
        FakeLLM(say_reply(tell="So x = 7.")),  # a number sympy never gave
        FakeLLM(say_reply(nudge=" ")),
    ],
    ids=["unavailable", "abstains", "example_number", "new_number", "empty"],
)
def test_rule_moves_fall_back_to_the_card_framed_by_its_example(
    make_client: MakeClient, llm: FakeLLM
) -> None:
    diagnosis = post(linear_client(make_client, llm), **LINEAR)["diagnosis"]
    assert diagnosis["source"] == "rule"
    assert diagnosis["what_to_say"] == CARD_MOVES
    assert diagnosis["say_example"] == {"kind": "solve", "expr": "2*x + 6 = 10"}
    assert diagnosis["lang"] == "en"


def test_rule_moves_for_the_cards_own_example_need_no_ai(make_client: MakeClient) -> None:
    llm = FakeLLM(say_reply())
    body = {**LINEAR, "problem": {"text": "2x+6=10"}, "answer": {"text": "8"}, "working": []}
    diagnosis = post(linear_client(make_client, llm), **body)["diagnosis"]
    assert diagnosis["what_to_say"] == CARD_MOVES and diagnosis["say_example"] is None
    assert llm.calls == []


def test_try_next_is_never_the_problem_just_typed(make_client: MakeClient) -> None:
    diagnosis = post(linear_client(make_client, FakeLLM(say_reply())), **LINEAR)["diagnosis"]
    # The card's check question is 3*x + 5 = 20 itself, so a practice problem of the topic is
    # offered before another card's check question (built to detect another belief).
    assert diagnosis["try_next"]["problem"] == {"kind": "solve", "expr": "8*x = 56"}
    assert diagnosis["explanation"] == ""  # the card is shown from `misconceptions`


def test_a_simplify_problem_typed_without_a_kind_is_recognised(make_client: MakeClient) -> None:
    # The page sends no kind, so `(6+9)/3` is read as `evaluate`; the pack calls it `simplify`.
    client = linear_client(make_client, FakeLLM(say_reply()))
    body = {"problem": {"text": "(6+9)/3"}, "answer": {"text": "9"}, "topic": "fractions"}
    diagnosis = post(client, **body)["diagnosis"]
    assert [m["id"] for m in diagnosis["misconceptions"]] == ["cancel_across_addition"]
    assert diagnosis["try_next"]["problem"]["expr"] != "(6+9)/3"


def test_the_cards_own_example_typed_without_a_kind_needs_no_ai(make_client: MakeClient) -> None:
    llm = FakeLLM(error="unavailable")
    body = {"problem": {"text": "(2+4)/2"}, "answer": {"text": "4"}, "topic": "fractions"}
    diagnosis = post(linear_client(make_client, llm), **body)["diagnosis"]
    assert diagnosis["source"] == "rule" and diagnosis["say_example"] is None
    assert llm.calls == []


def test_the_cards_example_with_another_wrong_answer_is_rewritten(make_client: MakeClient) -> None:
    # The rule also gives 5 on (2+4)/2, but the card's moves quote its own wrong answer, 4.
    llm = FakeLLM(error="unavailable")
    body = {"problem": {"text": "(2+4)/2"}, "answer": {"text": "5"}, "topic": "fractions"}
    diagnosis = post(linear_client(make_client, llm), **body)["diagnosis"]
    assert [m["id"] for m in diagnosis["misconceptions"]] == ["cancel_across_addition"]
    assert len(llm.calls) == 1
    assert diagnosis["say_example"] == {"kind": "simplify", "expr": "(2+4)/2"}


def test_ai_follow_ups_leave_out_the_problem_just_typed(make_client: MakeClient) -> None:
    llm = FakeLLM(error="unavailable")
    body = {**LINEAR, "answer": {"text": "7"}, "working": []}  # no rule gives 7
    result = post(linear_client(make_client, llm), **body)
    assert result["reason"] == "ai_unavailable"
    ids = llm.calls[0]["schema"]["properties"]["follow_up_id"]["anyOf"][0]["enum"]
    assert "check:sign_not_changed" not in ids and "check:divide_one_term" in ids
