"""Deterministic question builder from sampled facts + glossary."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from quiz_data.errors import QuizDataError
from quiz_data.sample import QuestionSample, sample_for_question
from quiz_data.store import load_glossary

FORMATS = ("mcq", "yes-no")
_BUILD_ATTEMPTS = 24


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


def build_question(
    topic: str,
    difficulty: str,
    formats: list[str] | tuple[str, ...],
    *,
    peers: int = 3,
    rng: random.Random | None = None,
) -> BuiltQuestion:
    """Sample knowledge and build one graded MCQ or yes-no question."""
    allowed = _normalize_formats(formats)
    rng = rng or random.Random()

    for _ in range(_BUILD_ATTEMPTS):
        sample = sample_for_question(
            topic, difficulty, peers=peers, rng=rng
        )
        order = list(allowed)
        rng.shuffle(order)
        # Prefer yes-no when MCQ peers are weak
        if sample.notes and any(
            n.startswith("no_glossary_peers") or n.startswith("hard_mcq_weak")
            for n in sample.notes
        ):
            order = [f for f in order if f != "mcq"] + [
                f for f in order if f == "mcq"
            ]

        for fmt in order:
            if fmt == "mcq":
                built = _try_mcq(sample, rng)
            else:
                built = _try_yes_no(sample, rng)
            if built is not None:
                return built

    raise QuizDataError(
        f"Could not build a deterministic question for topic {topic!r} "
        f"with formats {', '.join(allowed)}. "
        f"Add more glossary terms (for MCQ) or facts, then retry."
    )


def _normalize_formats(formats: list[str] | tuple[str, ...]) -> list[str]:
    if not formats:
        raise QuizDataError(
            "At least one format is required. Choose from: mcq, yes-no."
        )
    out: list[str] = []
    seen: set[str] = set()
    for raw in formats:
        fmt = raw.strip().lower()
        if fmt not in FORMATS:
            raise QuizDataError(
                f"Invalid format {raw!r}. Choose from: {', '.join(FORMATS)}."
            )
        if fmt not in seen:
            seen.add(fmt)
            out.append(fmt)
    return out


def _try_mcq(sample: QuestionSample, rng: random.Random) -> BuiltQuestion | None:
    peer_terms = [t for t, _ in sample.peer_glossary]
    if not peer_terms:
        return None

    same = load_glossary(sample.topic, sample.subtopic)
    if not same:
        return None

    # 1) Term appears in the target fact
    matches = _terms_in_text(sample.target_fact, [t for t, _ in same])
    if matches:
        correct = rng.choice(matches)
        wrongs = [t for t in peer_terms if t.casefold() != correct.casefold()]
        if wrongs:
            return _mcq_question(
                sample,
                prompt=(
                    "Which term best fits this claim?\n\n"
                    f"{sample.target_fact}"
                ),
                correct=correct,
                wrongs=wrongs,
                explanation=sample.target_fact,
                rng=rng,
            )

    # 2) Gloss → term using a same-subtopic entry
    peer_keys = {t.casefold() for t in peer_terms}
    candidates = [(t, g) for t, g in same if t.casefold() not in peer_keys]
    if not candidates:
        candidates = list(same)
    term, gloss = rng.choice(candidates)
    wrongs = [t for t in peer_terms if t.casefold() != term.casefold()]
    if not wrongs:
        return None
    return _mcq_question(
        sample,
        prompt=f"Which term matches this definition?\n\n{gloss}",
        correct=term,
        wrongs=wrongs,
        explanation=f"{term}: {gloss}",
        rng=rng,
    )


def _try_yes_no(
    sample: QuestionSample, rng: random.Random
) -> BuiltQuestion | None:
    want_true = rng.random() < 0.5
    if want_true:
        return BuiltQuestion(
            format="yes-no",
            prompt=f"True or false?\n\n{sample.target_fact}",
            options=["True", "False"],
            correct="True",
            explanation=sample.target_fact,
            topic=sample.topic,
            difficulty=sample.difficulty,
            subtopic=sample.subtopic,
        )

    false_stmt = _make_false_statement(sample, rng)
    if false_stmt is None:
        # Still deal a True question rather than failing the whole attempt
        return BuiltQuestion(
            format="yes-no",
            prompt=f"True or false?\n\n{sample.target_fact}",
            options=["True", "False"],
            correct="True",
            explanation=sample.target_fact,
            topic=sample.topic,
            difficulty=sample.difficulty,
            subtopic=sample.subtopic,
        )

    return BuiltQuestion(
        format="yes-no",
        prompt=f"True or false?\n\n{false_stmt}",
        options=["True", "False"],
        correct="False",
        explanation=f"False. The accurate claim is: {sample.target_fact}",
        topic=sample.topic,
        difficulty=sample.difficulty,
        subtopic=sample.subtopic,
    )


def _make_false_statement(
    sample: QuestionSample, rng: random.Random
) -> str | None:
    same = load_glossary(sample.topic, sample.subtopic)
    terms = [t for t, _ in same]
    matches = _terms_in_text(sample.target_fact, terms)
    if not matches:
        return None

    original = rng.choice(matches)
    replacements = [
        t
        for t, _ in sample.peer_glossary
        if t.casefold() != original.casefold()
    ]
    if not replacements:
        replacements = [
            t for t in terms if t.casefold() != original.casefold()
        ]
    if not replacements:
        return None

    substitute = rng.choice(replacements)
    pattern = re.compile(re.escape(original), re.IGNORECASE)
    false_stmt, n = pattern.subn(substitute, sample.target_fact, count=1)
    if n == 0 or false_stmt == sample.target_fact:
        return None
    return false_stmt


def _terms_in_text(text: str, terms: list[str]) -> list[str]:
    """Return glossary terms that appear in text (longest match first)."""
    found: list[str] = []
    lower = text.casefold()
    for term in sorted(terms, key=len, reverse=True):
        if not term:
            continue
        if term.casefold() in lower:
            found.append(term)
    return found


def _mcq_question(
    sample: QuestionSample,
    *,
    prompt: str,
    correct: str,
    wrongs: list[str],
    explanation: str,
    rng: random.Random,
) -> BuiltQuestion:
    pick = list(wrongs)
    rng.shuffle(pick)
    pick = pick[:3]
    options = [correct, *pick]
    rng.shuffle(options)
    return BuiltQuestion(
        format="mcq",
        prompt=prompt,
        options=options,
        correct=correct,
        explanation=explanation,
        topic=sample.topic,
        difficulty=sample.difficulty,
        subtopic=sample.subtopic,
    )
