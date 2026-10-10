# ai-quiz

Cursor-only couples topic quiz. A researcher agent fills a local knowledge bank; a host agent deals random questions in chat. No web UI in v1.

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
```

Requires Python 3.11+ (via `uv` is fine).

## How it works

- Topic knowledge lives under `topics/` (**gitignored**).
- Agents talk only to the **`quiz_data`** CLI (validated API; storage can change later).
- Playtime: host calls `sample-for-question` so only a tiny fact/glossary sample enters the chat context.

See [AGENTS.md](AGENTS.md), [docs/topic-format.md](docs/topic-format.md), and `agents/`.

## CLI examples

```bash
quiz_data ensure-topic --slug smoke --title Smoke
quiz_data ensure-subtopic --topic smoke --slug basics
quiz_data add-fact --topic smoke --subtopic basics --claim 'Smoke is a test topic.'
quiz_data add-glossary --topic smoke --subtopic basics --term 'Smoke' --gloss 'Test topic label'
quiz_data add-reference --topic smoke --ref 'https://example.com'
quiz_data status --topic smoke
quiz_data sample-for-question --topic smoke --difficulty easy --peers 2
```

## Copy-paste prompts

**Research**

> Research topic pokemon into the quiz bank. Create subtopics as needed. Aim for several ready buckets (≥8 facts each) with glossary terms. Use quiz_data only. Follow agents/researcher.md.

**Play**

> Topic: pokemon. Formats: mcq, freeform. Questions: 5. Difficulty: moderate. Host using agents/quiz-host.md and quiz_data sample-for-question.

Pokemon seeding is a follow-up step (local only; not committed).
