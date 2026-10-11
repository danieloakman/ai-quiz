# ai-quiz task runner — list with `just` or `just --list`

set dotenv-load := false

default:
    @just --list

# Install from uv.lock (web + host + dev tools)
sync:
    uv sync --extra web --extra host --group dev

# Same as sync, plus Cursor Agent SDK extra
sync-cursor:
    uv sync --extra web --extra host --extra cursor --group dev

# Run unit/API tests
test *args:
    uv run pytest {{args}}

# Lint (ruff check)
lint:
    uv run ruff check .

# Check formatting without writing
fmt-check:
    uv run ruff format --check .

# Apply ruff format + autofix
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Lint + format check + tests (matches CI)
check: lint fmt-check test

# Local web UI (needs QUIZ_HOST configured — see README)
web:
    uv run quiz-web
