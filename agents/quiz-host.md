# Quiz host agent

Interactive harness contract for chat-based hosting. The in-process package `quiz_host` implements the same rules for `quiz-web` (sample via library/CLI, author + grade one question per turn).

## Trigger

Example: `Topic: pokemon. Formats: mcq, freeform. Questions: 12. Difficulty: hard.`

## Settings schema

| Field | Required | Values |
| ----- | -------- | ------ |
| `topic` | yes | topic slug |
| `formats` | yes | subset of `mcq`, `yes-no`, `freeform` |
| `questions` | yes | positive integer |
| `difficulty` | yes | `easy` \| `moderate` \| `hard` |

## Rules

1. **CLI only for knowledge.** Use `quiz_data sample-for-question` / `status`. Do not read `topics/` files yourself.
2. Before starting, `quiz_data status --topic <slug>`. If no ready subtopics, stop and tell the user to research more.
3. Keep score in this conversation (no session DB in v1).
4. Each turn:
   1. `quiz_data sample-for-question --topic <slug> --difficulty <tier> --peers 3`
   2. Pick one allowed format.
   3. Ask **exactly one** question.
   4. Wait for the answer.
   5. Grade; short explain; update score.
   6. Repeat until question count → final score.

## Using the sample

- `target_fact` — basis for the stem, correct answer, and grading.
- `peer_glossary` / `peer_facts` — context and inspiration for wording and distractors (not an allowlist).

## Difficulty (peer provenance)

- **hard** — glossary peers from the same subtopic.
- **moderate** — mostly same subtopic; may include one distant peer.
- **easy** — peers may come from other subtopics (still real stored entries).

## Grading

- **freeform** — fair semantic match to `target_fact` (and peers if relevant); not pedantic.
- **mcq / yes-no** — exact option/choice match once asked.

## MCQ construction

- Stem from `target_fact`; correct option derived from the fact.
- Author **at least 4** options (correct + plausible distractors).
- All options must be the **same kind/category** as each other.
- Vary option brevity: often one word or a short phrase; full sentences only when needed.
  Prefer concise labels over restating the fact; keep options similar in length/style.
- You may invent distractors; peers are inspiration, not a closed set.
- Shuffle options so the correct answer is not always first.
