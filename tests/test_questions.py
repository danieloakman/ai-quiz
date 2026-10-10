from __future__ import annotations

import random

import pytest

from quiz_data.errors import QuizDataError
from quiz_data.questions import (
    _make_false_statement,
    _terms_in_text,
    build_question,
)
from quiz_data.sample import QuestionSample


def test_terms_in_text_longest_first():
    terms = ["widget", "red widget", "red"]
    found = _terms_in_text("A red widget weighs two kilograms.", terms)
    assert found[0] == "red widget"
    assert "red" in found


def test_build_mcq(ready_topic: str):
    q = build_question(
        ready_topic,
        "hard",
        ["mcq"],
        rng=random.Random(1),
    )
    assert q.format == "mcq"
    assert q.correct in q.options
    assert len(q.options) >= 2
    assert q.prompt


def test_build_yes_no(ready_topic: str):
    q = build_question(
        ready_topic,
        "moderate",
        ["yes-no"],
        rng=random.Random(2),
    )
    assert q.format == "yes-no"
    assert q.options == ["True", "False"]
    assert q.correct in ("True", "False")


def test_invalid_format(ready_topic: str):
    with pytest.raises(QuizDataError):
        build_question(ready_topic, "easy", ["freeform"])


def test_false_statement_substitution(ready_topic: str):
    sample = QuestionSample(
        topic=ready_topic,
        difficulty="hard",
        subtopic="basics",
        target_fact="A red widget weighs two kilograms.",
        peer_glossary=[
            ("Blue widget", "buoyant"),
            ("Green widget", "kinetic"),
        ],
        peer_facts=[],
        hard_mcq_ok=True,
        notes=[],
    )
    false = _make_false_statement(sample, random.Random(0))
    assert false is not None
    assert false != sample.target_fact
    assert "widget" in false.casefold()
