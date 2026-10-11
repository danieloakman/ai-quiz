"""QuizHost backed by an OpenAI-compatible completion client."""

from __future__ import annotations

from collections.abc import Sequence

from quiz_data.sample import QuestionSample
from quiz_host.authoring import deal_with_client, grade_with_client
from quiz_host.protocols import BuiltQuestion, CompletionClient, GradeResult


class LlmHost:
    def __init__(self, client: CompletionClient) -> None:
        self._client = client

    def deal(
        self,
        sample: QuestionSample,
        formats: Sequence[str],
    ) -> BuiltQuestion:
        return deal_with_client(self._client, sample, formats)

    def grade(self, question: BuiltQuestion, answer: str) -> GradeResult:
        return grade_with_client(
            self._client,
            question,
            answer,
            target_fact=question.target_fact or question.explanation,
        )
