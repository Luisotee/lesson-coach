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
from app.llm.client import Task


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
    assert sent["reasoning_effort"] == "none" and sent["max_completion_tokens"] == 4000
    assert '"cached_tokens": 1024' in caplog.text and '"x": 5' not in caplog.text


def test_gives_up_at_the_deadline() -> None:
    client = FakeClient(*[tls_eof() for _ in range(50)])
    result = call(client, mistake_deadline_s=0.0)
    assert (result.value, result.error, result.attempts) == (None, "unavailable", 1)
    assert len(client.calls) == 1


def test_does_not_retry_a_bad_request() -> None:
    client = FakeClient(bad_request(), response('{"x": 1}'))
    result = call(client)
    assert result.error == "unavailable" and len(client.calls) == 1 and result.attempts == 1


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


@pytest.mark.parametrize(
    ("task", "deployment"),
    [("mistake", "live-x"), ("transcribe", "live-x"), ("generate", "off-x"), ("judge", "off-x")],
)
def test_each_task_uses_its_deployment(task: Task, deployment: str) -> None:
    settings = Settings(_env_file=None, model_live="live-x", model_offline="off-x")  # type: ignore[call-arg]
    model, *_ = AzureLLM(settings, client=object())._task_settings(task)  # type: ignore[arg-type]
    assert model == deployment


def test_each_task_gets_its_own_settings() -> None:
    settings = Settings(_env_file=None, judge_max_completion_tokens=123, mistake_deadline_s=7)  # type: ignore[call-arg]
    llm = AzureLLM(settings, client=object())  # type: ignore[arg-type]
    assert llm._task_settings("judge")[2] == 123
    assert llm._task_settings("judge")[3] == settings.offline_deadline_s
    assert llm._task_settings("mistake")[3] == 7
    # The rule-match moves call: the mistake model, effort and tokens, its own short deadline.
    assert llm._task_settings("mistake_moves")[:3] == llm._task_settings("mistake")[:3]
    assert llm._task_settings("mistake_moves")[3] == settings.mistake_moves_deadline_s == 6.0
    with pytest.raises(ValueError, match="unknown LLM task"):
        llm._task_settings("chat")  # type: ignore[arg-type]
