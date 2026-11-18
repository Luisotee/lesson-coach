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
    assert diagnosis["explanation"].startswith("To add fractions, add the tops")
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
    assert diagnosis["try_next"]["prompt"] == "Add one quarter and one half."
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
