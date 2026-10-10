class QuizDataError(Exception):
    """User-facing CLI error with guidance."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
