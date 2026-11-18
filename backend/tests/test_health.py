from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


@pytest.fixture
def dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<title>index</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("secret")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)
    return dist


def test_health_returns_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST", "PUT", "DELETE"])
@pytest.mark.parametrize("path", ["/api", "/api/", "/api/nope", "/api/mistake"])
def test_unknown_api_paths_are_404_for_any_method(dist: Path, method: str, path: str) -> None:
    response = client.request(method, path)
    assert response.status_code == 404
    if method != "HEAD":
        assert response.headers["content-type"] == "application/json"


def test_api_paths_in_other_case_are_not_the_spa(dist: Path) -> None:
    assert client.get("/API/health").status_code == 404
    assert client.head("/Api").status_code == 404


def test_spa_serves_files_falls_back_to_index_and_blocks_traversal(dist: Path) -> None:
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/topics/fractions").text == "<title>index</title>"
    assert "secret" not in client.get("/..%2Fsecret.txt").text


@pytest.mark.parametrize("path", ["/", "/assets/app.js", "/topics/fractions"])
def test_spa_answers_head(dist: Path, path: str) -> None:
    assert client.head(path).status_code == 200
