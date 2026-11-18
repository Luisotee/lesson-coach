"""The two things the pipeline takes from math-core's T6: worked steps and the LLM interface.

Everything else in the pipeline imports from here, so the seam to `app.math.worked` and
`app.llm` is one file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from app.llm.client import LLM, LLMResult, Usage
from app.math import Problem, Step

__all__ = ["LLM", "LLMResult", "StepsFor", "Task", "Usage", "offline_llm", "worked_steps"]

StepsFor = Callable[[Problem], list[Step]]
Task = Literal["generate", "judge"]  # the offline tasks of `app.llm.client.Task`


def worked_steps(problem: Problem) -> list[Step]:
    """sympy's verified steps for a problem (math-core's `worked_solution`)."""
    from app.math.worked import worked_solution

    steps: list[Step] = worked_solution(problem)
    return steps


def offline_llm() -> tuple[LLM, str]:
    """math-core's client on the offline deployment (`MODEL_OFFLINE`), and its name."""
    from app.config import get_settings
    from app.llm.azure import AzureLLM

    settings = get_settings()
    if not settings.llm_configured:
        raise SystemExit("Azure OpenAI is not configured: copy .env into the repo root")
    return AzureLLM(settings), settings.model_offline
