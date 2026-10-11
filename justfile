# ai-quiz task runner — list with `just` or `just --list`

set dotenv-load := false
set shell := ["bash", "-euo", "pipefail", "-c"]

# Override: `just cursor_pass=other/path web-cursor`
cursor_pass := env_var_or_default("CURSOR_PASS_PATH", "api_keys/personal/cursor_ai")

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

# Web UI with Cursor host; loads CURSOR_API_KEY from `pass`
web-cursor:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! uv run python -c 'import cursor_sdk' >/dev/null 2>&1; then
      uv sync --extra web --extra host --extra cursor --group dev
    fi
    export QUIZ_HOST=cursor
    export CURSOR_API_KEY
    CURSOR_API_KEY="$(pass show '{{ cursor_pass }}')"
    exec uv run quiz-web

# Same as web-cursor, but auto-reloads on py/html/css/js changes under src/
web-cursor-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! uv run python -c 'import cursor_sdk' >/dev/null 2>&1; then
      uv sync --extra web --extra host --extra cursor --group dev
    fi
    export QUIZ_HOST=cursor
    export CURSOR_API_KEY
    CURSOR_API_KEY="$(pass show '{{ cursor_pass }}')"
    exec uv run uvicorn quiz_web.app:app \
      --host 127.0.0.1 \
      --port 8765 \
      --reload \
      --reload-dir src \
      --reload-include '*.py' \
      --reload-include '*.html' \
      --reload-include '*.css' \
      --reload-include '*.js'
