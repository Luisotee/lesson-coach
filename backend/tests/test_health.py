from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_path_is_404_not_the_spa() -> None:
    assert client.get("/api/nope").status_code == 404


def test_spa_serves_files_falls_back_to_index_and_blocks_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<title>index</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("secret")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)

    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/topics/fractions").text == "<title>index</title>"
    assert "secret" not in client.get("/..%2Fsecret.txt").text
