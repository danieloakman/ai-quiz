from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient

from quiz_data.sample import QuestionSample
from quiz_host.protocols import BuiltQuestion, GradeResult
from quiz_web import app as app_module
from quiz_web.app import app
from quiz_web.sessions import SessionStore


class FakeHost:
    def __init__(self) -> None:
        self.deals = 0

    def deal(self, sample: QuestionSample, formats: Sequence[str]) -> BuiltQuestion:
        self.deals += 1
        fmt = "mcq" if "mcq" in formats else formats[0]
        if fmt == "freeform":
            return BuiltQuestion(
                format="freeform",
                prompt=f"Explain: {sample.target_fact}",
                options=[],
                correct="reference",
                explanation=sample.target_fact,
                topic=sample.topic,
                difficulty=sample.difficulty,
                subtopic=sample.subtopic,
                target_fact=sample.target_fact,
            )
        if fmt == "yes-no":
            return BuiltQuestion(
                format="yes-no",
                prompt=f"True or false?\n\n{sample.target_fact}",
                options=["True", "False"],
                correct="True",
                explanation=sample.target_fact,
                topic=sample.topic,
                difficulty=sample.difficulty,
                subtopic=sample.subtopic,
                target_fact=sample.target_fact,
            )
        return BuiltQuestion(
            format="mcq",
            prompt=f"Which fits?\n\n{sample.target_fact}",
            options=["A", "B", "C"],
            correct="A",
            explanation=sample.target_fact,
            topic=sample.topic,
            difficulty=sample.difficulty,
            subtopic=sample.subtopic,
            target_fact=sample.target_fact,
        )

    def grade(self, question: BuiltQuestion, answer: str) -> GradeResult:
        ok = answer.strip() == question.correct
        return GradeResult(
            correct=ok,
            explanation=question.explanation,
        )


@pytest.fixture
def client(ready_topic: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_module, "sessions", SessionStore())
    app_module.set_host(FakeHost())
    yield TestClient(app), ready_topic
    app_module.set_host(None)


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
            "formats": ["mcq", "yes-no", "freeform"],
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

    q = session["question"]
    answer = q["options"][0] if q["options"] else "reference"
    ans = http.post(
        f"/api/play/{sid}/answer",
        json={"answer": answer},
    )
    assert ans.status_code == 200
    body = ans.json()
    assert body["answered"] == 1
    assert body["difficulty"] == "hard"
    if not body["finished"]:
        assert body["question"]["difficulty"] == "hard"
