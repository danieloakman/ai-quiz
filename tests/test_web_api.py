from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from quiz_web.app import app
from quiz_web.sessions import SessionStore


@pytest.fixture
def client(ready_topic: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("quiz_web.app.sessions", SessionStore())
    return TestClient(app), ready_topic


def test_list_and_topic_detail(client):
    http, slug = client
    r = http.get("/api/topics")
    assert r.status_code == 200
    topics = r.json()
    assert any(t["topic"] == slug for t in topics)
    detail = http.get(f"/api/topics/{slug}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "Widgets"
    assert body["ready_subtopics"] >= 1
    assert body["total_facts"] >= 8


def test_play_flow_and_mid_run_difficulty(client):
    http, slug = client
    start = http.post(
        "/api/play",
        json={
            "topic": slug,
            "questions": 3,
            "difficulty": "easy",
            "formats": ["mcq", "yes-no"],
        },
    )
    assert start.status_code == 200
    session = start.json()
    assert session["difficulty"] == "easy"
    assert session["question"] is not None
    sid = session["id"]

    diff = http.post(
        f"/api/play/{sid}/difficulty",
        json={"difficulty": "hard"},
    )
    assert diff.status_code == 200
    assert diff.json()["difficulty"] == "hard"

    # Answer current question; next deal should use hard
    q = session["question"]
    ans = http.post(
        f"/api/play/{sid}/answer",
        json={"answer": q["options"][0]},
    )
    assert ans.status_code == 200
    body = ans.json()
    assert body["answered"] == 1
    assert body["difficulty"] == "hard"
    if not body["finished"]:
        assert body["question"]["difficulty"] == "hard"
