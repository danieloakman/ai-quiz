from __future__ import annotations

import json
import random

import httpx
import pytest

from quiz_data.sample import QuestionSample, sample_for_question
from quiz_host.authoring import deal_with_client, grade_with_client
from quiz_host.errors import QuizHostError
from quiz_host.factory import host_from_env
from quiz_host.llm_host import LlmHost
from quiz_host.openai_compat import OpenAICompatClient
from quiz_host.parse import choose_format, extract_json_object, question_from_payload
from quiz_host.prompts import deal_messages
from quiz_host.protocols import BuiltQuestion, GradeResult


def _sample(ready_topic: str) -> QuestionSample:
    return sample_for_question(ready_topic, "easy", peers=3)


class ScriptedClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(
        self, messages: list[dict[str, str]], *, json_mode: bool = False
    ) -> str:
        del messages, json_mode
        if self.calls >= len(self.responses):
            raise QuizHostError("No scripted responses left.")
        text = self.responses[self.calls]
        self.calls += 1
        return text


def test_extract_json_from_fence():
    data = extract_json_object('Here:\n```json\n{"a": 1}\n```\n')
    assert data == {"a": 1}


def test_choose_format_uniform_among_allowed():
    rng = random.Random(0)
    formats = ["mcq", "yes-no", "freeform"]
    picks = [choose_format(formats, rng=rng) for _ in range(60)]
    assert set(picks) == set(formats)
    assert all(p in formats for p in picks)


def test_deal_messages_require_single_format(ready_topic: str):
    sample = _sample(ready_topic)
    messages = deal_messages(sample, "freeform")
    user = json.loads(messages[1]["content"])
    assert user["required_format"] == "freeform"
    assert "allowed_formats" not in user


def test_deal_picks_format_before_model(ready_topic: str, monkeypatch: pytest.MonkeyPatch):
    sample = _sample(ready_topic)
    monkeypatch.setattr(
        "quiz_host.authoring.choose_format", lambda formats: "yes-no"
    )
    payload = {
        "format": "yes-no",
        "prompt": "True or false?",
        "options": ["True", "False"],
        "correct": "True",
        "explanation": sample.target_fact,
    }

    class CaptureClient:
        def __init__(self) -> None:
            self.messages: list | None = None

        def complete(self, messages, *, json_mode: bool = False):
            del json_mode
            self.messages = messages
            return json.dumps(payload)

    client = CaptureClient()
    q = deal_with_client(client, sample, ["mcq", "yes-no", "freeform"])
    assert q.format == "yes-no"
    user = json.loads(client.messages[1]["content"])
    assert user["required_format"] == "yes-no"


def test_openai_compat_client_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["model"] == "test-model"
        assert body["messages"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    client = OpenAICompatClient(
        base_url="http://test.local/v1",
        api_key="k",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    text = client.complete([{"role": "user", "content": "hi"}], json_mode=True)
    assert text == '{"ok": true}'


def test_llm_host_deal_mcq_and_exact_grade(ready_topic: str):
    sample = _sample(ready_topic)
    correct = "Anchor term"
    options = [correct, "Peer A", "Peer B", "Peer C"]
    payload = {
        "format": "mcq",
        "prompt": f"Which term fits?\n\n{sample.target_fact}",
        "options": options,
        "correct": correct,
        "explanation": sample.target_fact,
    }

    host = LlmHost(ScriptedClient([json.dumps(payload)]))
    q = host.deal(sample, ["mcq"])
    assert q.format == "mcq"
    assert correct in q.options
    assert len(q.options) >= 4
    ok = host.grade(q, correct)
    assert ok.correct is True
    bad = host.grade(q, "Peer A")
    assert bad.correct is False


def test_mcq_allows_authored_distractors(ready_topic: str):
    sample = _sample(ready_topic)
    payload = {
        "format": "mcq",
        "prompt": "Which?",
        "options": ["Anchor term", "Invented A", "Invented B", "Invented C"],
        "correct": "Anchor term",
        "explanation": sample.target_fact,
    }
    q = question_from_payload(payload, sample, ["mcq"])
    assert q.options == payload["options"]


def test_mcq_rejects_too_few_options(ready_topic: str):
    sample = _sample(ready_topic)
    bad = {
        "format": "mcq",
        "prompt": "Which?",
        "options": ["Anchor term", "Only one distractor"],
        "correct": "Anchor term",
        "explanation": sample.target_fact,
    }
    with pytest.raises(QuizHostError, match="at least four"):
        question_from_payload(bad, sample, ["mcq"])


def test_deal_retries_then_errors(ready_topic: str):
    sample = _sample(ready_topic)
    client = ScriptedClient(["not json", "still bad", "{}"])
    with pytest.raises(QuizHostError, match="Could not author"):
        deal_with_client(client, sample, ["freeform"])


def test_freeform_grade_via_client(ready_topic: str):
    sample = _sample(ready_topic)
    q = BuiltQuestion(
        format="freeform",
        prompt="What about red widgets?",
        options=[],
        correct="They weigh two kilograms",
        explanation="short",
        topic=sample.topic,
        difficulty=sample.difficulty,
        subtopic=sample.subtopic,
        target_fact=sample.target_fact,
    )
    client = ScriptedClient(
        [json.dumps({"correct": True, "explanation": "Close enough."})]
    )
    result = grade_with_client(client, q, "about 2kg")
    assert result == GradeResult(correct=True, explanation="Close enough.")


def test_host_from_env_llm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUIZ_HOST", "llm")
    monkeypatch.setenv("QUIZ_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("QUIZ_LLM_MODEL", "m")
    monkeypatch.delenv("QUIZ_LLM_API_KEY", raising=False)
    host = host_from_env()
    assert isinstance(host, LlmHost)


def test_host_from_env_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("QUIZ_HOST", raising=False)
    monkeypatch.delenv("QUIZ_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("QUIZ_LLM_MODEL", raising=False)
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    with pytest.raises(QuizHostError, match="No quiz host configured"):
        host_from_env()


def test_cursor_host_deal_monkeypatch(
    ready_topic: str, monkeypatch: pytest.MonkeyPatch
):
    from quiz_host.cursor_host import CursorHost

    sample = _sample(ready_topic)
    payload = {
        "format": "yes-no",
        "prompt": f"True or false?\n\n{sample.target_fact}",
        "options": ["True", "False"],
        "correct": "True",
        "explanation": sample.target_fact,
    }

    class FakeResult:
        status = "finished"
        result = json.dumps(payload)

    def fake_prompt(prompt, options):
        del prompt, options
        return FakeResult()

    import sys
    import types

    fake_mod = types.ModuleType("cursor_sdk")

    class Agent:
        @staticmethod
        def prompt(prompt, options):
            return fake_prompt(prompt, options)

    class AgentOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class LocalAgentOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_mod.Agent = Agent
    fake_mod.AgentOptions = AgentOptions
    fake_mod.LocalAgentOptions = LocalAgentOptions
    monkeypatch.setitem(sys.modules, "cursor_sdk", fake_mod)

    host = CursorHost(api_key="test-key", model="composer-2.5")
    q = host.deal(sample, ["yes-no"])
    assert q.format == "yes-no"
    assert q.correct == "True"
