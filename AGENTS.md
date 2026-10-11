# AGENTS

Topic quiz — agent-harness agnostic. Any tool that can run shell in this repo can research and host. Optional local web UI (`quiz-web`) browses topics and plays agent-authored questions (mcq, yes-no, freeform) through `quiz_host`.

## Architecture

- Knowledge lives under `topics/<slug>/` (gitignored). Treat storage as private.
- **Only mutate or sample via `quiz_data`.** Do not edit files under `topics/` directly.
- Researcher fills facts + glossary (+ references/sources). Quiz host samples tiny slices each turn.
- Source of truth for roles: [`agents/`](agents/). Optional Cursor skill wrappers under `.cursor/skills/` only point at those contracts.
- In-process hosting: [`src/quiz_host/`](src/quiz_host/) implements the same rules (OpenAI-compatible HTTP or Cursor Agent SDK). Web play samples via the library, then calls `QuizHost.deal` / `grade`.

## Setup

```bash
direnv allow   # flake.nix + .envrc: creates .venv, installs quiz_data
# or: nix develop
```

Configure a host before `quiz-web` (see README): `QUIZ_HOST=llm` or `QUIZ_HOST=cursor`.

## Roles

| Role | Contract |
| ---- | -------- |
| Research topic into the bank | [agents/researcher.md](agents/researcher.md) |
| Host a quiz round | [agents/quiz-host.md](agents/quiz-host.md) |

## CLI cheatsheet

```bash
quiz_data ensure-topic --slug pokemon --title 'Pokemon'
quiz_data ensure-subtopic --topic pokemon --slug types
quiz_data add-fact --topic pokemon --subtopic types --claim '...'
quiz_data add-glossary --topic pokemon --subtopic types --term '...' --gloss '...'
quiz_data add-reference --topic pokemon --ref 'https://...'
quiz_data status --topic pokemon
quiz_data sample-for-question --topic pokemon --difficulty hard --peers 3
```

Invalid input exits non-zero with guidance on stderr.
