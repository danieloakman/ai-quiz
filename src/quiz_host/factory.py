"""Build a QuizHost from environment variables."""

from __future__ import annotations

import os

from quiz_host.cursor_host import CursorHost
from quiz_host.errors import QuizHostError
from quiz_host.llm_host import LlmHost
from quiz_host.openai_compat import OpenAICompatClient
from quiz_host.protocols import QuizHost


def _llm_configured() -> bool:
    return bool(
        os.environ.get("QUIZ_LLM_BASE_URL", "").strip()
        and os.environ.get("QUIZ_LLM_MODEL", "").strip()
    )


def _cursor_configured() -> bool:
    return bool(os.environ.get("CURSOR_API_KEY", "").strip())


def host_from_env() -> QuizHost:
    kind = os.environ.get("QUIZ_HOST", "").strip().lower()
    if not kind:
        if _llm_configured():
            kind = "llm"
        elif _cursor_configured():
            kind = "cursor"
        else:
            raise QuizHostError(
                "No quiz host configured. Set QUIZ_HOST=llm or QUIZ_HOST=cursor.\n"
                "For llm: QUIZ_LLM_BASE_URL, QUIZ_LLM_MODEL, and optionally "
                "QUIZ_LLM_API_KEY.\n"
                "For cursor: CURSOR_API_KEY (and optionally QUIZ_CURSOR_MODEL)."
            )

    if kind == "llm":
        base = os.environ.get("QUIZ_LLM_BASE_URL", "").strip()
        model = os.environ.get("QUIZ_LLM_MODEL", "").strip()
        api_key = os.environ.get("QUIZ_LLM_API_KEY", "").strip() or "no-key"
        if not base or not model:
            raise QuizHostError(
                "QUIZ_HOST=llm requires QUIZ_LLM_BASE_URL and QUIZ_LLM_MODEL."
            )
        return LlmHost(OpenAICompatClient(base_url=base, api_key=api_key, model=model))

    if kind == "cursor":
        api_key = os.environ.get("CURSOR_API_KEY", "").strip()
        if not api_key:
            raise QuizHostError("QUIZ_HOST=cursor requires CURSOR_API_KEY.")
        model = os.environ.get("QUIZ_CURSOR_MODEL", "").strip() or "composer-2.5"
        return CursorHost(api_key=api_key, model=model)

    raise QuizHostError(f"Unknown QUIZ_HOST={kind!r}. Choose llm or cursor.")
