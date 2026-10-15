"""Shared deal/grade loops for completion-backed hosts."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from quiz_data.sample import QuestionSample
from quiz_host.errors import QuizHostError
from quiz_host.parse import (
    choose_format,
    extract_json_object,
    grade_from_payload,
    question_from_payload,
)
from quiz_host.prompts import deal_messages, grade_messages
from quiz_host.protocols import BuiltQuestion, CompletionClient, GradeResult

_BUILD_ATTEMPTS = 3


def deal_with_client(
    client: CompletionClient,
    sample: QuestionSample,
    formats: Sequence[str],
    *,
    json_mode: bool = True,
) -> BuiltQuestion:
    # Pick format in-process so the model cannot bias toward MCQ.
    required = choose_format(formats)
    allowed = [required]
    errors: list[str] = []
    for _ in range(_BUILD_ATTEMPTS):
        try:
            text = client.complete(deal_messages(sample, required), json_mode=json_mode)
            data = extract_json_object(text)
            return question_from_payload(data, sample, allowed)
        except QuizHostError as exc:
            errors.append(exc.message)
    raise QuizHostError(
        "Could not author a valid question after retries. " + "; ".join(errors[-3:])
    )


def grade_with_client(
    client: CompletionClient,
    question: BuiltQuestion,
    answer: str,
    *,
    target_fact: str | None = None,
    json_mode: bool = True,
) -> GradeResult:
    chosen = answer.strip()
    if question.format in ("mcq", "yes-no"):
        ok = chosen == question.correct
        return GradeResult(
            correct=ok,
            explanation=question.explanation
            if ok
            else f"Expected {question.correct}. {question.explanation}",
        )

    fact = target_fact or question.explanation
    text = client.complete(
        grade_messages(
            prompt=question.prompt,
            target_fact=fact,
            reference=question.correct,
            answer=chosen,
        ),
        json_mode=json_mode,
    )
    data = extract_json_object(text)
    return grade_from_payload(data, question.explanation)


def complete_via(
    fn: Callable[[list[dict[str, str]]], str],
) -> CompletionClient:
    """Wrap a bare callable as a CompletionClient."""

    class _Adapter:
        def complete(
            self,
            messages: list[dict[str, str]],
            *,
            json_mode: bool = False,
        ) -> str:
            del json_mode
            return fn(messages)

    return _Adapter()
