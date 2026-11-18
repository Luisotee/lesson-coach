import json
from pathlib import Path

import pytest

from app.content.store import PackError, PackStore
from tests.api.conftest import FIXTURES, MakeClient


def test_list_topics(make_client: MakeClient) -> None:
    client, _ = make_client()
    topics = client.get("/api/topics").json()
    assert [t["id"] for t in topics] == ["fractions"]
    assert topics[0] | {"title": None} == {
        "id": "fractions",
        "title": None,
        "lang": "en",
        "langs": ["de", "en"],
        "machine_translated": False,
        "prerequisites": ["negative-numbers"],
        "grades": [],
        "summary": None,
    }
    german = client.get("/api/topics?lang=de").json()[0]
    assert (german["lang"], german["title"], german["machine_translated"]) == ("de", "Brüche", True)


def test_get_pack_and_fallback(make_client: MakeClient) -> None:
    client, _ = make_client()
    pack = client.get("/api/topics/fractions").json()
    assert pack["topic"] == "fractions" and len(pack["misconceptions"]) == 5
    assert client.get("/api/topics/fractions?lang=fr").json()["lang"] == "en"
    assert client.get("/api/topics/fractions?lang=de").json()["lang"] == "de"


def test_missing_and_unknown_topics(make_client: MakeClient) -> None:
    client, _ = make_client()
    assert client.get("/api/topics/linear-equations").status_code == 404
    assert client.get("/api/topics/algebra").status_code == 422
    assert client.get("/api/topics?lang=../x").status_code == 422


def test_no_content_dir_means_no_topics(make_client: MakeClient, tmp_path: Path) -> None:
    client, _ = make_client(content_dir=tmp_path / "missing")
    assert client.get("/api/topics").json() == []


def test_a_bad_pack_stops_startup(tmp_path: Path) -> None:
    (tmp_path / "en").mkdir()
    (tmp_path / "en" / "fractions.json").write_text('{"topic": "fractions"}')
    with pytest.raises(PackError):
        PackStore.load(tmp_path)


def test_a_pack_in_the_wrong_place_stops_startup(tmp_path: Path) -> None:
    (tmp_path / "fr").mkdir()
    data = json.loads((FIXTURES / "en" / "fractions.json").read_text())
    (tmp_path / "fr" / "fractions.json").write_text(json.dumps(data))
    with pytest.raises(PackError):
        PackStore.load(tmp_path)
