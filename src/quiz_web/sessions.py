"""In-memory play sessions."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field

from quiz_host.protocols import BuiltQuestion


@dataclass
class PlaySession:
    id: str
    topic: str
    title: str
    formats: list[str]
    questions_total: int
    difficulty: str
    time_limit_seconds: int | None = None
    score: int = 0
    answered: int = 0
    current: BuiltQuestion | None = None
    # Ready-ahead questions (not exposed in the public session view).
    prefetch: list[BuiltQuestion] = field(default_factory=list)
    finished: bool = False
    last_result: dict | None = None
    history: list[dict] = field(default_factory=list)
    dealing: bool = False
    deal_error: str | None = None
    # Bumped to drop in-flight prefetch deals after invalidate (e.g. difficulty).
    prefetch_generation: int = 0
    prefetch_worker_active: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, PlaySession] = {}

    def create(self, session: PlaySession) -> PlaySession:
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> PlaySession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


def new_session_id() -> str:
    return secrets.token_urlsafe(16)
