"""Prompt templates distilled from agents/quiz-host.md."""

from __future__ import annotations

import json
from collections.abc import Sequence

from quiz_data.sample import QuestionSample

DEAL_SYSTEM = """\
You are a quiz host. Author exactly one quiz question from the knowledge sample.

Rules:
- Ground every claim in the sample. Do not invent facts or MCQ distractors.
- MCQ wrong options must be terms from peer_glossary only.
- If notes warn hard_mcq_weak or no_glossary_peers, prefer freeform or yes-no over mcq.
- yes-no options must be exactly ["True", "False"].
- freeform: options must be [] (empty). correct is a short reference answer for grading.
- Pick one format from the allowed list.
- Return ONLY a JSON object with keys:
  format, prompt, options, correct, explanation
"""

GRADE_SYSTEM = """\
You grade one freeform quiz answer against the target knowledge.
Be fair and not pedantic: credit semantic matches to the target fact.
Return ONLY a JSON object with keys: correct (boolean), explanation (string).
"""


def sample_payload(sample: QuestionSample) -> dict:
    return {
        "topic": sample.topic,
        "difficulty": sample.difficulty,
        "subtopic": sample.subtopic,
        "target_fact": sample.target_fact,
        "peer_glossary": [{"term": t, "gloss": g} for t, g in sample.peer_glossary],
        "peer_facts": list(sample.peer_facts),
        "hard_mcq_ok": sample.hard_mcq_ok,
        "notes": list(sample.notes),
    }


def deal_messages(
    sample: QuestionSample, formats: Sequence[str]
) -> list[dict[str, str]]:
    user = {
        "allowed_formats": list(formats),
        "sample": sample_payload(sample),
    }
    return [
        {"role": "system", "content": DEAL_SYSTEM},
        {"role": "user", "content": json.dumps(user, indent=2)},
    ]


def grade_messages(
    *,
    prompt: str,
    target_fact: str,
    reference: str,
    answer: str,
) -> list[dict[str, str]]:
    user = {
        "question_prompt": prompt,
        "target_fact": target_fact,
        "reference_answer": reference,
        "player_answer": answer,
    }
    return [
        {"role": "system", "content": GRADE_SYSTEM},
        {"role": "user", "content": json.dumps(user, indent=2)},
    ]
