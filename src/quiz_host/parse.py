"""Parse and validate host JSON into BuiltQuestion / GradeResult."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from quiz_data.sample import QuestionSample
from quiz_host.errors import QuizHostError
from quiz_host.protocols import FORMATS, BuiltQuestion, GradeResult

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise QuizHostError("Host returned empty response.")
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = _FENCE_RE.search(raw)
    if m:
        data = json.loads(m.group(1))
        if isinstance(data, dict):
            return data
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(raw[start : end + 1])
        if isinstance(data, dict):
            return data
    raise QuizHostError("Host response was not valid JSON object.")


def normalize_formats(formats: Sequence[str]) -> list[str]:
    if not formats:
        raise QuizHostError(
            "At least one format is required. Choose from: " + ", ".join(FORMATS) + "."
        )
    out: list[str] = []
    seen: set[str] = set()
    for raw in formats:
        fmt = str(raw).strip().lower()
        if fmt not in FORMATS:
            raise QuizHostError(
                f"Invalid format {raw!r}. Choose from: {', '.join(FORMATS)}."
            )
        if fmt not in seen:
            seen.add(fmt)
            out.append(fmt)
    return out


def question_from_payload(
    data: dict,
    sample: QuestionSample,
    allowed: Sequence[str],
) -> BuiltQuestion:
    fmt = str(data.get("format", "")).strip().lower()
    if fmt not in allowed:
        raise QuizHostError(
            f"Host chose format {fmt!r}; allowed: {', '.join(allowed)}."
        )
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        raise QuizHostError("Host question missing prompt.")
    correct = str(data.get("correct", "")).strip()
    if not correct:
        raise QuizHostError("Host question missing correct answer.")
    explanation = str(data.get("explanation", "")).strip() or sample.target_fact
    raw_opts = data.get("options", [])
    if raw_opts is None:
        raw_opts = []
    if not isinstance(raw_opts, list):
        raise QuizHostError("Host options must be a list.")
    options = [str(o).strip() for o in raw_opts if str(o).strip()]

    if fmt == "yes-no":
        options = ["True", "False"]
        if correct not in ("True", "False"):
            raise QuizHostError("yes-no correct must be True or False.")
    elif fmt == "freeform":
        options = []
    elif fmt == "mcq":
        if len(options) < 4:
            raise QuizHostError("MCQ needs at least four options.")
        folded = [o.casefold() for o in options]
        if len(set(folded)) != len(folded):
            raise QuizHostError("MCQ options must be unique.")
        if correct not in options:
            raise QuizHostError("MCQ correct answer must appear in options.")
        if all(o == correct for o in options):
            raise QuizHostError("MCQ needs at least one distractor.")

    return BuiltQuestion(
        format=fmt,
        prompt=prompt,
        options=options,
        correct=correct,
        explanation=explanation,
        topic=sample.topic,
        difficulty=sample.difficulty,
        subtopic=sample.subtopic,
        target_fact=sample.target_fact,
    )


def grade_from_payload(data: dict, fallback_explanation: str) -> GradeResult:
    if "correct" not in data:
        raise QuizHostError("Grade response missing 'correct'.")
    val = data["correct"]
    if isinstance(val, bool):
        ok = val
    elif isinstance(val, str):
        low = val.strip().lower()
        if low in ("true", "yes", "1"):
            ok = True
        elif low in ("false", "no", "0"):
            ok = False
        else:
            raise QuizHostError(f"Invalid grade correct value: {val!r}")
    else:
        raise QuizHostError("Grade 'correct' must be boolean.")
    explanation = str(data.get("explanation", "")).strip() or fallback_explanation
    return GradeResult(correct=ok, explanation=explanation)
