from __future__ import annotations

import threading
import time
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


class SlowDealHost(FakeHost):
    """Deal blocks until released; grade is immediate."""

    def __init__(self) -> None:
        super().__init__()
        self.deal_gate = threading.Event()

    def deal(self, sample: QuestionSample, formats: Sequence[str]) -> BuiltQuestion:
        assert self.deal_gate.wait(timeout=5), "deal gate was not released"
        return super().deal(sample, formats)


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
    assert session["time_limit_seconds"] == 10
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
    assert body["last_result"] is not None

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        body = http.get(f"/api/play/{sid}").json()
        if body["question"] is not None:
            break
        time.sleep(0.05)
    assert body["question"] is not None
    assert body["dealing"] is False
    assert body["question"]["difficulty"] == "hard"


def test_answer_returns_before_slow_deal(
    ready_topic: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(app_module, "sessions", SessionStore())
    host = SlowDealHost()
    host.deal_gate.set()  # allow the initial start-play deal
    app_module.set_host(host)
    http = TestClient(app)
    try:
        start = http.post(
            "/api/play",
            json={
                "topic": ready_topic,
                "questions": 2,
                "difficulty": "easy",
                "formats": ["mcq"],
            },
        )
        assert start.status_code == 200
        sid = start.json()["id"]
        q = start.json()["question"]
        assert q is not None

        host.deal_gate.clear()  # block prefetch while answering
        ans = http.post(
            f"/api/play/{sid}/answer",
            json={"answer": q["options"][0]},
        )
        assert ans.status_code == 200
        body = ans.json()
        assert body["last_result"] is not None
        assert body["question"] is None
        assert body["dealing"] is True

        host.deal_gate.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            body = http.get(f"/api/play/{sid}").json()
            if body["question"] is not None:
                break
            time.sleep(0.05)
        assert body["question"] is not None
        assert body["dealing"] is False
    finally:
        app_module.set_host(None)


def test_start_with_time_limit_and_timeout_advances(client):
    http, slug = client
    start = http.post(
        "/api/play",
        json={
            "topic": slug,
            "questions": 2,
            "difficulty": "easy",
            "formats": ["mcq"],
            "time_limit_seconds": 30,
        },
    )
    assert start.status_code == 200
    session = start.json()
    assert session["time_limit_seconds"] == 30
    assert session["question"] is not None
    sid = session["id"]

    ans = http.post(
        f"/api/play/{sid}/answer",
        json={"timed_out": True},
    )
    assert ans.status_code == 200
    body = ans.json()
    assert body["answered"] == 1
    assert body["score"] == 0
    assert body["last_result"] is not None
    assert body["last_result"]["correct"] is False
    assert body["last_result"]["timed_out"] is True
    assert body["last_result"]["chosen"] == "(no answer)"
    assert "time ran out" in body["last_result"]["explanation"].lower()

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        body = http.get(f"/api/play/{sid}").json()
        if body["question"] is not None or body["finished"]:
            break
        time.sleep(0.05)
    assert body["question"] is not None or body["finished"]


def test_timeout_rejected_without_time_limit(client):
    http, slug = client
    start = http.post(
        "/api/play",
        json={
            "topic": slug,
            "questions": 1,
            "difficulty": "easy",
            "formats": ["mcq"],
            "time_limit_seconds": None,
        },
    )
    assert start.status_code == 200
    sid = start.json()["id"]

    ans = http.post(
        f"/api/play/{sid}/answer",
        json={"timed_out": True},
    )
    assert ans.status_code == 400
    assert "no time limit" in ans.json()["detail"].lower()


def test_invalid_time_limit_rejected(client):
    http, slug = client
    for bad in [0, -1, 601, "nope"]:
        r = http.post(
            "/api/play",
            json={
                "topic": slug,
                "questions": 1,
                "difficulty": "easy",
                "formats": ["mcq"],
                "time_limit_seconds": bad,
            },
        )
        assert r.status_code == 400, bad


def test_form_cleared_time_limit_is_untimed(client):
    http, slug = client
    start = http.post(
        "/play",
        data={
            "topic": slug,
            "questions": "1",
            "difficulty": "easy",
            "formats": "mcq",
            "time_limit_seconds": "",
        },
        follow_redirects=False,
    )
    assert start.status_code == 303
    sid = start.headers["location"].rsplit("/", 1)[-1]
    body = http.get(f"/api/play/{sid}").json()
    assert body["time_limit_seconds"] is None
