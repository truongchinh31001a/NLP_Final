import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.config import AppConfig
from app.intent.parser import IntentParser
from app.language.translation import BilingualTextNormalizer
from app.schemas import PracticeRequest


SUPPORTED_TOPICS = {
    "tenses",
    "passive_voice",
    "relative_clause",
    "conditional_sentence",
    "reported_speech",
    "prepositions",
    "vocabulary",
    "travel_vocabulary",
}

SUPPORTED_DIFFICULTIES = {"easy", "medium", "hard"}
SUPPORTED_EXERCISE_TYPES = {"grammar_mcq", "vocabulary_mcq", "fill_blank", "mcq"}
SUPPORTED_CONTENT_THEMES = {"anime"}


@dataclass(slots=True)
class PracticeIntentInterpretation:
    request: PracticeRequest
    assistant_reply: str
    needs_clarification: bool
    clarification_question: str | None
    confidence: float
    source: str
    raw_llm_response: str = ""


@dataclass(slots=True)
class _LLMPracticeIntent:
    request: PracticeRequest | None = None
    assistant_reply: str = ""
    needs_clarification: bool | None = None
    clarification_question: str | None = None
    confidence: float = 0.0
    raw_response: str = ""


class PracticeIntentInterpreter:
    """Hybrid intent interpreter for natural practice requests."""

    TOPIC_ALIASES = {
        "grammar": "tenses",
        "ngu_phap": "tenses",
        "thi": "tenses",
        "cac_thi": "tenses",
        "tense": "tenses",
        "tenses": "tenses",
        "past": "tenses",
        "past_tense": "tenses",
        "simple_past": "tenses",
        "passive": "passive_voice",
        "passive_voice": "passive_voice",
        "bi_dong": "passive_voice",
        "relative": "relative_clause",
        "relative_clause": "relative_clause",
        "menh_de_quan_he": "relative_clause",
        "conditional": "conditional_sentence",
        "conditional_sentence": "conditional_sentence",
        "cau_dieu_kien": "conditional_sentence",
        "reported": "reported_speech",
        "reported_speech": "reported_speech",
        "indirect_speech": "reported_speech",
        "gian_tiep": "reported_speech",
        "cau_gian_tiep": "reported_speech",
        "tuong_thuat": "reported_speech",
        "preposition": "prepositions",
        "prepositions": "prepositions",
        "gioi_tu": "prepositions",
        "vocab": "vocabulary",
        "vocabulary": "vocabulary",
        "tu_vung": "vocabulary",
        "travel": "travel_vocabulary",
        "travel_vocab": "travel_vocabulary",
        "travel_vocabulary": "travel_vocabulary",
        "du_lich": "travel_vocabulary",
        "tu_vung_du_lich": "travel_vocabulary",
    }

    CONTENT_THEME_ALIASES = {
        "anime": "anime",
        "manga": "anime",
        "otaku": "anime",
        "episode": "anime",
        "anime_episode": "anime",
        "anime_character": "anime",
        "nhan_vat_anime": "anime",
        "chu_de_anime": "anime",
        "bo_anime": "anime",
    }

    SUBTOPIC_ALIASES = {
        "past": "past_simple_finished_time",
        "past_tense": "past_simple_finished_time",
        "simple_past": "past_simple_finished_time",
        "past_simple": "past_simple_finished_time",
        "thi_qua_khu": "past_simple_finished_time",
        "qua_khu": "past_simple_finished_time",
        "past_continuous": "past_continuous_interrupted_action",
        "past_progressive": "past_continuous_interrupted_action",
        "past_perfect": "past_perfect_sequence",
        "present_simple": "present_simple_habits",
        "present_continuous": "present_continuous_now",
        "present_progressive": "present_continuous_now",
        "present_perfect": "present_perfect_experience",
        "future": "future_will_prediction",
        "future_tense": "future_will_prediction",
        "will_future": "future_will_prediction",
        "present_passive": "present_simple_passive",
        "past_passive": "past_simple_passive",
        "future_passive": "future_passive",
        "zero_conditional": "zero_conditional",
        "first_conditional": "first_conditional",
        "second_conditional": "second_conditional",
        "third_conditional": "third_conditional",
        "reported_question": "reported_yes_no_question",
        "reported_questions": "reported_yes_no_question",
        "reported_statement": "statement_backshift",
        "reported_statements": "statement_backshift",
        "preposition_of_time": "prepositions_of_time",
        "prepositions_of_time": "prepositions_of_time",
        "preposition_of_place": "prepositions_of_place",
        "prepositions_of_place": "prepositions_of_place",
        "airport": "airport_vocabulary",
        "hotel": "hotel_vocabulary",
        "transport": "transport_vocabulary",
    }

    OUT_OF_SCOPE_SIGNALS = [
        "pronunciation",
        "phat am",
        "listening",
        "nghe",
        "speaking",
        "noi chuyen",
        "writing essay",
        "viet luan",
        "ielts writing",
        "toeic listening",
        "translate paragraph",
        "dich doan",
    ]

    PRACTICE_SIGNALS = [
        "tao",
        "luyen",
        "bai",
        "cau",
        "question",
        "exercise",
        "practice",
        "quiz",
        "test",
        "kiem tra",
    ]

    CONTINUE_SIGNALS = [
        "luyen tiep",
        "tiep tuc",
        "continue",
        "tiep theo",
        "bai tiep",
        "de tiep",
    ]

    def __init__(self, config: AppConfig, parser: IntentParser) -> None:
        self.config = config
        self.parser = parser
        self.text_normalizer = BilingualTextNormalizer()

    def interpret(
        self,
        *,
        user_id: str,
        message: str,
        profile_context: dict[str, Any] | None = None,
    ) -> PracticeIntentInterpretation:
        profile_context = profile_context or {}
        rule_request = self.parser.parse(user_id=user_id, raw_text=message)

        llm = _LLMPracticeIntent()
        if self._should_try_llm(rule_request, profile_context):
            llm = self._try_llm_interpret(
                user_id=user_id,
                message=message,
                rule_request=rule_request,
                profile_context=profile_context,
            )

        request = self._merge_requests(rule_request, llm.request)
        request = self._apply_memory_preferences(
            request=request,
            message=message,
            profile_context=profile_context,
        )
        request = self._complete_implied_fields(request)
        needs_clarification, clarification_question = self._clarification_decision(
            request=request,
            message=message,
            profile_context=profile_context,
            llm=llm,
        )

        assistant_reply = (
            clarification_question
            if needs_clarification
            else llm.assistant_reply or self._build_acknowledgement(request)
        )
        source = self._source(rule_request=rule_request, llm=llm)

        return PracticeIntentInterpretation(
            request=request,
            assistant_reply=assistant_reply,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            confidence=self._final_confidence(
                request=request,
                llm=llm,
                needs_clarification=needs_clarification,
            ),
            source=source,
            raw_llm_response=llm.raw_response[:4000],
        )

    def _try_llm_interpret(
        self,
        *,
        user_id: str,
        message: str,
        rule_request: PracticeRequest,
        profile_context: dict[str, Any],
    ) -> _LLMPracticeIntent:
        if self.config.llm_backend.strip().lower() != "ollama":
            return _LLMPracticeIntent()

        prompt_payload = {
            "message": message,
            "rule": self._request_to_dict(rule_request),
            "memory": self._compact_profile_context(profile_context),
        }
        prompt = (
            "Extract English practice intent from Vietnamese/English chat. "
            "Return strict compact JSON only with keys: topic,target_subtopic,difficulty,"
            "exercise_type,num_questions,content_theme,needs_clarification,"
            "clarification_question,assistant_reply,confidence.\n"
            f"Allowed topics={','.join(sorted(SUPPORTED_TOPICS))}. "
            f"Allowed difficulty={','.join(sorted(SUPPORTED_DIFFICULTIES))}. "
            f"Allowed exercise_type={','.join(sorted(SUPPORTED_EXERCISE_TYPES))}. "
            "Allowed content_theme=anime.\n"
            "Current message wins. Use rule as baseline. Use memory only to fill missing "
            "details or stable preferences. If memory.preferred_content_theme or "
            "memory.content_themes exists and current message does not change/reject theme, "
            "copy it to content_theme. "
            "Anime/manga/otaku means content_theme=anime, never topic. "
            "If unclear, ask one short Vietnamese clarification. Use null for unknown. "
            "num_questions 1-20, confidence 0-1.\n"
            f"INPUT={json.dumps(prompt_payload, ensure_ascii=False)}"
        )
        request_payload = {
            "model": self.config.ollama_model,
            "messages": [
                {"role": "system", "content": "Return strict JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_ctx": 2048,
                "num_predict": 220,
            },
        }

        request = urllib.request.Request(
            f"{self.config.ollama_base_url.rstrip('/')}/api/chat",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.practice_intent_llm_timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return _LLMPracticeIntent()

        raw_content = str(payload.get("message", {}).get("content", "")).strip()
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            return _LLMPracticeIntent(raw_response=raw_content)

        request_patch = PracticeRequest(
            user_id=user_id,
            raw_text=message,
            processing_text=rule_request.processing_text,
            detected_language=rule_request.detected_language,
            topic=self._normalize_topic(parsed.get("topic")),
            difficulty=self._normalize_difficulty(parsed.get("difficulty")),
            exercise_type=self._normalize_exercise_type(parsed.get("exercise_type")),
            num_questions=self._normalize_num_questions(parsed.get("num_questions")),
            target_subtopic=self._normalize_subtopic(parsed.get("target_subtopic")),
            content_theme=self._normalize_content_theme(
                parsed.get("content_theme"),
            )
            or self._normalize_content_theme(parsed.get("topic")),
        )
        confidence = self._clamp_float(parsed.get("confidence"), 0.0, 1.0)
        if confidence < 0.25:
            request_patch = None

        return _LLMPracticeIntent(
            request=request_patch,
            assistant_reply=self._safe_string(parsed.get("assistant_reply")),
            needs_clarification=self._safe_bool(parsed.get("needs_clarification")),
            clarification_question=self._safe_string(
                parsed.get("clarification_question"),
            )
            or None,
            confidence=confidence,
            raw_response=raw_content,
        )

    def _merge_requests(
        self,
        base: PracticeRequest,
        patch: PracticeRequest | None,
    ) -> PracticeRequest:
        if patch is None:
            return base
        return PracticeRequest(
            user_id=base.user_id,
            raw_text=base.raw_text,
            processing_text=base.processing_text,
            detected_language=base.detected_language,
            topic=base.topic or patch.topic,
            difficulty=base.difficulty or patch.difficulty,
            exercise_type=base.exercise_type or patch.exercise_type,
            num_questions=base.num_questions or patch.num_questions,
            target_subtopic=base.target_subtopic or patch.target_subtopic,
            content_theme=base.content_theme or patch.content_theme,
        )

    def _apply_memory_preferences(
        self,
        *,
        request: PracticeRequest,
        message: str,
        profile_context: dict[str, Any],
    ) -> PracticeRequest:
        if self._rejects_memory_theme(message):
            return self._with_content_theme(request, None)
        if request.content_theme:
            return request

        content_theme = self._memory_content_theme(profile_context)
        if not content_theme:
            return request

        return self._with_content_theme(request, content_theme)

    def _with_content_theme(
        self,
        request: PracticeRequest,
        content_theme: str | None,
    ) -> PracticeRequest:
        return PracticeRequest(
            user_id=request.user_id,
            raw_text=request.raw_text,
            processing_text=request.processing_text,
            detected_language=request.detected_language,
            topic=request.topic,
            difficulty=request.difficulty,
            exercise_type=request.exercise_type,
            num_questions=request.num_questions,
            target_subtopic=request.target_subtopic,
            content_theme=content_theme,
        )

    def _complete_implied_fields(self, request: PracticeRequest) -> PracticeRequest:
        topic = request.topic
        exercise_type = request.exercise_type
        if topic and exercise_type is None:
            exercise_type = "vocabulary_mcq" if "vocabulary" in topic else "grammar_mcq"
        if exercise_type == "vocabulary_mcq" and topic is None:
            topic = "vocabulary"
        if request.target_subtopic and topic is None:
            topic = self._topic_from_subtopic(request.target_subtopic)
        return PracticeRequest(
            user_id=request.user_id,
            raw_text=request.raw_text,
            processing_text=request.processing_text,
            detected_language=request.detected_language,
            topic=topic,
            difficulty=request.difficulty,
            exercise_type=exercise_type,
            num_questions=request.num_questions,
            target_subtopic=request.target_subtopic,
            content_theme=request.content_theme,
        )

    def _clarification_decision(
        self,
        *,
        request: PracticeRequest,
        message: str,
        profile_context: dict[str, Any],
        llm: _LLMPracticeIntent,
    ) -> tuple[bool, str | None]:
        normalized = self.text_normalizer.normalize_for_matching(message)
        question = llm.clarification_question or self._default_clarification_question()

        if self._has_out_of_scope_signal(normalized) and not self._has_specific_focus(
            request,
        ):
            return True, (
                "Hien minh dang manh ve ngu phap va tu vung. "
                "Ban muon doi sang thi, bi dong, gioi tu, cau dieu kien hay tu vung?"
            )

        if llm.needs_clarification is True and not self._has_specific_focus(request):
            return True, question

        if self._has_specific_focus(request):
            return False, None

        if self._is_continue_signal(normalized) or self._profile_has_learning_focus(
            profile_context,
        ):
            return False, None

        if not self._has_practice_signal(normalized):
            return True, question

        if request.num_questions or request.difficulty or request.exercise_type:
            return True, question

        return True, question

    def _has_specific_focus(self, request: PracticeRequest) -> bool:
        return bool(request.topic or request.target_subtopic)

    def _should_try_llm(
        self,
        request: PracticeRequest,
        profile_context: dict[str, Any],
    ) -> bool:
        if self.config.llm_backend.strip().lower() != "ollama":
            return False
        if self._has_chat_context(profile_context):
            return True
        if not self._has_specific_focus(request):
            return True
        return not (request.content_theme and request.target_subtopic)

    def _has_chat_context(self, profile_context: dict[str, Any]) -> bool:
        if profile_context.get("chat_memory_summary"):
            return True
        facts = profile_context.get("chat_extracted_facts")
        if isinstance(facts, dict) and bool(facts):
            return True
        messages = profile_context.get("recent_chat_messages")
        if not isinstance(messages, list):
            return False
        return any(
            isinstance(message, dict)
            and bool(str(message.get("content") or "").strip())
            for message in messages
        )

    def _memory_content_theme(self, profile_context: dict[str, Any]) -> str | None:
        facts = profile_context.get("chat_extracted_facts")
        if not isinstance(facts, dict):
            return None

        preferred = self._normalize_content_theme(facts.get("preferred_content_theme"))
        if preferred:
            return preferred

        content_themes = facts.get("content_themes")
        if isinstance(content_themes, list):
            for theme in content_themes:
                normalized = self._normalize_content_theme(theme)
                if normalized:
                    return normalized
        return None

    def _rejects_memory_theme(self, message: str) -> bool:
        normalized = self.text_normalizer.normalize_for_matching(message)
        if any(
            signal in normalized
            for signal in [
                "khong anime",
                "khong can anime",
                "bo anime",
                "no anime",
                "not anime",
                "without anime",
            ]
        ):
            return True
        return ("chu de" in normalized or "theme" in normalized) and "anime" not in normalized

    def _compact_profile_context(
        self,
        profile_context: dict[str, Any],
    ) -> dict[str, Any]:
        fact_keys = [
            "display_name",
            "level",
            "goals",
            "weak_topics",
            "recent_topics",
            "last_topic_requested",
            "preferred_difficulty",
            "preferred_num_questions",
            "preferred_content_theme",
            "content_themes",
            "last_user_request",
        ]
        facts = profile_context.get("chat_extracted_facts")
        compact_facts = {}
        if isinstance(facts, dict):
            compact_facts = {
                key: facts[key]
                for key in fact_keys
                if facts.get(key) not in (None, "", [])
            }

        messages = profile_context.get("recent_chat_messages")
        compact_messages: list[dict[str, str]] = []
        if isinstance(messages, list):
            compact_messages = [
                {
                    "role": str(message.get("role") or "")[:20],
                    "content": str(message.get("content") or "")[:160],
                }
                for message in messages[-3:]
                if isinstance(message, dict)
                and str(message.get("content") or "").strip()
            ]

        return {
            "level": profile_context.get("level"),
            "goals": profile_context.get("goals") or [],
            "preferred_difficulty": profile_context.get("preferred_difficulty"),
            "preferred_num_questions": profile_context.get("preferred_num_questions"),
            "preferred_content_theme": compact_facts.get("preferred_content_theme"),
            "content_themes": compact_facts.get("content_themes") or [],
            "weak_topics": profile_context.get("weak_topics") or [],
            "chat_memory_summary": str(
                profile_context.get("chat_memory_summary") or "",
            )[:240],
            "chat_extracted_facts": compact_facts,
            "recent_chat_messages": compact_messages,
        }

    def _has_out_of_scope_signal(self, normalized: str) -> bool:
        return any(signal in normalized for signal in self.OUT_OF_SCOPE_SIGNALS)

    def _has_practice_signal(self, normalized: str) -> bool:
        return any(signal in normalized for signal in self.PRACTICE_SIGNALS)

    def _is_continue_signal(self, normalized: str) -> bool:
        return any(signal in normalized for signal in self.CONTINUE_SIGNALS)

    def _profile_has_learning_focus(self, profile_context: dict[str, Any]) -> bool:
        weak_topics = profile_context.get("weak_topics")
        goals = profile_context.get("goals")
        return bool(weak_topics or goals)

    def _default_clarification_question(self) -> str:
        return (
            "Minh chua ro ban muon luyen phan nao. Ban chon giup minh mot huong: "
            "thi/ngu phap, bi dong, menh de quan he, cau dieu kien, cau gian tiep, "
            "gioi tu hay tu vung?"
        )

    def _build_acknowledgement(self, request: PracticeRequest) -> str:
        if request.topic:
            count = request.num_questions or self.config.default_num_questions
            theme = (
                f" theo chu de {self._theme_label(request.content_theme)}"
                if request.content_theme
                else ""
            )
            return f"Minh hieu roi: tao {count} cau ve {self._topic_label(request.topic)}{theme}."
        return "Minh se dua vao ho so hoc cua ban de chon bai phu hop."

    def _source(
        self,
        *,
        rule_request: PracticeRequest,
        llm: _LLMPracticeIntent,
    ) -> str:
        if llm.request is not None or llm.assistant_reply or llm.raw_response:
            return "hybrid-ollama"
        if self._has_specific_focus(rule_request):
            return "rule-based"
        return "rule-based-clarify"

    def _final_confidence(
        self,
        *,
        request: PracticeRequest,
        llm: _LLMPracticeIntent,
        needs_clarification: bool,
    ) -> float:
        if needs_clarification:
            return max(llm.confidence, 0.55)
        if llm.confidence:
            return max(0.55, min(llm.confidence, 1.0))
        if self._has_specific_focus(request):
            return 0.9
        return 0.6

    def _normalize_topic(self, value: object) -> str | None:
        code = self._normalize_code(value)
        if not code:
            return None
        topic = self.TOPIC_ALIASES.get(code, code)
        return topic if topic in SUPPORTED_TOPICS else None

    def _normalize_difficulty(self, value: object) -> str | None:
        code = self._normalize_code(value)
        return code if code in SUPPORTED_DIFFICULTIES else None

    def _normalize_exercise_type(self, value: object) -> str | None:
        code = self._normalize_code(value)
        aliases = {
            "grammar": "grammar_mcq",
            "grammar_mcq": "grammar_mcq",
            "vocab": "vocabulary_mcq",
            "vocabulary": "vocabulary_mcq",
            "vocabulary_mcq": "vocabulary_mcq",
            "multiple_choice": "mcq",
            "mcq": "mcq",
            "fill_blank": "fill_blank",
            "fill_in_the_blank": "fill_blank",
            "dien_khuyet": "fill_blank",
        }
        exercise_type = aliases.get(code, code)
        return exercise_type if exercise_type in SUPPORTED_EXERCISE_TYPES else None

    def _normalize_num_questions(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return min(max(value, 1), 20)
        if isinstance(value, float) and value.is_integer():
            return min(max(int(value), 1), 20)
        if isinstance(value, str):
            match = re.search(r"\b\d{1,2}\b", value)
            if match:
                return min(max(int(match.group(0)), 1), 20)
        return None

    def _normalize_subtopic(self, value: object) -> str | None:
        code = self._normalize_code(value)
        if not code:
            return None
        subtopic = self.SUBTOPIC_ALIASES.get(code, code)
        if re.fullmatch(r"[a-z0-9_]{2,80}", subtopic):
            return subtopic
        return None

    def _normalize_content_theme(self, value: object) -> str | None:
        code = self._normalize_code(value)
        if not code:
            return None
        theme = self.CONTENT_THEME_ALIASES.get(code, code)
        return theme if theme in SUPPORTED_CONTENT_THEMES else None

    def _topic_from_subtopic(self, subtopic: str) -> str:
        if "passive" in subtopic:
            return "passive_voice"
        if "conditional" in subtopic or subtopic in {"unless", "mixed_conditional"}:
            return "conditional_sentence"
        if "reported" in subtopic or "backshift" in subtopic:
            return "reported_speech"
        if "preposition" in subtopic or subtopic in {"time_at", "time_on", "time_in"}:
            return "prepositions"
        if "vocabulary" in subtopic or subtopic in {"airport", "hotel", "transport"}:
            return "travel_vocabulary"
        return "tenses"

    def _topic_label(self, topic: str) -> str:
        labels = {
            "tenses": "thi va ngu phap",
            "passive_voice": "cau bi dong",
            "relative_clause": "menh de quan he",
            "conditional_sentence": "cau dieu kien",
            "reported_speech": "cau gian tiep",
            "prepositions": "gioi tu",
            "vocabulary": "tu vung",
            "travel_vocabulary": "tu vung du lich",
        }
        return labels.get(topic, topic.replace("_", " "))

    def _theme_label(self, theme: str | None) -> str:
        labels = {
            "anime": "anime",
        }
        return labels.get(theme or "", theme or "")

    def _request_to_dict(self, request: PracticeRequest) -> dict[str, Any]:
        return {
            "topic": request.topic,
            "difficulty": request.difficulty,
            "exercise_type": request.exercise_type,
            "num_questions": request.num_questions,
            "target_subtopic": request.target_subtopic,
            "content_theme": request.content_theme,
            "detected_language": request.detected_language,
            "processing_text": request.processing_text,
        }

    def _normalize_code(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        normalized = self.text_normalizer.normalize_for_matching(value)
        return normalized.replace(" ", "_").replace("-", "_")

    def _safe_string(self, value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    def _safe_bool(self, value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
        return None

    def _clamp_float(self, value: object, minimum: float, maximum: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(minimum, min(parsed, maximum))
