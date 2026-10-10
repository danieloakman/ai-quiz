from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import quiz_data.paths as paths
import quiz_data.store as store


@pytest.fixture
def topics_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "topics"
    template_src = Path(__file__).resolve().parents[1] / "topics" / "_TEMPLATE"
    template_dst = root / "_TEMPLATE"
    shutil.copytree(template_src, template_dst)
    monkeypatch.setattr(paths, "TOPICS_DIR", root)
    monkeypatch.setattr(paths, "TEMPLATE_DIR", template_dst)
    monkeypatch.setattr(store, "TOPICS_DIR", root)
    monkeypatch.setattr(store, "TEMPLATE_DIR", template_dst)
    return root


@pytest.fixture
def ready_topic(topics_root: Path) -> str:
    from quiz_data.store import (
        add_fact,
        add_glossary,
        ensure_subtopic,
        ensure_topic,
    )

    slug = "widgets"
    ensure_topic(slug, "Widgets")
    ensure_subtopic(slug, "basics", "Basics")
    facts = [
        "A red widget weighs two kilograms.",
        "Blue widgets float in freshwater.",
        "Green widgets store kinetic energy.",
        "Yellow widgets emit a soft click when armed.",
        "Orange widgets cannot be stacked above three.",
        "Purple widgets conduct heat poorly.",
        "Silver widgets resist mild acids.",
        "Copper widgets tarnish outdoors within a week.",
        "The factory marks each widget with a serial stamp.",
    ]
    gloss = [
        ("Red widget", "A widget colored red that weighs two kilograms."),
        ("Blue widget", "A buoyant widget that floats in freshwater."),
        ("Green widget", "A widget that stores kinetic energy."),
        ("Yellow widget", "A widget that clicks softly when armed."),
        ("Serial stamp", "Factory mark identifying an individual widget."),
    ]
    for claim in facts:
        add_fact(slug, "basics", claim)
    for term, g in gloss:
        add_glossary(slug, term, g, subtopic="basics")
    return slug
