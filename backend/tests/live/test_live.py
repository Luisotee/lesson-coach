"""One real call per endpoint against Azure. `make test` skips these; run them with
`uv run pytest -m live -s` (needs the repo's .env)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.api.conftest import FIXTURES

pytestmark = pytest.mark.live
IMAGE = Path(__file__).resolve().parents[3] / "infra" / "fixtures" / "equation.png"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    settings = Settings(content_dir=FIXTURES)
    if not settings.llm_configured:
        pytest.skip("no Azure credentials in the environment or .env")
    with TestClient(create_app(settings)) as client:  # runs the real process pool
        yield client


def test_topics(client: TestClient) -> None:
    topics = client.get("/api/topics").json()
    print(topics)
    assert topics and client.get("/api/topics/fractions").status_code == 200


def test_mistake_ai_path(client: TestClient) -> None:
    body = {
        "problem": {"text": "1/2 + 1/3"},
        "answer": {"text": "2/6"},
        "topic": "fractions",
        "lang": "de",
    }
    result = client.post("/api/mistake", json=body).json()
    print(result)
    assert result["correct_answer"] == "5/6"
    assert result["reason"] != "ai_unavailable" and result["diagnosis"]["source"] == "ai"


def test_transcribe(client: TestClient) -> None:
    files = {"image": ("equation.png", IMAGE.read_bytes(), "image/png")}
    result = client.post("/api/transcribe", files=files).json()
    print(result)
    assert result["status"] == "ok" and len(result["lines"]) == 2


def test_check_working(client: TestClient) -> None:
    body = {"problem": {"text": "3x + 5 = 20"}, "lines": [{"text": "3x = 15"}, {"text": "x = 5"}]}
    result = client.post("/api/check-working", json=body).json()
    print(result)
    assert result == {
        "status": "all_follow",
        "reason": None,
        "first_bad_line": None,
        "final": "correct",
    }
