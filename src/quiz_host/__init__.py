"""Agent-backed quiz host: deal and grade from sampled knowledge."""

from quiz_host.errors import QuizHostError
from quiz_host.factory import host_from_env
from quiz_host.protocols import FORMATS, BuiltQuestion, GradeResult, QuizHost

__all__ = [
    "FORMATS",
    "BuiltQuestion",
    "GradeResult",
    "QuizHost",
    "QuizHostError",
    "host_from_env",
]
