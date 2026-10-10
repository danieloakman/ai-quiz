# ai-quiz

Cursor-only topic quiz for date night (or anyone). Research any subject into a local knowledge bank, then play MCQ / yes-no / freeform rounds in Cursor chat — no web UI.

## Idea

1. **Researcher agent** gathers atomic facts + a glossary ahead of time (via CLI).
2. **Quiz host agent** deals random questions from that bank at playtime.
3. Formats and difficulty are chosen at game start; scores live in the chat thread.

Topic data stays on your machine under `topics/` (gitignored). Agents never hand-edit those files — they only use the `quiz_data` CLI, so storage can change later without rewriting prompts.

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
```

Python 3.11+ required (`uv` recommended).

## How it works

| Piece | Role |
| ----- | ---- |
| `quiz_data` CLI | Controlled API: create topics, add facts/glossary/references, sample for a turn |
| `topics/<slug>/` | Local fact bank (gitignored); subtopics hold `facts.txt` + `glossary.txt` |
| `agents/` + Cursor skills | Contracts for researcher and quiz host |

Playtime stays token-cheap: the host calls `sample-for-question` and only sees a tiny slice (target fact + glossary peers), not the whole topic.

**Difficulty:** `easy` · `moderate` · `hard` (how tightly MCQ distractors stay in the same subtopic).  
**Readiness:** a subtopic needs ≥8 facts to be dealt; hard MCQ also wants ≥4 glossary terms.

More detail: [AGENTS.md](AGENTS.md), [docs/topic-format.md](docs/topic-format.md).

## CLI cheatsheet

```bash
quiz_data ensure-topic --slug pokemon --title 'Pokemon'
quiz_data ensure-subtopic --topic pokemon --slug types
quiz_data add-fact --topic pokemon --subtopic types --claim 'Pikachu is an Electric-type Pokémon.'
quiz_data add-glossary --topic pokemon --subtopic types --term 'Pikachu' --gloss 'Electric-type Mouse Pokémon'
quiz_data add-reference --topic pokemon --ref 'https://example.com'
quiz_data status --topic pokemon
quiz_data sample-for-question --topic pokemon --difficulty hard --peers 3
```

Invalid input exits non-zero with guidance on stderr.

## Copy-paste prompts (Cursor)

**Research**

> Research topic pokemon into the quiz bank. Create subtopics as needed. Aim for several ready buckets (≥8 facts each) with glossary terms. Use quiz_data only. Follow agents/researcher.md.

**Play**

> Topic: pokemon. Formats: mcq, freeform. Questions: 5. Difficulty: moderate. Host using agents/quiz-host.md and quiz_data sample-for-question.

## Status

v1 is Cursor + local files only. Topic corpora are not committed. Web UI, vectors, and persisted scores are out of scope for now.
