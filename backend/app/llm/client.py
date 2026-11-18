"""The one interface every LLM call goes through. Callers get a value or an error, never an
exception, so each caller has an abstain path."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

Task = Literal["mistake", "transcribe", "generate", "judge"]  # the last two run offline
LLMError = Literal["unavailable", "deadline", "invalid_output", "refused"]
Message = dict[str, Any]


@dataclass
class Usage:
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass
class LLMResult[T: BaseModel]:
    value: T | None
    error: LLMError | None = None
    usage: Usage = field(default_factory=Usage)
    attempts: int = 0


class LLM(Protocol):
    async def structured[T: BaseModel](
        self,
        *,
        task: Task,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> LLMResult[T]:
        """One structured-output call. `schema` is a strict JSON schema; the reply is
        validated with `output`."""
        ...


class NullLLM:
    """Used when no credentials are configured: every AI part abstains."""

    async def structured[T: BaseModel](
        self,
        *,
        task: Task,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> LLMResult[T]:
        return LLMResult(None, "unavailable")
