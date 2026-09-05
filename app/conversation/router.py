import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from typing import Any

from app.config import AppConfig
from app.conversation.schemas import ConversationRoute
from app.intent.interpreter import PracticeIntentInterpreter
from app.language.translation import BilingualTextNormalizer
from app.schemas import (
    ConversationIntent,
    ConversationTurnContext,
    LearningActivity,
    PendingClarification,
    PracticeRequest,
)


class ConversationRouter:
    """Rule-first router for a learner's current conversational intent."""

    PRACTICE_SIGNALS = (
        "practice",
        "luyen",
        "luyen tap",
        "luyen tiep",
        "tao bai",
        "sinh bai",
        "generate exercises",
        "exercise",
        "exercises",
        "quiz",
        "test",
        "trac nghiem",
        "dien khuyet",
        "cau hoi",
        "cau",
    )
    PRACTICE_CONTINUE_SIGNALS = (
        "luyen tiep",
        "tiep tuc luyen",
        "continue practice",
        "bai tiep",
        "de tiep",
        "practice more",
    )
    EXPLICIT_ACTIVITY_SIGNALS = (
        "practice",
        "luyen",
        "luyen tap",
        "luyen tiep",
        "tao bai",
        "sinh bai",
        "generate exercises",
        "exercise",
        "exercises",
        "quiz",
        "test",
        "trac nghiem",
    )
    EXPLAIN_SIGNALS = (
        "giai thich",
        "explain",
        "la gi",
        "dung khi nao",
        "khi nao dung",
        "khac gi",
        "khac nhau",
        "how do i use",
        "when do i use",
        "what is",
        "why do we use",
    )
    EXPLAIN_CONTINUE_SIGNALS = (
        "giai thich tiep",
        "noi tiep",
        "explain more",
        "more detail",
        "continue explaining",
    )
    REVIEW_SIGNALS = (
        "tai sao cau",
        "vi sao cau",
        "cau vua roi",
        "cau nay",
        "dap an",
        "answer",
        "sai",
        "wrong",
        "incorrect",
        "mistake",
        "loi",
    )
    PROGRESS_SIGNALS = (
        "yeu phan nao",
        "dang yeu",
        "diem yeu",
        "ky nang nao thap nhat",
        "skill nao thap nhat",
        "phan nao thap nhat",
        "progress",
        "tien do",
        "mastery",
        "hoc luc",
        "can on phan nao",
    )
    PROFILE_UPDATE_SIGNALS = (
        "tu gio",
        "tu bay gio",
        "lan sau",
        "moi lan",
        "mac dinh",
        "uu tien",
        "kho hon",
        "de hon",
        "harder",
        "easier",
        "kho qua",
        "de qua",
        "toi muon",
        "minh muon",
        "i want",
    )
    CONCEPT_SIGNALS = (
        "past perfect",
        "past simple",
        "present perfect",
        "present simple",
        "present continuous",
        "passive voice",
        "relative clause",
        "conditional",
        "reported speech",
        "preposition",
        "prepositions",
        "vocabulary",
        "thi",
        "ngu phap",
        "tu vung",
    )
    LEARNING_FOCUS_KEYWORDS = {
        "reading": ("doc", "read", "reading"),
        "listening": ("nghe", "listen", "listening"),
        "speaking": ("noi", "speak", "speaking"),
        "writing": ("viet", "write", "writing"),
    }
    LEARNING_FOCUS_SELECTION_MARKERS = (
        "truoc",
        "di",
        "nhe",
        "nha",
        "thoi",
        "first",
        "please",
        "ok",
        "oke",
        "duoc",
        "chon",
    )
    LEARNING_FOCUS_FILLERS = set(LEARNING_FOCUS_SELECTION_MARKERS)

    def __init__(
        self,
        config: AppConfig,
        practice_interpreter: PracticeIntentInterpreter,
    ) -> None:
        self.config = config
        self.practice_interpreter = practice_interpreter
        self.text_normalizer = BilingualTextNormalizer()

    def route(
        self,
        *,
        message: str,
        context: ConversationTurnContext,
    ) -> ConversationRoute:
        normalized = self.text_normalizer.normalize_for_matching(message)

        if context.pending_clarification is not None:
            return self._route_pending_clarification(
                message=message,
                context=context,
            )

        if self._is_review_request(normalized):
            return self._review_route(message, normalized, context)

        if self._is_progress_request(normalized):
            return ConversationRoute(
                intent=ConversationIntent.PROGRESS,
                confidence=0.9,
                source="rule-based",
                reason="Learner asks about weakness, progress, or lowest skill.",
                slots=self._progress_slots(normalized),
            )

        if (
            self._is_profile_update_request(normalized)
            and not self._is_explicit_activity_request(normalized)
        ):
            return ConversationRoute(
                intent=ConversationIntent.PROFILE_UPDATE,
                confidence=0.86,
                source="rule-based",
                reason="Learner is changing future preferences or giving difficulty feedback.",
                slots=self._profile_update_slots(normalized),
            )

        if self._is_explain_request(normalized, context):
            return ConversationRoute(
                intent=ConversationIntent.EXPLAIN,
                confidence=0.88,
                source="rule-based",
                reason="Learner asks for a concept explanation, not a new exercise.",
                slots=self._explain_slots(message, normalized),
            )

        if self._is_practice_request(normalized):
            return self._practice_route(
                message=message,
                context=context,
                reason="Learner asks to create or continue a practice activity.",
            )

        learning_focus = self._learning_focus_selection(normalized, context)
        if learning_focus is not None:
            if learning_focus == "reading":
                return ConversationRoute(
                    intent=ConversationIntent.READING,
                    confidence=0.84,
                    source="rule-based",
                    reason="Learner selected reading as the next learning focus.",
                    slots={
                        "learning_focus": learning_focus,
                        "selection_kind": "learning_focus",
                        "topic": "reading",
                    },
                    assistant_reply=(
                        "Ok, minh chuyen sang doc: doc doan ngan truoc, "
                        "roi tra loi vai cau hoi hieu bai."
                    ),
                )
            if learning_focus == "writing":
                return ConversationRoute(
                    intent=ConversationIntent.WRITING,
                    confidence=0.84,
                    source="rule-based",
                    reason="Learner selected writing as the next learning focus.",
                    slots={
                        "learning_focus": learning_focus,
                        "selection_kind": "learning_focus",
                        "topic": "writing",
                    },
                    assistant_reply=(
                        "Ok, minh mo bai viet ngan de ban viet thu, "
                        "sau do minh se sua theo rubric."
                    ),
                )
            return ConversationRoute(
                intent=ConversationIntent.GENERAL,
                confidence=0.82,
                source="rule-based",
                reason="Learner selected a learning focus from the tutor menu.",
                slots={
                    "learning_focus": learning_focus,
                    "selection_kind": "learning_focus",
                    "planned_activity": learning_focus,
                },
                assistant_reply=(
                    "Minh ghi nhan focus nay, nhung listening/speaking can "
                    "chon audio, STT/TTS truoc khi bat thanh activity that."
                )
                if learning_focus in {"listening", "speaking"}
                else "",
            )

        llm_route = self._try_llm_route(message=message, context=context)
        if llm_route is not None:
            return llm_route

        return ConversationRoute(
            intent=ConversationIntent.GENERAL,
            confidence=0.55,
            source="fallback",
            reason="No deterministic intent rule matched.",
            slots={},
        )

    def _route_pending_clarification(
        self,
        *,
        message: str,
        context: ConversationTurnContext,
    ) -> ConversationRoute:
        pending = context.pending_clarification
        if pending is None:
            raise ValueError("Pending clarification is required.")

        if pending.pending_intent == ConversationIntent.PRACTICE:
            route = self._practice_route(
                message=message,
                context=context,
                reason="Learner answered a pending practice clarification.",
                source="pending-clarification",
                base_slots=pending.collected_slots,
            )
            route.confidence = max(route.confidence, 0.92)
            return route

        return ConversationRoute(
            intent=pending.pending_intent,
            confidence=0.9,
            source="pending-clarification",
            reason=f"Learner answered pending {pending.pending_intent.value} clarification.",
            slots={
                **pending.collected_slots,
                "clarification_answer": message.strip(),
            },
        )

    def _practice_route(
        self,
        *,
        message: str,
        context: ConversationTurnContext,
        reason: str,
        source: str = "rule-based-practice-interpreter",
        base_slots: dict[str, Any] | None = None,
    ) -> ConversationRoute:
        interpretation = self.practice_interpreter.interpret(
            user_id=context.learner_id,
            message=message,
            profile_context=self._profile_context(context),
        )
        request = self._apply_collected_practice_slots(
            interpretation.request,
            base_slots or {},
        )
        slots = {
            **(base_slots or {}),
            **self._practice_slots(request),
        }
        needs_clarification = interpretation.needs_clarification
        missing_fields = self._missing_practice_fields(request)
        if needs_clarification and not missing_fields:
            needs_clarification = False
        clarification_question = (
            interpretation.clarification_question if needs_clarification else None
        )
        clarification = None
        if needs_clarification:
            clarification = PendingClarification(
                pending_intent=ConversationIntent.PRACTICE,
                missing_fields=missing_fields,
                collected_slots=slots,
                question=clarification_question or "",
            )

        return ConversationRoute(
            intent=ConversationIntent.PRACTICE,
            confidence=interpretation.confidence,
            source=source,
            reason=reason,
            slots=slots,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            pending_clarification=clarification,
            assistant_reply=(
                interpretation.assistant_reply
                if not interpretation.needs_clarification or needs_clarification
                else ""
            ),
            practice_request=request,
        )

    def _review_route(
        self,
        message: str,
        normalized: str,
        context: ConversationTurnContext,
    ) -> ConversationRoute:
        activity = self._context_activity(context)
        slots: dict[str, Any] = {
            **self._activity_slots(activity),
            **self._review_slots(normalized),
        }
        needs_clarification = activity is None
        question = None
        pending = None
        if needs_clarification:
            question = (
                "Minh can biet ban muon xem lai bai/cau nao. "
                "Ban gui activity hoac noi ro cau so may nhe?"
            )
            pending = PendingClarification(
                pending_intent=ConversationIntent.REVIEW,
                missing_fields=["activity_id"],
                collected_slots=slots,
                question=question,
            )

        return ConversationRoute(
            intent=ConversationIntent.REVIEW,
            confidence=0.9 if not needs_clarification else 0.76,
            source="rule-based",
            reason="Learner references a previous answer, mistake, or question.",
            slots=slots,
            needs_clarification=needs_clarification,
            clarification_question=question,
            pending_clarification=pending,
        )

    def _try_llm_route(
        self,
        *,
        message: str,
        context: ConversationTurnContext,
    ) -> ConversationRoute | None:
        if not self.config.conversation_router_llm_enabled:
            return None
        if self.config.llm_backend.strip().lower() != "ollama":
            return None

        payload = {
            "message": message,
            "active_intent": (
                context.active_intent.value if context.active_intent else None
            ),
            "active_activity": self._activity_slots(context.active_activity),
            "memory_summary": context.memory_summary[:240],
            "recent_messages": [
                {
                    "role": str(item.get("role") or "")[:20],
                    "content": str(item.get("content") or "")[:180],
                }
                for item in context.recent_messages[-4:]
                if isinstance(item, dict)
            ],
        }
        prompt = (
            "Classify this English tutor chat turn. Return strict JSON only with "
            "intent, confidence, reason, slots, needs_clarification. "
            "Allowed intent values: PRACTICE, READING, WRITING, EXPLAIN, REVIEW, "
            "PROGRESS, PROFILE_UPDATE, GENERAL. Prefer non-PRACTICE unless the learner asks "
            "for an exercise, quiz, test, or continuing practice.\n"
            f"INPUT={json.dumps(payload, ensure_ascii=False)}"
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
                "num_predict": 180,
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
                timeout=self.config.conversation_router_llm_timeout_seconds,
            ) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            raw_content = str(
                response_payload.get("message", {}).get("content", ""),
            ).strip()
            parsed = json.loads(raw_content)
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return None

        intent = self._parse_intent(parsed.get("intent"))
        if intent is None:
            return None
        confidence = self._clamp_float(parsed.get("confidence"), 0.0, 1.0)
        if confidence < 0.55:
            return None
        slots = parsed.get("slots")

        if intent == ConversationIntent.PRACTICE:
            return self._practice_route(
                message=message,
                context=context,
                reason=self._safe_string(parsed.get("reason"))
                or "LLM classified this turn as practice.",
                source="llm-ollama-practice-interpreter",
                base_slots=slots if isinstance(slots, dict) else None,
            )

        return ConversationRoute(
            intent=intent,
            confidence=confidence,
            source="llm-ollama",
            reason=self._safe_string(parsed.get("reason"))
            or "LLM classified ambiguous conversation turn.",
            slots=slots if isinstance(slots, dict) else {},
            needs_clarification=bool(parsed.get("needs_clarification")),
        )

    def _is_practice_request(self, normalized: str) -> bool:
        if self._has_any(normalized, self.PRACTICE_CONTINUE_SIGNALS):
            return True
        if "phan toi yeu" in normalized and "luyen" in normalized:
            return True
        return self._has_any(normalized, self.PRACTICE_SIGNALS)

    def _learning_focus_selection(
        self,
        normalized: str,
        context: ConversationTurnContext,
    ) -> str | None:
        matches = [
            focus
            for focus, keywords in self.LEARNING_FOCUS_KEYWORDS.items()
            if any(self._has_whole_phrase(normalized, keyword) for keyword in keywords)
        ]
        if len(matches) != 1:
            return None

        focus = matches[0]
        tokens = normalized.split()
        if len(tokens) > 6:
            return None

        has_marker = self._has_any(normalized, self.LEARNING_FOCUS_SELECTION_MARKERS)
        if has_marker:
            return focus

        if self._is_compact_learning_focus_choice(normalized, focus):
            return focus

        return None

    def _is_compact_learning_focus_choice(
        self,
        normalized: str,
        focus: str,
    ) -> bool:
        for keyword in self.LEARNING_FOCUS_KEYWORDS[focus]:
            if not self._has_whole_phrase(normalized, keyword):
                continue
            remaining = re.sub(
                rf"(?<!\w){re.escape(keyword)}(?!\w)",
                " ",
                normalized,
                count=1,
            )
            leftovers = set(remaining.split())
            if leftovers.issubset(self.LEARNING_FOCUS_FILLERS):
                return True
        return False

    def _is_explicit_activity_request(self, normalized: str) -> bool:
        return self._has_any(normalized, self.EXPLICIT_ACTIVITY_SIGNALS) or bool(
            re.search(r"\btao\s+(?:cho\s+\w+\s+)?\d{1,2}\s*cau\b", normalized),
        )

    def _is_explain_request(
        self,
        normalized: str,
        context: ConversationTurnContext,
    ) -> bool:
        if self._has_any(normalized, self.EXPLAIN_CONTINUE_SIGNALS):
            return context.active_intent in {
                ConversationIntent.EXPLAIN,
                ConversationIntent.GENERAL,
                None,
            }
        has_explain_signal = self._has_any(normalized, self.EXPLAIN_SIGNALS)
        has_concept = self._has_any(normalized, self.CONCEPT_SIGNALS)
        return has_explain_signal and not self._has_review_reference(normalized) and (
            has_concept or "grammar" in normalized or "ngu phap" in normalized
        )

    def _is_review_request(self, normalized: str) -> bool:
        if "bai vua roi kho qua" in normalized or "bai nay kho qua" in normalized:
            return False
        if "giai thich cau" in normalized or "explain question" in normalized:
            return True
        if self._has_review_reference(normalized) and self._has_any(
            normalized,
            self.REVIEW_SIGNALS,
        ):
            return True
        if re.search(r"\b(question|cau)\s*\d{1,2}\b", normalized) and self._has_any(
            normalized,
            ("sai", "wrong", "incorrect", "mistake", "loi"),
        ):
            return True
        return False

    def _is_progress_request(self, normalized: str) -> bool:
        return self._has_any(normalized, self.PROGRESS_SIGNALS)

    def _is_profile_update_request(self, normalized: str) -> bool:
        if "bai vua roi kho qua" in normalized or "bai nay kho qua" in normalized:
            return True
        if "bai vua roi de qua" in normalized or "bai nay de qua" in normalized:
            return True
        if not self._has_any(normalized, self.PROFILE_UPDATE_SIGNALS):
            return False
        preference_scope = self._has_any(
            normalized,
            ("tu gio", "tu bay gio", "lan sau", "moi lan", "mac dinh", "uu tien"),
        )
        preference_change = self._has_any(
            normalized,
            ("kho hon", "de hon", "harder", "easier"),
        )
        count_preference = re.search(r"\b\d{1,2}\s*(cau|question)", normalized) and (
            "moi lan" in normalized or "mac dinh" in normalized
        )
        return bool(preference_scope or preference_change or count_preference)

    def _has_review_reference(self, normalized: str) -> bool:
        return bool(
            re.search(r"\b(question|cau)\s*\d{1,2}\b", normalized)
            or "cau vua roi" in normalized
            or "cau nay" in normalized
            or "dap an" in normalized
            or "answer" in normalized
            or "vua roi sai" in normalized
        )

    def _profile_context(self, context: ConversationTurnContext) -> dict[str, Any]:
        profile = context.profile
        facts = {}
        if isinstance(context.recent_context.get("chat_extracted_facts"), dict):
            facts = dict(context.recent_context["chat_extracted_facts"])
        return {
            "level": profile.level,
            "goals": profile.goals,
            "preferred_difficulty": profile.preferred_difficulty,
            "preferred_num_questions": profile.preferred_num_questions,
            "weak_topics": [
                topic
                for topic, _score in sorted(
                    profile.weak_topics.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:5]
            ],
            "chat_memory_summary": context.memory_summary,
            "chat_extracted_facts": facts,
            "recent_chat_messages": context.recent_messages[-8:],
        }

    def _practice_slots(self, request: PracticeRequest) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(request).items()
            if key
            in {
                "topic",
                "difficulty",
                "exercise_type",
                "num_questions",
                "target_subtopic",
                "content_theme",
            }
            and value not in (None, "", [])
        }

    def _apply_collected_practice_slots(
        self,
        request: PracticeRequest,
        slots: dict[str, Any],
    ) -> PracticeRequest:
        if not slots:
            return request
        return replace(
            request,
            topic=request.topic or self._safe_optional_string(slots.get("topic")),
            difficulty=request.difficulty
            or self._safe_optional_string(slots.get("difficulty")),
            exercise_type=request.exercise_type
            or self._safe_optional_string(slots.get("exercise_type")),
            num_questions=request.num_questions
            or self._safe_optional_int(slots.get("num_questions")),
            target_subtopic=request.target_subtopic
            or self._safe_optional_string(slots.get("target_subtopic")),
            content_theme=request.content_theme
            or self._safe_optional_string(slots.get("content_theme")),
        )

    def _missing_practice_fields(self, request: PracticeRequest) -> list[str]:
        missing = []
        if not request.topic and not request.target_subtopic:
            missing.append("topic")
        if request.num_questions is None:
            missing.append("num_questions")
        return missing

    def _explain_slots(self, message: str, normalized: str) -> dict[str, Any]:
        concept = self._extract_known_concept(normalized)
        return {
            "concept": concept or self._strip_explain_phrase(message),
        }

    def _review_slots(self, normalized: str) -> dict[str, Any]:
        slots: dict[str, Any] = {}
        question_number = self._extract_question_number(normalized)
        if question_number is not None:
            slots["question_number"] = question_number
        if self._has_any(normalized, ("sai", "wrong", "incorrect", "mistake", "loi")):
            slots["review_focus"] = "mistake"
        elif self._has_any(normalized, ("dap an", "answer")):
            slots["review_focus"] = "answer"
        else:
            slots["review_focus"] = "latest_question"
        return slots

    def _progress_slots(self, normalized: str) -> dict[str, Any]:
        if self._has_any(normalized, ("thap nhat", "lowest")):
            return {"metric": "lowest_skill"}
        return {"metric": "weak_areas"}

    def _profile_update_slots(self, normalized: str) -> dict[str, Any]:
        slots: dict[str, Any] = {}
        count = self._extract_num_questions(normalized)
        if count is not None:
            slots["preferred_num_questions"] = count
        if self._has_any(normalized, ("kho hon", "harder")):
            slots["difficulty_delta"] = "harder"
            slots["preferred_difficulty"] = "hard"
        elif self._has_any(normalized, ("de hon", "easier")):
            slots["difficulty_delta"] = "easier"
            slots["preferred_difficulty"] = "easy"
        elif self._has_any(normalized, ("kho qua", "too hard")):
            slots["difficulty_feedback"] = "too_hard"
            slots["difficulty_delta"] = "easier"
        elif self._has_any(normalized, ("de qua", "too easy")):
            slots["difficulty_feedback"] = "too_easy"
            slots["difficulty_delta"] = "harder"
        return slots

    def _activity_slots(self, activity: LearningActivity | None) -> dict[str, Any]:
        if activity is None:
            return {}
        return {
            "activity_id": activity.activity_id,
            "activity_type": activity.type.value,
            "activity_status": activity.status.value,
            "generation_run_id": activity.generation_run_id,
            "session_code": activity.session_code,
        }

    def _context_activity(
        self,
        context: ConversationTurnContext,
    ) -> LearningActivity | None:
        if context.active_activity is not None:
            return context.active_activity
        latest = context.recent_context.get("latest_activity")
        if isinstance(latest, LearningActivity):
            return latest
        return None

    def _extract_known_concept(self, normalized: str) -> str | None:
        for concept in self.CONCEPT_SIGNALS:
            if concept in normalized:
                return concept.replace(" ", "_")
        return None

    def _strip_explain_phrase(self, message: str) -> str:
        normalized = " ".join(message.strip().split())
        for phrase in ("giai thich", "giải thích", "explain"):
            normalized = re.sub(
                re.escape(phrase),
                "",
                normalized,
                flags=re.IGNORECASE,
            ).strip()
        return normalized

    def _extract_question_number(self, normalized: str) -> int | None:
        match = re.search(r"\b(?:question|cau)(?:\s+hoi)?\s*(\d{1,2})\b", normalized)
        if match:
            return int(match.group(1))
        return None

    def _extract_num_questions(self, normalized: str) -> int | None:
        match = re.search(r"\b(\d{1,2})\s*(?:cau|question|questions)\b", normalized)
        if not match:
            return None
        return max(1, min(int(match.group(1)), 20))

    def _parse_intent(self, value: object) -> ConversationIntent | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        try:
            return ConversationIntent(normalized)
        except ValueError:
            return None

    def _has_any(self, normalized: str, phrases: tuple[str, ...]) -> bool:
        return any(phrase in normalized for phrase in phrases)

    def _has_whole_phrase(self, normalized: str, phrase: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized))

    def _safe_string(self, value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    def _safe_optional_string(self, value: object) -> str | None:
        parsed = self._safe_string(value)
        return parsed or None

    def _safe_optional_int(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return max(1, min(value, 20))
        if isinstance(value, str):
            match = re.search(r"\b\d{1,2}\b", value)
            if match:
                return max(1, min(int(match.group(0)), 20))
        return None

    def _clamp_float(self, value: object, minimum: float, maximum: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(minimum, min(parsed, maximum))
