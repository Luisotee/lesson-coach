"""Regression tests for the PR #6 review, round 1."""

import tempfile
from collections.abc import Iterator
from typing import Any

import pytest

from app.api.models import CheckWorkingResult
from app.llm.guard import new_numbers
from app.llm.prompts import MAX_EXPLANATION, MistakeOut, TranscribeOut, clip
from app.mathpool import MathFailure, MathPool
from tests.api.conftest import FakeLLM, MakeClient
from tests.api.slow import die, fail
from tests.api.test_mistake import FRACTIONS, ai_reply, post

PNG = b"\x89PNG\r\n\x1a\n"


def chunks(data: bytes, size: int = 64 * 1024) -> Iterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start : start + size]


# 1. Uploads stay in memory.
def test_a_2mb_image_is_not_spooled_to_disk(
    make_client: MakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    rolled: list[bool] = []
    original = tempfile.SpooledTemporaryFile.rollover

    def spy(self: Any) -> None:
        rolled.append(True)
        original(self)

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", spy)
    client, _ = make_client(FakeLLM({"lines": []}))
    image = PNG + b"\0" * (2 * 1024 * 1024)
    response = client.post("/api/transcribe", files={"image": ("w.png", image, "image/png")})
    assert response.status_code == 200 and rolled == []


# 2. Chunked bodies over the limit get 413.
def test_chunked_json_over_the_limit_is_413(make_client: MakeClient) -> None:
    client, _ = make_client()
    body = b'{"lines": [{"text": "1"}], "pad": "' + b"x" * 100_000 + b'"}'
    response = client.post(
        "/api/check-working", content=chunks(body), headers={"content-type": "application/json"}
    )
    assert response.status_code == 413


def test_chunked_upload_over_the_limit_is_413(make_client: MakeClient) -> None:
    client, llm = make_client()
    boundary = "b0undary"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="w.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + PNG
        + b"\0" * (7 * 1024 * 1024)
        + f"\r\n--{boundary}--\r\n".encode()
    )
    response = client.post(
        "/api/transcribe",
        content=chunks(body),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413 and llm.calls == []


def test_chunked_json_under_the_limit_is_replayed(make_client: MakeClient) -> None:
    client, _ = make_client()
    body = b'{"lines": [{"text": "1 + 1 = 2"}]}'
    response = client.post(
        "/api/check-working", content=chunks(body, 5), headers={"content-type": "application/json"}
    )
    assert response.status_code == 200 and response.json()["status"] == "all_follow"


# 4. Over-long AI output is trimmed, not rejected.
def test_long_ai_text_is_clipped_at_a_word(make_client: MakeClient) -> None:
    long = "They added the tops. " * 100
    client, _ = make_client(
        FakeLLM(ai_reply(explanation=long, margin_note="a" * 30 + " " + "b" * 40))
    )
    diagnosis = post(client, **FRACTIONS, answer={"text": "7/9"})["diagnosis"]
    assert len(diagnosis["explanation"]) <= MAX_EXPLANATION
    assert diagnosis["explanation"].endswith("tops.")
    assert diagnosis["margin_note"] == "a" * 30 + "…"
    assert clip("short", 10) == "short"


def test_transcription_is_clipped() -> None:
    reply = TranscribeOut.model_validate(
        {"lines": [{"left": "x" * 300, "right": "1", "op": "", "confidence": 1.5}] * 40}
    ).clipped()
    assert len(reply.lines) == 30 and reply.lines[0].confidence == 1.0
    assert len(reply.lines[0].left) == 200
    assert MistakeOut.model_validate(
        ai_reply(misconception_ids=["a", "b", "c"])
    ).clipped().misconception_ids == ["a", "b", "c"]  # mistake.py dedupes, then caps


# 5. AI abstains carry a reason.
@pytest.mark.parametrize(
    ("reply", "status", "reason"),
    [
        (ai_reply(status="unclear"), "unclear", "ai_unclear"),
        (ai_reply(status="out_of_scope"), "out_of_scope", "ai_out_of_scope"),
        (ai_reply(misconception_ids=["made_up"]), "unclear", "ai_unclear"),
        (ai_reply(status="slip"), "slip", None),
    ],
)
def test_ai_abstain_reasons(
    make_client: MakeClient, reply: dict[str, Any], status: str, reason: str | None
) -> None:
    client, _ = make_client(FakeLLM(reply))
    result = post(client, **FRACTIONS, answer={"text": "7/9"})
    assert (result["status"], result["reason"]) == (status, reason)


# 6. A failing or dying math worker abstains.
def test_inline_failure_raises_so_tests_see_bugs() -> None:
    import asyncio

    with pytest.raises(RecursionError):
        asyncio.run(MathPool(0, 1.0).run(fail))


def test_a_failing_task_in_the_pool_is_a_math_failure() -> None:
    import asyncio

    pool = MathPool(1, 5.0)
    pool.start()
    try:
        with pytest.raises(MathFailure):
            asyncio.run(pool.run(fail))
    finally:
        pool.stop()


def test_a_dead_worker_is_a_math_failure() -> None:
    import asyncio

    pool = MathPool(1, 5.0)
    pool.start()
    try:
        with pytest.raises(MathFailure):
            asyncio.run(pool.run(die))
    finally:
        pool.stop()


def test_math_failure_abstains(make_client: MakeClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = make_client()

    async def broken(*args: Any) -> None:
        raise MathFailure

    monkeypatch.setattr(client.app.state.pool, "run", broken)  # type: ignore[attr-defined]
    assert post(client, **FRACTIONS, answer={"text": "2/5"})["reason"] == "math_error"
    result = client.post("/api/check-working", json={"lines": [{"text": "1"}]}).json()
    assert (result["status"], result["reason"]) == ("unclear", "math_error")


# 7. The AI's text may only quote math it was given.
def test_ai_math_that_sympy_gave_is_shown(make_client: MakeClient) -> None:
    reply = ai_reply(explanation="Use sixths: 3/6 + 2/6 makes 5/6, not 7/9.")
    client, _ = make_client(FakeLLM(reply))
    result = post(client, **FRACTIONS, answer={"text": "7/9"})
    assert result["status"] == "diagnosed" and "5/6" in result["diagnosis"]["explanation"]


@pytest.mark.parametrize("field", ["explanation", "margin_note", "probe", "nudge", "tell"])
def test_ai_math_sympy_didnt_give_is_not_shown(make_client: MakeClient, field: str) -> None:
    reply = ai_reply()
    if field in ("probe", "nudge", "tell"):
        reply["what_to_say"] = {**reply["what_to_say"], field: "The answer is 7/12."}
    else:
        reply[field] = "The answer is 7/12."
    client, _ = make_client(FakeLLM(reply))
    result = post(client, **FRACTIONS, answer={"text": "7/9"})
    assert (result["status"], result["reason"], result["diagnosis"]) == (
        "unclear",
        "ai_unverified_math",
        None,
    )
    assert result["correct_answer"] == "5/6"


def test_guard_values() -> None:
    given = ["1/2 + 1/3", "3/6 + 2/6", "5/6"]
    assert new_numbers(["Halbe ist 0,5; one step"], given) == set()
    assert {str(v) for v in new_numbers(["Then 7/12 is wrong"], given)} == {"7", "12"}
    assert new_numbers(["4/12 is the same as 1/3"], given) == set()  # its value was given


def test_the_prompt_forbids_new_math(make_client: MakeClient) -> None:
    client, llm = make_client(FakeLLM(ai_reply()))
    post(client, **FRACTIONS, answer={"text": "7/9"})
    assert (
        "Never compute, simplify or invent a new number" in llm.calls[0]["messages"][0]["content"]
    )


# 8. The rate limit is checked before the body is read.
def test_rate_limit_comes_before_the_body(make_client: MakeClient) -> None:
    client, _ = make_client(rate_transcribe_per_min=1)
    small = {"image": ("w.png", PNG, "image/png")}
    client.post("/api/transcribe", files=small)
    big = PNG + b"\0" * (7 * 1024 * 1024)
    response = client.post("/api/transcribe", files={"image": ("w.png", big, "image/png")})
    assert response.status_code == 429


# 9. Small items.
def test_a_zero_limit_turns_the_limit_off(make_client: MakeClient) -> None:
    client, _ = make_client(rate_check_working_per_min=0)
    codes = {
        client.post("/api/check-working", json={"lines": [{"text": "1"}]}).status_code
        for _ in range(3)
    }
    assert codes == {200}


def test_check_working_rejects_an_undefined_problem(make_client: MakeClient) -> None:
    client, _ = make_client()
    result = client.post(
        "/api/check-working", json={"problem": {"text": "1/0"}, "lines": [{"text": "1"}]}
    )
    assert (result.json()["status"], result.json()["reason"]) == ("unclear", "problem_unreadable")


def test_dividing_by_zero_in_the_margin_breaks_the_chain(make_client: MakeClient) -> None:
    client, _ = make_client()
    lines = [{"left": "2*x", "right": "4", "op": "/0"}, {"left": "x", "right": "2"}]
    result = client.post("/api/check-working", json={"lines": lines}).json()
    assert result["first_bad_line"] == {"index": 1, "reason": "not_equivalent"}
    lines[0]["op"] = "*0"
    assert (
        client.post("/api/check-working", json={"lines": lines}).json()["status"]
        == "line_doesnt_follow"
    )


# 10. The lines the student sent come back, normalised, in order.
def test_mistake_echoes_the_working(make_client: MakeClient) -> None:
    client, _ = make_client()
    working = [
        {"text": "2x+6=10"},
        {"left": "2x", "right": "16", "op": "/2"},
        {"latex": r"\sqrt{x}"},
        {"text": "8"},
    ]
    result = post(client, problem={"text": "2x + 6 = 10"}, answer={"text": "8"}, working=working)
    assert result["working"] == [
        {"left": "2*x + 6", "right": "10", "op": ""},
        {"left": "2*x", "right": "16", "op": "/2"},
        {"left": r"\sqrt{x}", "right": None, "op": None},
        {"left": "8", "right": "", "op": ""},
    ]
    assert result["first_bad_line"]["index"] == 1
    assert post(client, **FRACTIONS, answer={"text": "5/6"})["working"] == []


def test_check_working_echoes_the_lines(make_client: MakeClient) -> None:
    client, _ = make_client()
    lines = [{"text": "2x = 4"}, {"left": "x", "right": "2?"}]
    result = CheckWorkingResult.model_validate(
        client.post(
            "/api/check-working", json={"problem": {"text": "2x+6=10"}, "lines": lines}
        ).json()
    )
    assert [(w.left, w.right) for w in result.lines] == [("2*x", "4"), ("x = 2?", None)]
    assert result.first_bad_line is not None and result.first_bad_line.index == 1


# Round 2.
LINEAR = ["2*x + 6 = 10", "2*x + 6 10 -6", "2*x 4 /2", "x 2"]


@pytest.mark.parametrize(
    "text", ["They should get 4x = 12x", "So 3x/2 is next", "Now x^3", "x = 7"]
)
def test_guard_catches_digits_next_to_letters(text: str) -> None:
    assert new_numbers([text], LINEAR)


@pytest.mark.parametrize("text", ["2x = 4, so x = 2", "Subtract 6 from 2x + 6", "x^2 has 2 in it"])
def test_guard_passes_given_coefficients(text: str) -> None:
    assert new_numbers([text], LINEAR) == set()


def test_guard_decimal_comma_only_where_it_is_a_decimal() -> None:
    given = ["1/2 + 1/3", "3/6 + 2/6", "5/6"]
    assert new_numbers(["Think of 2,3 and 6 as denominators."], given, lang="en") == set()
    assert new_numbers(["Ein Halb ist 0,5."], given, lang="de") == set()
    assert new_numbers(["Two numbers: 2,3"], given, lang="de")  # 2.3 is new math in German


def test_guard_allows_line_numbers_and_card_examples(make_client: MakeClient) -> None:
    assert new_numbers(["Look at line 3."], ["2*x"], line_count=3) == set()
    assert new_numbers(["Look at line 3."], ["2*x"], line_count=2)
    # Card examples sent in the prompt (1/4 + 1/2 is a check question; 3*2/5 -> 6/15 a card).
    reply = ai_reply(explanation="Like 3 * 2/5 turning into 6/15, they treat parts as wholes.")
    client, _ = make_client(FakeLLM(reply))
    assert post(client, **FRACTIONS, answer={"text": "7/9"})["status"] == "diagnosed"


def test_the_ai_sees_the_students_working(make_client: MakeClient) -> None:
    client, llm = make_client(FakeLLM(ai_reply(misconception_ids=["other"])))
    working = [{"text": "2x+6=10"}, {"text": "2x = 17"}]
    post(client, problem={"text": "2x + 6 = 10"}, answer={"text": "x = 8.5"}, working=working)
    request = llm.calls[0]["messages"][-1]["content"]
    assert (
        '"student_working": [{"left": "2*x + 6", "right": "10", "op": ""}, '
        '{"left": "2*x", "right": "17"' in request
    )


def test_a_cut_transcription_line_is_uncertain(make_client: MakeClient) -> None:
    long = "1+" * 120 + "1"
    reply = {"lines": [{"left": long, "right": "241", "op": "", "confidence": 0.99}]}
    client, _ = make_client(FakeLLM(reply))
    files = {"image": ("w.png", PNG, "image/png")}
    line = client.post("/api/transcribe", files=files).json()["lines"][0]
    assert line["uncertain"] is True and len(line["left"]) == 200


def test_clip_keeps_the_limit_with_the_ellipsis() -> None:
    assert len(clip("x" * 100, 60)) == 60


def test_duplicate_ids_do_not_push_out_a_second_misconception(make_client: MakeClient) -> None:
    ids = ["add_tops_and_bottoms", "add_tops_and_bottoms", "multiply_both_by_whole"]
    client, _ = make_client(FakeLLM(ai_reply(misconception_ids=ids)))
    diagnosis = post(client, **FRACTIONS, answer={"text": "7/9"})["diagnosis"]
    assert [m["id"] for m in diagnosis["misconceptions"]] == ids[1:]
