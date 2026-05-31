from app.schemas import ExerciseItem


class ExerciseValidator:
    def validate(self, exercises: list[ExerciseItem], expected_count: int | None = None) -> None:
        if expected_count is not None and len(exercises) != expected_count:
            raise ValueError(
                f"Expected {expected_count} exercises, but received {len(exercises)}."
            )

        for exercise in exercises:
            self._validate_item(exercise)

    def _validate_item(self, exercise: ExerciseItem) -> None:
        if not exercise.question_text.strip():
            raise ValueError("Exercise question text must not be empty.")

        if not exercise.explanation.strip():
            raise ValueError("Exercise explanation must not be empty.")

        if exercise.exercise_type == "fill_blank":
            if not exercise.correct_answer.strip():
                raise ValueError("Fill-in-the-blank exercises require a correct answer.")
            return

        if len(exercise.options) != 4:
            raise ValueError("MCQ exercises must contain exactly 4 options.")

        correct_options = [option for option in exercise.options if option.is_correct]
        if len(correct_options) != 1:
            raise ValueError("MCQ exercises must contain exactly one correct option.")

        valid_labels = {option.label for option in exercise.options}
        if exercise.correct_answer not in valid_labels:
            raise ValueError("Correct answer must match one of the option labels.")
