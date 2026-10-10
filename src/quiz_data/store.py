from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from quiz_data import MIN_FACTS_READY, MIN_GLOSSARY_HARD_MCQ
from quiz_data.errors import QuizDataError
from quiz_data.lines import (
    append_line,
    format_glossary_line,
    parse_glossary_line,
    read_content_lines,
)
from quiz_data.paths import TEMPLATE_DIR, TOPICS_DIR, subtopic_dir, topic_dir

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SOURCE_TITLE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._ -]{0,80}$")


def validate_slug(slug: str, *, kind: str = "slug") -> str:
    slug = slug.strip()
    if not _SLUG_RE.fullmatch(slug):
        raise QuizDataError(
            f"Invalid {kind} {slug!r}. Use lowercase letters, digits, and "
            f"hyphens only (e.g. 'pokemon' or 'kanto-starters').\n"
            f"Example: quiz_data ensure-topic --slug pokemon --title 'Pokemon'"
        )
    if slug.startswith("_"):
        raise QuizDataError(
            f"Invalid {kind} {slug!r}: names starting with '_' are reserved."
        )
    return slug


def require_topic(slug: str) -> Path:
    slug = validate_slug(slug, kind="topic")
    path = topic_dir(slug)
    if not path.is_dir() or slug == "_TEMPLATE":
        raise QuizDataError(
            f"Topic {slug!r} not found. Create it with:\n"
            f"  quiz_data ensure-topic --slug {slug} --title 'Your Title'"
        )
    return path


def require_subtopic(topic: str, subtopic: str) -> Path:
    require_topic(topic)
    subtopic = validate_slug(subtopic, kind="subtopic")
    path = subtopic_dir(topic, subtopic)
    if not path.is_dir() or subtopic.startswith("_"):
        raise QuizDataError(
            f"Subtopic {subtopic!r} not found under topic {topic!r}. Create it with:\n"
            f"  quiz_data ensure-subtopic --topic {topic} --slug {subtopic}"
        )
    return path


def ensure_topic(slug: str, title: str) -> Path:
    slug = validate_slug(slug, kind="topic")
    title = title.strip()
    if not title:
        raise QuizDataError(
            "Title is required and must be non-empty.\n"
            "Example: quiz_data ensure-topic --slug pokemon --title 'Pokemon'"
        )
    if not TEMPLATE_DIR.is_dir():
        raise QuizDataError(
            f"Template missing at {TEMPLATE_DIR}. Restore topics/_TEMPLATE/."
        )
    dest = topic_dir(slug)
    if dest.exists():
        return dest
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        TEMPLATE_DIR,
        dest,
        ignore=shutil.ignore_patterns("subtopics"),
    )
    (dest / "subtopics").mkdir(exist_ok=True)
    (dest / "sources").mkdir(exist_ok=True)
    meta = dest / "meta.toml"
    meta.write_text(
        f'slug = "{slug}"\ntitle = "{_escape_toml(title)}"\nnotes = ""\n',
        encoding="utf-8",
    )
    for name in ("references.txt", "glossary.txt"):
        path = dest / name
        if not path.exists():
            path.write_text("", encoding="utf-8")
    return dest


def ensure_subtopic(topic: str, slug: str, title: str | None = None) -> Path:
    require_topic(topic)
    slug = validate_slug(slug, kind="subtopic")
    dest = subtopic_dir(topic, slug)
    if dest.exists():
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    header_title = (title or slug).strip()
    (dest / "facts.txt").write_text(
        f"# Subtopic: {header_title}\n# One atomic claim per line.\n",
        encoding="utf-8",
    )
    (dest / "glossary.txt").write_text(
        f"# Subtopic glossary: {header_title}\n# Term: short gloss\n",
        encoding="utf-8",
    )
    return dest


def add_fact(topic: str, subtopic: str, claim: str) -> None:
    path = require_subtopic(topic, subtopic) / "facts.txt"
    claim = _normalize_single_line(claim, field="claim")
    existing = read_content_lines(path)
    if claim in existing:
        raise QuizDataError(
            f"Duplicate fact (exact match already present) in "
            f"{topic}/{subtopic}:\n  {claim}"
        )
    # Cheap near-dup: casefold exact
    folded = claim.casefold()
    for line in existing:
        if line.casefold() == folded:
            raise QuizDataError(
                f"Near-duplicate fact already present (same text ignoring case):\n"
                f"  existing: {line}\n  new:      {claim}"
            )
    append_line(path, claim)


def add_glossary(
    topic: str,
    term: str,
    gloss: str,
    *,
    subtopic: str | None = None,
) -> None:
    term = term.strip()
    gloss = gloss.strip()
    if not term or not gloss:
        raise QuizDataError(
            "Both --term and --gloss are required and must be non-empty.\n"
            'Example: quiz_data add-glossary --topic pokemon --subtopic types '
            '--term "Pikachu" --gloss "Electric-type Mouse Pokémon"'
        )
    if "\n" in term or "\n" in gloss:
        raise QuizDataError("Term and gloss must be a single line each.")
    if ": " in term:
        raise QuizDataError(
            "Term must not contain ': ' (that separator is reserved for "
            "Term: gloss lines)."
        )
    line = format_glossary_line(term, gloss)
    # Validate round-trip
    parse_glossary_line(line)

    if subtopic:
        path = require_subtopic(topic, subtopic) / "glossary.txt"
    else:
        require_topic(topic)
        path = topic_dir(topic) / "glossary.txt"

    existing_terms = {
        parse_glossary_line(l)[0].casefold() for l in read_content_lines(path)
    }
    if term.casefold() in existing_terms:
        raise QuizDataError(
            f"Glossary term {term!r} already exists in "
            f"{topic}" + (f"/{subtopic}" if subtopic else "") + "."
        )
    append_line(path, line)


