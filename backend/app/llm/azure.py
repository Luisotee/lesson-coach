"""Azure OpenAI Chat Completions with structured output, retries and a total deadline.

Transient failures (connection resets such as the TLS EOFs infra saw, timeouts, 429, 5xx) are
retried with exponential backoff and jitter until the task's deadline. Each call logs one
line of numbers (tokens, latency, attempts, outcome) and never any prompt or reply text.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any

import openai
from openai import AsyncAzureOpenAI
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.llm.client import LLMError, LLMResult, Message, Task, Usage

log = logging.getLogger("app.llm")

TRANSIENT = (
    openai.APIConnectionError,  # includes APITimeoutError
    openai.RateLimitError,
    openai.InternalServerError,
)
BACKOFF_BASE_S = 0.5
BACKOFF_MAX_S = 8.0
sleep = asyncio.sleep  # tests replace it


class AzureLLM:
    def __init__(self, settings: Settings, client: AsyncAzureOpenAI | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key.get_secret_value(),
            api_version=settings.azure_openai_api_version,
            max_retries=0,  # we retry ourselves, under one deadline
        )

    def _task_settings(self, task: Task) -> tuple[str, str, int, float, float]:
        """Deployment, reasoning effort, token limit, deadline and per-attempt timeout."""
        s = self.settings
        live, offline = s.model_live, s.model_offline
        attempt, offline_attempt = s.llm_attempt_timeout_s, s.offline_attempt_timeout_s
        match task:
            case "mistake":
                return (
                    live,
                    s.mistake_reasoning_effort,
                    s.mistake_max_completion_tokens,
                    s.mistake_deadline_s,
                    attempt,
                )
            case "transcribe":
                return (
                    live,
                    s.transcribe_reasoning_effort,
                    s.transcribe_max_completion_tokens,
                    s.transcribe_deadline_s,
                    attempt,
                )
            case "generate":
                return (
                    offline,
                    s.generate_reasoning_effort,
                    s.generate_max_completion_tokens,
                    s.offline_deadline_s,
                    offline_attempt,
                )
            case "judge":
                return (
                    offline,
                    s.judge_reasoning_effort,
                    s.judge_max_completion_tokens,
                    s.offline_deadline_s,
                    offline_attempt,
                )

    async def structured[T: BaseModel](
        self,
        *,
        task: Task,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> LLMResult[T]:
        model, effort, max_tokens, deadline_s, attempt_s = self._task_settings(task)
        start = time.monotonic()
        deadline = start + deadline_s
        attempts = 0
        result: LLMResult[T] = LLMResult(None, "unavailable")
        while True:
            attempts += 1
            remaining = deadline - time.monotonic()
            try:
                params: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": schema_name, "strict": True, "schema": schema},
                    },
                    "max_completion_tokens": max_tokens,
                    "reasoning_effort": effort,
                    "timeout": max(1.0, min(attempt_s, remaining)),
                }
                response = await self.client.chat.completions.create(**params)
            except TRANSIENT as err:
                delay = min(BACKOFF_MAX_S, BACKOFF_BASE_S * 2 ** (attempts - 1))
                delay *= 0.5 + random.random()  # jitter
                if time.monotonic() + delay >= deadline:
                    error: LLMError = "deadline" if attempts > 1 else "unavailable"
                    result = LLMResult(None, error)
                    self._log(task, model, start, attempts, result, type(err).__name__)
                    return result
                await sleep(delay)
                continue
            except openai.OpenAIError as err:  # 400, 401, 404...: retrying won't help
                result = LLMResult(None, "unavailable")
                self._log(task, model, start, attempts, result, type(err).__name__)
                return result
            result = _read(response, output)
            result.attempts = attempts
            self._log(task, model, start, attempts, result, None)
            return result

    def _log(
        self,
        task: Task,
        model: str,
        start: float,
        attempts: int,
        result: LLMResult[Any],
        cause: str | None,
    ) -> None:
        log.info(
            json.dumps(
                {
                    "event": "llm_call",
                    "task": task,
                    "model": model,
                    "latency_ms": round((time.monotonic() - start) * 1000),
                    "attempts": attempts,
                    "outcome": result.error or "ok",
                    "cause": cause,
                    "prompt_tokens": result.usage.prompt_tokens,
                    "cached_tokens": result.usage.cached_tokens,
                    "completion_tokens": result.usage.completion_tokens,
                    "reasoning_tokens": result.usage.reasoning_tokens,
                }
            )
        )


def _usage(response: Any) -> Usage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return Usage()
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    return Usage(
        prompt_tokens=usage.prompt_tokens or 0,
        cached_tokens=getattr(prompt_details, "cached_tokens", 0) or 0,
        completion_tokens=usage.completion_tokens or 0,
        reasoning_tokens=getattr(completion_details, "reasoning_tokens", 0) or 0,
    )


def _read[T: BaseModel](response: Any, output: type[T]) -> LLMResult[T]:
    usage = _usage(response)
    choice = response.choices[0] if response.choices else None
    if choice is None or getattr(choice.message, "refusal", None):
        return LLMResult(None, "refused", usage)
    content = choice.message.content
    if choice.finish_reason != "stop" or not content:
        return LLMResult(None, "invalid_output", usage)
    try:
        return LLMResult(output.model_validate_json(content), None, usage)
    except ValidationError:
        return LLMResult(None, "invalid_output", usage)
