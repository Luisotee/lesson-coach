from typing import Any

from app.api.limits import RateLimiter, client_ip
from tests.api.conftest import MakeClient


def test_rate_limit_answers_429_with_retry_after(make_client: MakeClient) -> None:
    client, _ = make_client(rate_check_working_per_min=2)
    body = {"lines": [{"text": "1 + 1 = 2"}]}
    assert [client.post("/api/check-working", json=body).status_code for _ in range(2)] == [
        200,
        200,
    ]
    refused = client.post("/api/check-working", json=body)
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) >= 1


def test_window_slides() -> None:
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert limiter.check("b", "ip", 1) is None
    assert limiter.check("b", "ip", 1) == 60.0
    assert limiter.check("b", "other", 1) is None
    now[0] = 60.0
    assert limiter.check("b", "ip", 1) is None


def _request(headers: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "http",
        "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        "client": ("10.0.0.1", 1234),
    }


def test_client_ip_trusts_only_the_ingress_hop() -> None:
    request = _request({"x-forwarded-for": "6.6.6.6, 1.2.3.4"})
    assert client_ip(request, trust_proxy=True) == "1.2.3.4"
    assert client_ip(request, trust_proxy=False) == "10.0.0.1"


def test_body_size_limit(make_client: MakeClient) -> None:
    client, _ = make_client()
    big = {"lines": [{"text": "1"}], "padding": "x" * 70_000}
    assert client.post("/api/check-working", json=big).status_code == 413
