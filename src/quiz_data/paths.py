from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = _PACKAGE_DIR.parent.parent
TOPICS_DIR = REPO_ROOT / "topics"
TEMPLATE_DIR = TOPICS_DIR / "_TEMPLATE"


def topic_dir(slug: str) -> Path:
    return TOPICS_DIR / slug


def subtopic_dir(topic: str, subtopic: str) -> Path:
    return topic_dir(topic) / "subtopics" / subtopic
