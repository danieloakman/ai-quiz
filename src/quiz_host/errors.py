"""Errors for quiz host backends."""

from __future__ import annotations


class QuizHostError(Exception):
    """Host misconfiguration, authoring failure, or grade failure."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
