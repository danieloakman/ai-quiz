---
name: quiz-researcher
description: >-
  Research a topic into the local quiz knowledge bank via the quiz_data CLI
  (facts, glossary, references, sources). Use when the user asks to research a
  topic, seed or deepen topic knowledge, or build a quiz fact bank. Thin Cursor
  adapter — follow agents/researcher.md.
---

# Quiz researcher

Follow the full contract in [agents/researcher.md](../../../agents/researcher.md).

## Hard rules

- Mutate knowledge **only** through `quiz_data` (never hand-edit `topics/`).
- On CLI errors, read stderr guidance, fix args, retry.
- Pair facts with glossary terms in each subtopic; record references; use sources for loose notes.
- Treat ≥8 facts as quiz-ready per subtopic; deepen later if the user asks.

## Start

```bash
quiz_data ensure-topic --slug <slug> --title '<Title>'
quiz_data status --topic <slug>
```
