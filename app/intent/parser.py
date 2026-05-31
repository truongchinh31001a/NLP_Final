import re

from app.config import AppConfig
from app.schemas import PracticeRequest


class IntentParser:
    """Rule-based parser for the first baseline."""

    TOPIC_KEYWORDS = {
        "passive voice": "passive_voice",
        "passive": "passive_voice",
        "cau bi dong": "passive_voice",
        "bi dong": "passive_voice",
        "relative clause": "relative_clause",
        "menh de quan he": "relative_clause",
        "conditional": "conditional_sentence",
        "cau dieu kien": "conditional_sentence",
        "vocabulary": "vocabulary",
        "tu vung": "vocabulary",
        "travel": "travel_vocabulary",
        "grammar": "grammar",
    }

    DIFFICULTY_KEYWORDS = {
        "de": "easy",
        "easy": "easy",
        "co ban": "easy",
        "trung binh": "medium",
        "medium": "medium",
        "vua": "medium",
        "kho": "hard",
        "hard": "hard",
        "nang cao": "hard",
    }

    EXERCISE_TYPE_KEYWORDS = {
        "mcq": "mcq",
        "trac nghiem": "mcq",
        "multiple choice": "mcq",
        "fill in the blank": "fill_blank",
        "dien khuyet": "fill_blank",
        "fill blank": "fill_blank",
        "vocabulary": "vocabulary_mcq",
        "grammar": "grammar_mcq",
    }

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def parse(self, user_id: str, raw_text: str) -> PracticeRequest:
        normalized_text = self._normalize(raw_text)
        return PracticeRequest(
            user_id=user_id,
            raw_text=raw_text,
            topic=self._extract_keyword(normalized_text, self.TOPIC_KEYWORDS),
            difficulty=self._extract_keyword(normalized_text, self.DIFFICULTY_KEYWORDS),
            exercise_type=self._extract_exercise_type(normalized_text),
            num_questions=self._extract_num_questions(normalized_text),
        )

    def _normalize(self, text: str) -> str:
        return " ".join(text.strip().lower().split())

    def _extract_keyword(self, text: str, keyword_map: dict[str, str]) -> str | None:
        for keyword, value in keyword_map.items():
            if keyword in text:
                return value
        return None

    def _extract_exercise_type(self, text: str) -> str | None:
        for keyword, value in self.EXERCISE_TYPE_KEYWORDS.items():
            if keyword in text:
                return value

        if "tu vung" in text:
            return "vocabulary_mcq"
        if "ngu phap" in text or "grammar" in text:
            return "grammar_mcq"

        return None

    def _extract_num_questions(self, text: str) -> int | None:
        match = re.search(r"(\d+)\s*(cau|question|questions)", text)
        if match:
            return int(match.group(1))

        bare_number = re.search(r"\b(\d{1,2})\b", text)
        if bare_number:
            return int(bare_number.group(1))

        return None
