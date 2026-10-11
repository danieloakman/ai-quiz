"""Protocols and shared question types for quiz hosts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from quiz_data.sample import QuestionSample

FORMATS = ("mcq", "yes-no", "freeform")


@dataclass
class BuiltQuestion:
    format: str
    prompt: str
    options: list[str]
    correct: str
    explanation: str
    topic: str
    difficulty: str
    subtopic: str
    target_fact: str = ""


@dataclass
class GradeResult:
    correct: bool
    explanation: str


class CompletionClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str: ...


class QuizHost(Protocol):
    def deal(
        self,
        sample: QuestionSample,
        formats: Sequence[str],
    ) -> BuiltQuestion: ...

    def grade(self, question: BuiltQuestion, answer: str) -> GradeResult: ...
