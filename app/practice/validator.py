from app.generation.validator import ExerciseValidator
from app.schemas import ExerciseItem


class PracticeValidator:
    """Practice-facing wrapper around the existing exercise validator."""

    def __init__(self, validator: ExerciseValidator) -> None:
        self.validator = validator

    def validate(
        self,
        exercises: list[ExerciseItem],
        expected_count: int | None = None,
    ) -> None:
        self.validator.validate(exercises, expected_count=expected_count)


__all__ = ["PracticeValidator"]
