from typing import Any

import pytest

from tests.api.conftest import MakeClient

EQUATION = {"text": "2x + 6 = 10"}


def check(make_client: MakeClient, **body: Any) -> dict[str, Any]:
    client, llm = make_client()
    response = client.post("/api/check-working", json=body)
    assert response.status_code == 200, response.text
    assert llm.calls == []  # sympy only
    result: dict[str, Any] = response.json()
    return result


def test_all_lines_follow_and_final_answer(make_client: MakeClient) -> None:
    lines = [{"left": "2x + 6", "right": "10", "op": "-6"}, {"latex": "2x=4"}, {"text": "x = 2"}]
    result = check(make_client, problem=EQUATION, lines=lines)
    assert (result["status"], result["final"]) == ("all_follow", "correct")
    result = check(make_client, problem=EQUATION, lines=[{"text": "2x = 4"}])
    assert result["final"] == "equivalent_not_simplified"


def test_first_line_that_doesnt_follow(make_client: MakeClient) -> None:
    lines = [{"text": "2x = 16"}, {"text": "x = 8"}]
    result = check(make_client, problem=EQUATION, lines=lines)
    assert result["status"] == "line_doesnt_follow"
    assert result["first_bad_line"] == {"index": 0, "reason": "not_equivalent"}
    assert result["final"] is None


def test_without_a_problem(make_client: MakeClient) -> None:
    lines = [{"text": "1/2 + 1/3 = 2/5"}]
    result = check(make_client, lines=lines)
    assert result["first_bad_line"] == {"index": 0, "reason": "false_equality"}


def test_unreadable_line(make_client: MakeClient) -> None:
    result = check(make_client, problem=EQUATION, lines=[{"latex": r"\sqrt{2}"}])
    assert result["first_bad_line"] == {"index": 0, "reason": "unparsable"}


@pytest.mark.parametrize(
    ("problem", "status", "reason"),
    [
        ({"text": "2 +"}, "unclear", "problem_unreadable"),
        ({"text": "6/x = 2"}, "out_of_scope", "unsupported"),
    ],
)
def test_problem_abstains(
    make_client: MakeClient, problem: dict[str, str], status: str, reason: str
) -> None:
    result = check(make_client, problem=problem, lines=[{"text": "x = 3"}])
    assert (result["status"], result["reason"]) == (status, reason)


def test_needs_lines(make_client: MakeClient) -> None:
    client, _ = make_client()
    assert client.post("/api/check-working", json={"lines": []}).status_code == 422


def test_a_blank_for_the_answer_is_dropped_from_the_problem(make_client: MakeClient) -> None:
    lines = [{"text": "1/2 + 1/2 = 2/4"}]
    asked = check(make_client, problem={"latex": "\\frac{1}{2}+\\frac{1}{2}=?"}, lines=lines)
    assert asked == check(make_client, problem={"text": "1/2 + 1/2"}, lines=lines)
    assert asked["first_bad_line"] == {"index": 0, "reason": "false_equality"}
