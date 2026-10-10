from __future__ import annotations

from pathlib import Path


def read_content_lines(path: Path) -> list[str]:
    """Return non-empty, non-comment lines from a text file."""
    if not path.is_file():
        return []
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    existing = path.read_text(encoding="utf-8")
    prefix = "" if (not existing or existing.endswith("\n")) else "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{prefix}{line}\n")


def parse_glossary_line(line: str) -> tuple[str, str]:
    if ": " not in line:
        raise ValueError(
            "Glossary lines must look like 'Term: short gloss' "
            "(term, colon, space, gloss)."
        )
    term, gloss = line.split(": ", 1)
    term, gloss = term.strip(), gloss.strip()
    if not term or not gloss:
        raise ValueError("Both term and gloss are required (non-empty).")
    return term, gloss


def format_glossary_line(term: str, gloss: str) -> str:
    return f"{term}: {gloss}"
