from typing import Any

from tests.api.conftest import FakeLLM, MakeClient

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 64


def send(client: Any, data: bytes, mime: str = "image/png") -> Any:
    return client.post("/api/transcribe", files={"image": ("work.png", data, mime)})


def reply(*lines: tuple[str, str, str, float]) -> dict[str, Any]:
    return {"lines": [{"left": a, "right": b, "op": c, "confidence": d} for a, b, c, d in lines]}


def test_lines_with_uncertainty(make_client: MakeClient) -> None:
    llm = FakeLLM(
        reply(
            ("2*x + 6", "10", "-6", 0.95),
            ("2*x", "4", "", 0.5),
            ("x", "2?", "", 0.9),
            ("", "", "", 0.9),
        )
    )
    client, _ = make_client(llm)
    result = send(client, PNG).json()
    assert result["status"] == "ok"
    assert [(line["left"], line["uncertain"]) for line in result["lines"]] == [
        ("2*x + 6", False),
        ("2*x", True),
        ("x", True),
    ]
    image = llm.calls[0]["messages"][-1]["content"][0]["image_url"]["url"]
    assert image.startswith("data:image/png;base64,")


def test_no_math_and_no_ai(make_client: MakeClient) -> None:
    client, _ = make_client(FakeLLM(reply()))
    assert send(client, JPEG, "image/jpeg").json() == {
        "status": "unclear",
        "reason": "no_math",
        "lines": [],
    }
    client, _ = make_client(FakeLLM(error="unavailable"))
    assert send(client, PNG).json()["reason"] == "ai_unavailable"


def test_type_must_match_the_bytes(make_client: MakeClient) -> None:
    client, llm = make_client()
    assert send(client, JPEG, "image/png").status_code == 415
    assert send(client, b"GIF89a" + b"\0" * 10, "image/gif").status_code == 415
    assert send(client, b"%PDF-1.7", "image/png").status_code == 415
    assert llm.calls == []


def test_size_limit(make_client: MakeClient) -> None:
    client, llm = make_client()
    big = PNG + b"\0" * (5 * 1024 * 1024)
    assert send(client, big).status_code == 413
    assert llm.calls == []
