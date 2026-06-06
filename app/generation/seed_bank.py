import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas import ExerciseOption, PracticePlan


@dataclass(slots=True, frozen=True)
class SeedExercise:
    exercise_code: str
    exercise_type: str
    topic_code: str
    subtopic: str
    level: str
    difficulty: str
    skill: str
    question_text: str
    options: list[ExerciseOption]
    correct_answer: str
    explanation: str
    error_tag: str
    source: str


class SeedExerciseBank:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: list[SeedExercise] | None = None

    def select_for_plan(self, plan: PracticePlan, limit: int) -> list[SeedExercise]:
        topic_codes = self._topic_candidates(plan.topic)
        records = [
            record
            for record in self._load_records()
            if record.topic_code in topic_codes
            and self._exercise_type_matches(plan.exercise_type, record.exercise_type)
        ]
        records.sort(key=lambda record: self._rank(record, plan))
        return records[:limit]

    def format_reference_examples(
        self,
        examples: list[SeedExercise],
        limit: int = 3,
    ) -> str:
        if not examples:
            return "No seed exercise examples available."

        payload = [
            {
                "exercise_code": example.exercise_code,
                "subtopic": example.subtopic,
                "difficulty": example.difficulty,
                "question_text": example.question_text,
                "options": [
                    {
                        "label": option.label,
                        "text": option.text,
                        "is_correct": option.is_correct,
                    }
                    for option in example.options
                ],
                "correct_answer": example.correct_answer,
                "explanation": example.explanation,
                "error_tag": example.error_tag,
            }
            for example in examples[:limit]
        ]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _load_records(self) -> list[SeedExercise]:
        if self._records is not None:
            return self._records

        if not self.path.exists():
            self._records = []
            return self._records

        raw_records = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw_records, list):
            raise ValueError("Seed exercise file must contain a JSON array.")

        self._records = [
            self._record_to_seed_exercise(record)
            for record in raw_records
            if isinstance(record, dict)
        ]
        return self._records

    def _record_to_seed_exercise(self, record: dict[str, Any]) -> SeedExercise:
        return SeedExercise(
            exercise_code=str(record["exercise_code"]),
            exercise_type=str(record["exercise_type"]),
            topic_code=str(record["topic_code"]),
            subtopic=str(record["subtopic"]),
            level=str(record["level"]),
            difficulty=str(record["difficulty"]),
            skill=str(record["skill"]),
            question_text=str(record["question_text"]),
            options=[
                ExerciseOption(
                    label=str(option["label"]),
                    text=str(option["text"]),
                    is_correct=bool(option["is_correct"]),
                )
                for option in record["options"]
            ],
            correct_answer=str(record["correct_answer"]),
            explanation=str(record["explanation"]),
            error_tag=str(record.get("error_tag", "")),
            source=str(record["source"]),
        )

    def _exercise_type_matches(self, requested: str, available: str) -> bool:
        if requested == available:
            return True
        if requested == "mcq" and available.endswith("_mcq"):
            return True
        if requested == "grammar_mcq" and available == "mcq":
            return True
        if requested == "vocabulary_mcq" and available == "mcq":
            return True
        return False

    def _topic_candidates(self, topic: str) -> set[str]:
        if topic == "vocabulary":
            return {"vocabulary", "travel_vocabulary"}
        return {topic}

    def _rank(
        self,
        record: SeedExercise,
        plan: PracticePlan,
    ) -> tuple[int, int, int, int, str]:
        return (
            self._topic_distance(record.topic_code, plan.topic),
            self._subtopic_distance(record.subtopic, plan.target_subtopic),
            self._content_theme_distance(record, plan.content_theme),
            0 if record.difficulty == plan.difficulty else 1,
            self._difficulty_distance(record.difficulty, plan.difficulty),
            record.exercise_code,
        )

    def _topic_distance(self, actual: str, expected: str) -> int:
        return 0 if actual == expected else 1

    def _difficulty_distance(self, actual: str, expected: str) -> int:
        order = {"easy": 0, "medium": 1, "hard": 2}
        return abs(order.get(actual, 1) - order.get(expected, 1))

    def _subtopic_distance(self, actual: str, expected: str | None) -> int:
        if not expected:
            return 0
        if actual == expected:
            return 0
        if actual.startswith(expected) or expected.startswith(actual):
            return 1
        actual_tokens = set(actual.split("_"))
        expected_tokens = set(expected.split("_"))
        if "past" in expected_tokens:
            return 1 if "past" in actual_tokens else 2
        if actual_tokens.intersection(expected_tokens):
            return 1
        return 2

    def _content_theme_distance(
        self,
        record: SeedExercise,
        expected: str | None,
    ) -> int:
        if not expected:
            return 0
        if expected != "anime":
            return 1
        haystack = " ".join(
            [
                record.source,
                record.question_text,
                record.explanation,
            ]
        ).lower()
        anime_markers = [
            "anime",
            "manga",
            "episode",
            "character",
            "spoiler",
            "studio",
            "animation",
        ]
        return 0 if any(marker in haystack for marker in anime_markers) else 1
