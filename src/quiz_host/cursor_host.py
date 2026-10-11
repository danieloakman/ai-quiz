"""QuizHost backed by the Cursor Agent SDK."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from quiz_data.sample import QuestionSample
from quiz_host.authoring import complete_via, deal_with_client, grade_with_client
from quiz_host.errors import QuizHostError
from quiz_host.protocols import BuiltQuestion, GradeResult


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


class CursorHost:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "composer-2.5",
        cwd: str | Path | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.cwd = str(cwd or _repo_root())

    def _complete(self, messages: list[dict[str, str]]) -> str:
        try:
            from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
        except ImportError as exc:
            raise QuizHostError(
                "cursor-sdk is not installed. "
                'Install with: uv pip install -e ".[cursor]"'
            ) from exc

        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            parts.append(f"[{role}]\n{msg.get('content', '')}")
        prompt = (
            "\n\n".join(parts)
            + "\n\nRespond with ONLY the JSON object described above."
        )
        try:
            result = Agent.prompt(
                prompt,
                AgentOptions(
                    api_key=self.api_key,
                    model=self.model,
                    local=LocalAgentOptions(cwd=self.cwd),
                ),
            )
        except Exception as exc:  # noqa: BLE001 — SDK error types vary
            raise QuizHostError(f"Cursor agent failed to start: {exc}") from exc

        status = getattr(result, "status", None)
        text = getattr(result, "result", None)
        if status == "error" or not text:
            raise QuizHostError(f"Cursor agent run failed (status={status!r}).")
        if not isinstance(text, str):
            text = json.dumps(text)
        return text

    def deal(
        self,
        sample: QuestionSample,
        formats: Sequence[str],
    ) -> BuiltQuestion:
        client = complete_via(self._complete)
        return deal_with_client(client, sample, formats, json_mode=False)

    def grade(self, question: BuiltQuestion, answer: str) -> GradeResult:
        client = complete_via(self._complete)
        return grade_with_client(
            client,
            question,
            answer,
            target_fact=question.target_fact or question.explanation,
            json_mode=False,
        )
