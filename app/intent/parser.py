import re

from app.config import AppConfig
from app.language.translation import BilingualTextNormalizer
from app.schemas import PracticeRequest


class IntentParser:
    """Rule-based parser for the first baseline."""

    CONTENT_THEME_KEYWORDS = {
        "anime": "anime",
        "manga": "anime",
        "otaku": "anime",
        "episode": "anime",
        "anime episode": "anime",
        "anime character": "anime",
        "nhan vat anime": "anime",
        "chu de anime": "anime",
        "bo anime": "anime",
    }

    TOPIC_KEYWORDS = {
        "modal passive": "passive_voice",
        "passive modal": "passive_voice",
        "passive voice modal": "passive_voice",
        "dong tu khuyet thieu bi dong": "passive_voice",
        "khuyet thieu bi dong": "passive_voice",
        "passive voice": "passive_voice",
        "passive": "passive_voice",
        "cau bi dong": "passive_voice",
        "bi dong": "passive_voice",
        "relative clause": "relative_clause",
        "menh de quan he": "relative_clause",
        "conditional": "conditional_sentence",
        "cau dieu kien": "conditional_sentence",
        "reported speech": "reported_speech",
        "reported": "reported_speech",
        "indirect speech": "reported_speech",
        "cau gian tiep": "reported_speech",
        "gian tiep": "reported_speech",
        "tuong thuat": "reported_speech",
        "preposition": "prepositions",
        "prepositions": "prepositions",
        "gioi tu": "prepositions",
        "travel vocabulary": "travel_vocabulary",
        "travel vocab": "travel_vocabulary",
        "travel": "travel_vocabulary",
        "vocabulary": "vocabulary",
        "tu vung": "vocabulary",
        "past perfect": "tenses",
        "past continuous": "tenses",
        "past simple": "tenses",
        "past tense": "tenses",
        "yesterday": "tenses",
        "hom qua": "tenses",
        "last week": "tenses",
        "tuan truoc": "tenses",
        "last month": "tenses",
        "thang truoc": "tenses",
        "thi qua khu": "tenses",
        "qua khu": "tenses",
        "tense": "tenses",
        "tenses": "tenses",
        "cac thi": "tenses",
        "thi hien tai": "tenses",
        "thi tuong lai": "tenses",
        "grammar": "tenses",
    }

    SUBTOPIC_KEYWORDS = {
        "modal passive": "modal_passive",
        "passive modal": "modal_passive",
        "passive voice modal": "modal_passive",
        "dong tu khuyet thieu bi dong": "modal_passive",
        "khuyet thieu bi dong": "modal_passive",
        "past perfect": "past_perfect_sequence",
        "past continuous": "past_continuous_interrupted_action",
        "past simple": "past_simple_finished_time",
        "past tense": "past_simple_finished_time",
        "yesterday": "past_simple_finished_time",
        "hom qua": "past_simple_finished_time",
        "last week": "past_simple_finished_time",
        "tuan truoc": "past_simple_finished_time",
        "last month": "past_simple_finished_time",
        "thang truoc": "past_simple_finished_time",
        "thi qua khu": "past_simple_finished_time",
        "qua khu": "past_simple_finished_time",
        "present perfect": "present_perfect_experience",
        "present continuous": "present_continuous_now",
        "present simple": "present_simple_habits",
        "thi hien tai": "present_simple_habits",
        "future tense": "future_will_prediction",
        "thi tuong lai": "future_will_prediction",
        "present passive": "present_simple_passive",
        "past passive": "past_simple_passive",
        "future passive": "future_passive",
        "first conditional": "first_conditional",
        "second conditional": "second_conditional",
        "third conditional": "third_conditional",
        "zero conditional": "zero_conditional",
        "reported question": "reported_yes_no_question",
        "reported speech": "reported_speech_overview",
        "prepositions of time": "prepositions_of_time",
        "preposition of time": "prepositions_of_time",
        "prepositions of place": "prepositions_of_place",
        "preposition of place": "prepositions_of_place",
    }

    DIFFICULTY_KEYWORDS = {
        "easy": "easy",
        "co ban": "easy",
        "beginner": "easy",
        "basic": "easy",
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
        self.text_normalizer = BilingualTextNormalizer()

    def parse(self, user_id: str, raw_text: str) -> PracticeRequest:
        processing_text = self.text_normalizer.request_to_processing_text(raw_text)
        return PracticeRequest(
            user_id=user_id,
            raw_text=raw_text,
            processing_text=processing_text,
            detected_language=self.text_normalizer.detect_language(raw_text),
            topic=self._extract_keyword(processing_text, self.TOPIC_KEYWORDS),
            difficulty=self._extract_keyword(processing_text, self.DIFFICULTY_KEYWORDS),
            exercise_type=self._extract_exercise_type(processing_text),
            num_questions=self._extract_num_questions(processing_text),
            target_subtopic=self._extract_keyword(
                processing_text,
                self.SUBTOPIC_KEYWORDS,
            ),
            content_theme=self._extract_keyword(
                processing_text,
                self.CONTENT_THEME_KEYWORDS,
            ),
        )

    def _extract_keyword(self, text: str, keyword_map: dict[str, str]) -> str | None:
        for keyword, value in keyword_map.items():
            if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text):
                return value
        return None

    def _extract_exercise_type(self, text: str) -> str | None:
        for keyword, value in self.EXERCISE_TYPE_KEYWORDS.items():
            if keyword in text:
                return value

        if "tu vung" in text:
            return "vocabulary_mcq"
        if self._extract_keyword(text, self.SUBTOPIC_KEYWORDS):
            return "grammar_mcq"
        if (
            "ngu phap" in text
            or "grammar" in text
            or "tense" in text
            or "thi qua khu" in text
            or "qua khu" in text
            or "reported" in text
            or "gian tiep" in text
            or "modal" in text
            or "khuyet thieu" in text
            or "preposition" in text
            or "gioi tu" in text
        ):
            return "grammar_mcq"

        return None

    def _extract_num_questions(self, text: str) -> int | None:
        match = re.search(
            r"(\d+)\s*(?:\w+\s+){0,3}(cau|question|questions|exercise|exercises)",
            text,
        )
        if match:
            return int(match.group(1))

        bare_number = re.search(r"\b(\d{1,2})\b", text)
        if bare_number:
            return int(bare_number.group(1))

        return None
