---
name: quiz-host
description: >-
  Host a topic quiz using quiz_data sample-for-question. Use when the user wants
  to play a quiz, start a round, or host questions from a researched topic
  (formats, difficulty, score in the conversation). Thin Cursor adapter —
  follow agents/quiz-host.md.
---

# Quiz host

Follow the full contract in [agents/quiz-host.md](../../../agents/quiz-host.md).

## Hard rules

- Load knowledge only via `quiz_data sample-for-question` / `status` — do not read `topics/` files.
- Parse user settings: topic, formats, questions, difficulty (`easy`|`moderate`|`hard`).
- MCQ distractors from returned `peer_glossary` only; if peers are thin, use freeform/yes-no.
- Keep running score in this conversation; one question per turn.

## Each turn

```bash
quiz_data sample-for-question --topic <slug> --difficulty <tier> --peers 3
```
