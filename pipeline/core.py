"""The two things the pipeline takes from math-core's T6: worked steps and the LLM interface.

Everything else in the pipeline imports from here, so the seam to `app.math.worked` and
`app.llm` is one file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Protocol

from app.math import Problem, Step
from pydantic import BaseModel

StepsFor = Callable[[Problem], list[Step]]
Task = Literal["generate", "judge"]
Message = dict[str, Any]


class Usage(Protocol):
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    reasoning_tokens: int


class Result[T: BaseModel](Protocol):
    @property
    def value(self) -> T | None: ...
    @property
    def error(self) -> str | None: ...
    @property
    def usage(self) -> Usage: ...


class LLM(Protocol):
    """math-core's `app.llm.client.LLM`, with the offline tasks `generate` and `judge`."""

    async def structured[T: BaseModel](
        self,
        *,
        task: Any,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> Any: ...


def worked_steps(problem: Problem) -> list[Step]:
    """sympy's verified steps for a problem (math-core's `worked_solution`)."""
    from app.math.worked import worked_solution  # type: ignore[import-not-found]  # T6

    steps: list[Step] = worked_solution(problem)
    return steps


def offline_llm() -> tuple[LLM, str]:
    """math-core's client on the offline deployment (`MODEL_OFFLINE`), and its name."""
    from app.config import get_settings  # type: ignore[import-not-found]  # T6
    from app.llm.azure import AzureLLM  # type: ignore[import-not-found]  # T6

    settings = get_settings()
    if not settings.llm_configured:
        raise SystemExit("Azure OpenAI is not configured: copy .env into the repo root")
    return AzureLLM(settings), settings.model_offline
