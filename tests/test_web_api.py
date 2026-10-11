from __future__ import annotations

import threading
import time
from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient

from quiz_data.sample import QuestionSample
from quiz_host.errors import QuizHostError
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
    """Deals after `instant_deals` block on `deal_gate`; grade is immediate."""

    def __init__(self, *, instant_deals: int = 1) -> None:
        super().__init__()
        self.instant_deals = instant_deals
        self.deal_gate = threading.Event()

    def deal(self, sample: QuestionSample, formats: Sequence[str]) -> BuiltQuestion:
        next_n = self.deals + 1
        if next_n > self.instant_deals:
            assert self.deal_gate.wait(timeout=5), "deal gate was not released"
        return super().deal(sample, formats)


class PrefetchFailHost(FakeHost):
    """First deal succeeds; further deals raise until `fail_prefetch` is cleared."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_prefetch = True

    def deal(self, sample: QuestionSample, formats: Sequence[str]) -> BuiltQuestion:
        next_n = self.deals + 1
        if next_n > 1 and self.fail_prefetch:
            self.deals = next_n
            raise QuizHostError("prefetch failed")
        return super().deal(sample, formats)


def _wait_until(predicate, *, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


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


def test_prefetch_fills_two_ahead(client):
    http, slug = client
    host = app_module.get_host()
    assert isinstance(host, FakeHost)

    start = http.post(
        "/api/play",
        json={
            "topic": slug,
            "questions": 5,
            "difficulty": "easy",
            "formats": ["mcq"],
        },
    )
    assert start.status_code == 200
    body = start.json()
    sid = body["id"]
    assert body["question"] is not None
    assert "prefetch" not in body

    session = app_module.sessions.get(sid)
    assert session is not None
    assert _wait_until(lambda: len(session.prefetch) == 2)
    assert host.deals >= 3
    # Upcoming prompts must not leak into the public view.
    view = http.get(f"/api/play/{sid}").json()
    assert view["question"]["prompt"] == body["question"]["prompt"]
    assert "prefetch" not in view


def test_warm_buffer_serves_next_question_immediately(client):
    http, slug = client
    start = http.post(
        "/api/play",
        json={
            "topic": slug,
            "questions": 5,
            "difficulty": "easy",
            "formats": ["mcq"],
        },
    )
    sid = start.json()["id"]
    q = start.json()["question"]
    session = app_module.sessions.get(sid)
    assert session is not None
    assert _wait_until(lambda: len(session.prefetch) >= 1)

    buffered_prompt = session.prefetch[0].prompt
    ans = http.post(
        f"/api/play/{sid}/answer",
        json={"answer": q["options"][0]},
    )
    assert ans.status_code == 200
    body = ans.json()
    assert body["last_result"] is not None
    assert body["dealing"] is False
    assert body["question"] is not None
    assert body["question"]["prompt"] == buffered_prompt


def test_answer_returns_before_slow_deal_when_buffer_cold(
    ready_topic: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(app_module, "sessions", SessionStore())
    host = PrefetchFailHost()
    app_module.set_host(host)
    http = TestClient(app)
    try:
        start = http.post(
            "/api/play",
            json={
                "topic": ready_topic,
                "questions": 3,
                "difficulty": "easy",
                "formats": ["mcq"],
            },
        )
        assert start.status_code == 200
        sid = start.json()["id"]
        q = start.json()["question"]
        assert q is not None
        # Prefetch fails in the background; the current turn stays healthy.
        time.sleep(0.2)
        session = app_module.sessions.get(sid)
        assert session is not None
        assert session.prefetch == []
        cold = http.get(f"/api/play/{sid}").json()
        assert cold["question"] is not None
        assert cold["dealing"] is False
        assert cold["deal_error"] is None

        host.fail_prefetch = False
        slow = SlowDealHost(instant_deals=0)
        slow.deal_gate.clear()
        # Keep deal count continuity irrelevant; swap host for on-demand path.
        app_module.set_host(slow)

        ans = http.post(
            f"/api/play/{sid}/answer",
            json={"answer": q["options"][0]},
        )
        assert ans.status_code == 200
        body = ans.json()
        assert body["last_result"] is not None
        assert body["question"] is None
        assert body["dealing"] is True

        slow.deal_gate.set()
        assert _wait_until(
            lambda: http.get(f"/api/play/{sid}").json()["question"] is not None
        )
        body = http.get(f"/api/play/{sid}").json()
        assert body["question"] is not None
        assert body["dealing"] is False
    finally:
        app_module.set_host(None)


def test_difficulty_change_discards_stale_prefetch(client):
    http, slug = client
    start = http.post(
        "/api/play",
        json={
            "topic": slug,
            "questions": 4,
            "difficulty": "easy",
            "formats": ["mcq"],
        },
    )
    sid = start.json()["id"]
    session = app_module.sessions.get(sid)
    assert session is not None
    assert _wait_until(lambda: len(session.prefetch) == 2)
    assert all(q.difficulty == "easy" for q in session.prefetch)

    diff = http.post(
        f"/api/play/{sid}/difficulty",
        json={"difficulty": "hard"},
    )
    assert diff.status_code == 200
    assert diff.json()["difficulty"] == "hard"
    assert _wait_until(
        lambda: (
            len(session.prefetch) == 2
            and all(q.difficulty == "hard" for q in session.prefetch)
        )
    )


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
