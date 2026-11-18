import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import httpx2 as httpx
import openai
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.llm import azure
from app.llm.azure import AzureLLM


class Out(BaseModel):
    x: int


def response(content: str | None, finish: str = "stop", refusal: str | None = None) -> Any:
    usage = SimpleNamespace(
        prompt_tokens=1200,
        completion_tokens=50,
        prompt_tokens_details=SimpleNamespace(cached_tokens=1024),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=30),
    )
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish)], usage=usage
    )


class FakeClient:
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def tls_eof() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))


def bad_request() -> openai.BadRequestError:
    request = httpx.Request("POST", "https://example.invalid")
    return openai.BadRequestError("bad", response=httpx.Response(400, request=request), body=None)


def call(client: FakeClient, **settings: Any) -> Any:
    llm = AzureLLM(Settings(_env_file=None, **settings), client=client)  # type: ignore[call-arg, arg-type]
    return asyncio.run(
        llm.structured(task="mistake", messages=[], schema_name="s", schema={}, output=Out)
    )


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr(azure, "sleep", instant)


def test_retries_transient_errors_then_succeeds(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient(tls_eof(), tls_eof(), response('{"x": 5}'))
    with caplog.at_level(logging.INFO, logger="app.llm"):
        result = call(client)
    assert result.value == Out(x=5) and result.attempts == 3
    assert (result.usage.cached_tokens, result.usage.reasoning_tokens) == (1024, 30)
    sent = client.calls[0]
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert sent["reasoning_effort"] == "low" and sent["max_completion_tokens"] == 4000
    assert '"cached_tokens": 1024' in caplog.text and '"x": 5' not in caplog.text


def test_gives_up_at_the_deadline() -> None:
    client = FakeClient(*[tls_eof() for _ in range(50)])
    result = call(client, mistake_deadline_s=0.0)
    assert (result.value, result.error) == (None, "unavailable")
    assert len(client.calls) == 1


def test_does_not_retry_a_bad_request() -> None:
    client = FakeClient(bad_request(), response('{"x": 1}'))
    result = call(client)
    assert result.error == "unavailable" and len(client.calls) == 1


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (response('{"x": "five"}'), "invalid_output"),
        (response('{"x": 1', finish="length"), "invalid_output"),
        (response(None, refusal="no"), "refused"),
    ],
)
def test_bad_replies_abstain(reply: Any, error: str) -> None:
    assert call(FakeClient(reply)).error == error
