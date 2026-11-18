from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.llm.client import LLMError, LLMResult, Message, Task
from app.main import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "content"


class FakeLLM:
    """Returns `reply` (a dict validated with the caller's output model) or `error`."""

    def __init__(self, reply: dict[str, Any] | None = None, error: LLMError | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def structured[T: BaseModel](
        self,
        *,
        task: Task,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        output: type[T],
    ) -> LLMResult[T]:
        self.calls.append({"task": task, "messages": messages, "schema": schema})
        if self.reply is None:
            return LLMResult(None, self.error or "unavailable")
        return LLMResult(output.model_validate(self.reply))


def settings_for_tests(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "content_dir": FIXTURES,
        "math_workers": 0,
        "azure_openai_endpoint": "",
        "azure_openai_api_key": "",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


MakeClient = Callable[..., tuple[TestClient, FakeLLM]]


@pytest.fixture
def make_client() -> MakeClient:
    def make(llm: FakeLLM | None = None, **overrides: Any) -> tuple[TestClient, FakeLLM]:
        fake = llm or FakeLLM()
        return TestClient(create_app(settings_for_tests(**overrides), llm=fake)), fake

    return make