def add_reference(topic: str, ref: str) -> None:
    require_topic(topic)
    ref = _normalize_single_line(ref, field="ref")
    path = topic_dir(topic) / "references.txt"
    existing = read_content_lines(path)
    if ref in existing:
        raise QuizDataError(f"Reference already listed (exact match):\n  {ref}")
    append_line(path, ref)


def add_source(topic: str, title: str, body: str) -> Path:
    require_topic(topic)
    title = title.strip()
    if not _SOURCE_TITLE_RE.fullmatch(title):
        raise QuizDataError(
            f"Invalid source title {title!r}. Use 1–81 chars: letters, digits, "
            f"spaces, dots, underscores, hyphens; must start alphanumeric.\n"
            f"Example: quiz_data add-source --topic pokemon --title 'bulbapedia-types'"
        )
    body = body if body.endswith("\n") or body == "" else body + "\n"
    safe = re.sub(r"[^\w.-]+", "-", title.strip()).strip("-").lower() or "note"
    sources = topic_dir(topic) / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    path = sources / f"{safe}.txt"
    n = 1
    while path.exists():
        n += 1
        path = sources / f"{safe}-{n}.txt"
    path.write_text(body, encoding="utf-8")
    return path


@dataclass
class SubtopicStatus:
    slug: str
    fact_count: int
    glossary_count: int
    ready: bool
    hard_mcq_ok: bool

    @property
    def label(self) -> str:
        return "ready" if self.ready else "under-researched"


def list_topic_slugs() -> list[str]:
    if not TOPICS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in TOPICS_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and p.name != ".gitkeep"
    )


def list_subtopic_slugs(topic: str) -> list[str]:
    require_topic(topic)
    root = topic_dir(topic) / "subtopics"
    if not root.is_dir():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )


def subtopic_status(topic: str, subtopic: str) -> SubtopicStatus:
    path = require_subtopic(topic, subtopic)
    facts = read_content_lines(path / "facts.txt")
    gloss = read_content_lines(path / "glossary.txt")
    fc, gc = len(facts), len(gloss)
    return SubtopicStatus(
        slug=subtopic,
        fact_count=fc,
        glossary_count=gc,
        ready=fc >= MIN_FACTS_READY,
        hard_mcq_ok=fc >= MIN_FACTS_READY and gc >= MIN_GLOSSARY_HARD_MCQ,
    )


def load_topic_meta(topic: str) -> dict[str, str]:
    """Return meta.toml fields (slug, title, notes). Missing title falls back to slug."""
    path = require_topic(topic) / "meta.toml"
    data: dict[str, str] = {"slug": topic, "title": topic, "notes": ""}
    if not path.is_file():
        return data
    with path.open("rb") as f:
        raw = tomllib.load(f)
    for key in ("slug", "title", "notes"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            data[key] = val.strip()
    return data


def topic_status(topic: str) -> dict:
    require_topic(topic)
    meta = load_topic_meta(topic)
    subs = [subtopic_status(topic, s) for s in list_subtopic_slugs(topic)]
    refs = read_content_lines(topic_dir(topic) / "references.txt")
    topic_gloss = read_content_lines(topic_dir(topic) / "glossary.txt")
    return {
        "topic": topic,
        "title": meta["title"],
        "notes": meta.get("notes", ""),
        "references": len(refs),
        "topic_glossary": len(topic_gloss),
        "subtopics": subs,
        "ready_subtopics": sum(1 for s in subs if s.ready),
        "total_subtopics": len(subs),
        "total_facts": sum(s.fact_count for s in subs),
        "total_glossary": sum(s.glossary_count for s in subs) + len(topic_gloss),
    }


def load_facts(topic: str, subtopic: str) -> list[str]:
    return read_content_lines(require_subtopic(topic, subtopic) / "facts.txt")


def load_glossary(topic: str, subtopic: str | None = None) -> list[tuple[str, str]]:
    if subtopic:
        path = require_subtopic(topic, subtopic) / "glossary.txt"
    else:
        require_topic(topic)
        path = topic_dir(topic) / "glossary.txt"
    out: list[tuple[str, str]] = []
    for line in read_content_lines(path):
        try:
            out.append(parse_glossary_line(line))
        except ValueError:
            continue
    return out


def _normalize_single_line(value: str, *, field: str) -> str:
    value = value.strip()
    if not value:
        raise QuizDataError(
            f"{field} must be non-empty.\n"
            f'Example: quiz_data add-fact --topic pokemon --subtopic types '
            f'--claim "Pikachu is an Electric-type Pokémon."'
        )
    if "\n" in value or "\r" in value:
        raise QuizDataError(
            f"{field} must be a single line (no newlines). "
            f"Split into separate facts if needed."
        )
    return value


def _escape_toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
