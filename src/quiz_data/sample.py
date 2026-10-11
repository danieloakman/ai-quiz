from __future__ import annotations

import random
from dataclasses import dataclass

from quiz_data import MIN_GLOSSARY_HARD_MCQ
from quiz_data.errors import QuizDataError
from quiz_data.store import (
    list_subtopic_slugs,
    load_facts,
    load_glossary,
    require_topic,
    subtopic_status,
)

DIFFICULTIES = ("easy", "moderate", "hard")


@dataclass
class QuestionSample:
    topic: str
    difficulty: str
    subtopic: str
    target_fact: str
    peer_glossary: list[tuple[str, str]]
    peer_facts: list[str]
    hard_mcq_ok: bool
    notes: list[str]


def sample_for_question(
    topic: str,
    difficulty: str,
    *,
    peers: int = 3,
    rng: random.Random | None = None,
) -> QuestionSample:
    require_topic(topic)
    difficulty = difficulty.strip().lower()
    if difficulty not in DIFFICULTIES:
        raise QuizDataError(
            f"Invalid difficulty {difficulty!r}. Choose one of: "
            f"{', '.join(DIFFICULTIES)}.\n"
            f"Example: quiz_data sample-for-question --topic pokemon "
            f"--difficulty hard --peers 3"
        )
    if peers < 0:
        raise QuizDataError("--peers must be >= 0.")

    rng = rng or random.Random()
    ready = [s for s in list_subtopic_slugs(topic) if subtopic_status(topic, s).ready]
    if not ready:
        raise QuizDataError(
            f"No quiz-ready subtopics for topic {topic!r} "
            f"(need ≥8 facts each). Check:\n"
            f"  quiz_data status --topic {topic}\n"
            f"Research more, then retry."
        )

    # Prefer hard-MCQ-capable buckets when asking hard
    pool = ready
    if difficulty == "hard":
        hard_ok = [s for s in ready if subtopic_status(topic, s).hard_mcq_ok]
        if hard_ok:
            pool = hard_ok

    subtopic = rng.choice(pool)
    status = subtopic_status(topic, subtopic)
    facts = load_facts(topic, subtopic)
    target = rng.choice(facts)

    same_gloss = load_glossary(topic, subtopic)
    other_subs = [s for s in ready if s != subtopic]
    other_gloss: list[tuple[str, str]] = []
    for s in other_subs:
        other_gloss.extend(load_glossary(topic, s))
    # Include topic-wide glossary as distant peers
    other_gloss.extend(load_glossary(topic, None))

    peer_glossary = _pick_glossary_peers(
        difficulty=difficulty,
        peers=peers,
        same=same_gloss,
        other=other_gloss,
        rng=rng,
    )

    # Extra peer facts for context (same subtopic, excluding target)
    other_facts = [f for f in facts if f != target]
    peer_facts = rng.sample(other_facts, k=min(2, len(other_facts)))

    notes: list[str] = []
    if difficulty == "hard" and len(same_gloss) < MIN_GLOSSARY_HARD_MCQ:
        notes.append(
            "hard_mcq_weak: fewer than 4 glossary terms in-bucket; "
            "prefer freeform/yes-no or easier difficulty."
        )
    if not peer_glossary and peers > 0:
        notes.append(
            "no_glossary_peers: inventing MCQ distractors is discouraged; "
            "use freeform/yes-no."
        )

    return QuestionSample(
        topic=topic,
        difficulty=difficulty,
        subtopic=subtopic,
        target_fact=target,
        peer_glossary=peer_glossary,
        peer_facts=peer_facts,
        hard_mcq_ok=status.hard_mcq_ok,
        notes=notes,
    )


def _pick_glossary_peers(
    *,
    difficulty: str,
    peers: int,
    same: list[tuple[str, str]],
    other: list[tuple[str, str]],
    rng: random.Random,
) -> list[tuple[str, str]]:
    if peers == 0:
        return []

    def dedupe(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        for term, gloss in items:
            key = term.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append((term, gloss))
        return out

    same = dedupe(same)
    other = dedupe(other)
    # Avoid overlapping terms when mixing
    same_keys = {t.casefold() for t, _ in same}
    other = [(t, g) for t, g in other if t.casefold() not in same_keys]

    if difficulty == "hard":
        pool = same
        return rng.sample(pool, k=min(peers, len(pool)))

    if difficulty == "moderate":
        # Mostly same-subtopic; at most one distant peer
        result: list[tuple[str, str]] = []
        same_n = min(peers, len(same))
        if same_n:
            result.extend(rng.sample(same, k=same_n))
        if len(result) < peers and other:
            distant = rng.choice(other)
            # Replace last same peer with distant if we already filled, else append
            if len(result) >= peers and result:
                result[-1] = distant
            elif distant not in result:
                result.append(distant)
            result = result[:peers]
        elif len(result) < peers and same:
            # pad from remaining same if any left
            remain = [x for x in same if x not in result]
            need = peers - len(result)
            result.extend(rng.sample(remain, k=min(need, len(remain))))
        return result[:peers]

    # easy: prefer other subtopics, fall back to same
    pool = other if other else same
    if len(pool) < peers and same:
        pool = dedupe(pool + same)
    return rng.sample(pool, k=min(peers, len(pool)))


def format_sample(sample: QuestionSample) -> str:
    lines = [
        f"topic: {sample.topic}",
        f"difficulty: {sample.difficulty}",
        f"subtopic: {sample.subtopic}",
        f"hard_mcq_ok: {str(sample.hard_mcq_ok).lower()}",
        f"target_fact: {sample.target_fact}",
        "peer_glossary:",
    ]
    if sample.peer_glossary:
        for term, gloss in sample.peer_glossary:
            lines.append(f"  - {term}: {gloss}")
    else:
        lines.append("  (none)")
    lines.append("peer_facts:")
    if sample.peer_facts:
        for fact in sample.peer_facts:
            lines.append(f"  - {fact}")
    else:
        lines.append("  (none)")
    if sample.notes:
        lines.append("notes:")
        for note in sample.notes:
            lines.append(f"  - {note}")
    return "\n".join(lines) + "\n"
