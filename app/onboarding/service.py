import json
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from app.config import AppConfig


ONBOARDING_STEPS = [
    {
        "key": "displayName",
        "question": "Mình gọi bạn là gì cho thân thiện nhỉ? Tên thật hay nickname đều được.",
    },
    {
        "key": "level",
        "question": "Bạn đang ở mức nào? Nếu chưa chắc, cứ chọn mức gần nhất, mình sẽ tự điều chỉnh sau vài bài.",
    },
    {
        "key": "goals",
        "question": "Bạn học tiếng Anh để làm gì nhiều nhất lúc này? Ví dụ: giao tiếp, TOEIC, ngữ pháp, từ vựng, đi du lịch.",
    },
    {
        "key": "weakTopics",
        "question": "Phần nào làm bạn hay khựng nhất? Bạn có thể nói nhiều ý, ví dụ: thì, bị động, giới từ, mệnh đề quan hệ.",
    },
    {
        "key": "preferredDifficulty",
        "question": "Mình nên bắt đầu nhẹ nhàng hay thử thách một chút?",
    },
    {
        "key": "preferredNumQuestions",
        "question": "Mỗi lần luyện bạn muốn khoảng bao nhiêu câu để vừa sức?",
    },
]

STEP_KEYS = [step["key"] for step in ONBOARDING_STEPS]
QUESTION_BY_KEY = {step["key"]: step["question"] for step in ONBOARDING_STEPS}


@dataclass(slots=True)
class OnboardingInterpretation:
    answers: dict[str, Any]
    assistant_reply: str
    next_question: str | None
    next_step_key: str | None
    is_complete: bool
    confidence: float
    source: str
    raw_llm_response: str = ""


@dataclass(slots=True)
class _LLMInterpretation:
    answers: dict[str, Any] = field(default_factory=dict)
    assistant_reply: str = ""
    next_question: str = ""
    confidence: float = 0.0
    raw_response: str = ""


class OnboardingInterpreter:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def extract_progressive_profile_facts(self, message: str) -> dict[str, Any]:
        """Extract conservative profile facts from an ordinary chat turn."""

        normalized = self._normalize_text(message)
        facts: dict[str, Any] = {}

        if self._has_display_name_signal(normalized):
            display_name = self._parse_display_name(message)
            if display_name:
                facts["display_name"] = display_name

        if (
            self._has_level_signal(normalized)
            and not self._is_unclear_or_survey_request(normalized)
        ):
            facts["level"] = self._parse_level(normalized)

        if self._has_goal_signal(normalized):
            goals = self._parse_goals(normalized, message)
            if goals:
                facts["goals"] = goals

        topics = (
            self._parse_topics(normalized, message)
            if self._has_topic_signal(normalized)
            else []
        )
        if topics:
            facts["recent_topics"] = topics
            facts["last_topic_requested"] = topics[0]
            if self._has_weakness_marker(normalized):
                facts["weak_topics"] = topics

        content_themes = self._extract_content_themes(normalized)
        if content_themes:
            facts["content_themes"] = content_themes
            facts["preferred_content_theme"] = content_themes[0]

        if self._has_difficulty_signal(normalized) and self._has_preference_scope(
            normalized,
        ):
            facts["preferred_difficulty"] = self._parse_difficulty(normalized)

        if self._has_question_count_signal(normalized) and self._has_preference_scope(
            normalized,
        ):
            facts["preferred_num_questions"] = self._parse_question_count(message)

        return facts

    def interpret(
        self,
        *,
        message: str,
        current_answers: dict[str, Any] | None = None,
        current_step_key: str | None = None,
    ) -> OnboardingInterpretation:
        current = self._normalize_answers(current_answers or {})
        step_key = current_step_key if current_step_key in STEP_KEYS else self._next_step_key(current)
        normalized_message = self._normalize_text(message)

        if (
            self.config.llm_backend.strip().lower() != "ollama"
            and step_key == "level"
            and self._is_unclear_or_survey_request(normalized_message)
        ):
            return OnboardingInterpretation(
                answers=current,
                assistant_reply=(
                    "Không sao, mình sẽ không đoán bừa level của bạn. "
                    "Mình hỏi nhanh một câu để ước lượng trước nhé."
                ),
                next_question=self._build_level_diagnostic_question(),
                next_step_key="level",
                is_complete=False,
                confidence=0.95,
                source="rule-based-clarify",
            )

        explicit_patch = (
            self._parse_step_answer(step_key, message)
            if step_key and not self._is_unclear_or_survey_request(normalized_message)
            else {}
        )
        rule_patch = self._extract_rule_hints(message)
        rule_answers = self._merge_answers(current, rule_patch, explicit_patch)

        llm = self._try_llm_interpret(
            message=message,
            current_step_key=step_key,
            current_answers=current,
            rule_answers=rule_answers,
        )
        final_answers = self._merge_answers(rule_answers, llm.answers)
        next_step_key = self._next_step_key(final_answers)
        is_complete = next_step_key is None

        assistant_reply = (
            llm.assistant_reply
            if llm.assistant_reply and not self._looks_english(llm.assistant_reply)
            else self._build_rule_reply(
                step_key=step_key,
                message=message,
                answers=final_answers,
                is_complete=is_complete,
            )
        )
        next_question = (
            None
            if is_complete
            else (
                llm.next_question
                if self._is_next_question_aligned(llm.next_question, next_step_key)
                else ""
            )
            or self._build_conversational_next_question(
                next_step_key=next_step_key,
                answers=final_answers,
            )
        )
        source = (
            "hybrid-ollama"
            if llm.answers or llm.assistant_reply or llm.next_question
            else "rule-based"
        )

        return OnboardingInterpretation(
            answers=final_answers,
            assistant_reply=assistant_reply,
            next_question=next_question,
            next_step_key=next_step_key,
            is_complete=is_complete,
            confidence=max(0.55, min(llm.confidence or 0.55, 1.0)),
            source=source,
            raw_llm_response=llm.raw_response[:4000],
        )

    def _try_llm_interpret(
        self,
        *,
        message: str,
        current_step_key: str | None,
        current_answers: dict[str, Any],
        rule_answers: dict[str, Any],
    ) -> _LLMInterpretation:
        if self.config.llm_backend.strip().lower() != "ollama":
            return _LLMInterpretation()

        prompt_payload = {
            "msg": message,
            "current": current_answers,
            "rule": rule_answers,
            "missing": self._next_step_key(rule_answers),
        }
        prompt = (
            "Extract onboarding facts from Vietnamese/English learner chat. "
            "Return strict compact JSON only: answers,assistant_reply,next_question,confidence. "
            "answers keys: displayName,level,goals,weakTopics,preferredDifficulty,preferredNumQuestions. "
            "Allowed level=beginner/intermediate/advanced; difficulty=easy/medium/hard. "
            "Common goals=daily_communication,exam_preparation,grammar_foundation,topic_vocabulary,travel_english. "
            "Common weakTopics=passive_voice,tenses,relative_clause,conditional_sentence,reported_speech,prepositions,vocabulary,travel_vocabulary. "
            "Use rule as baseline. Do not invent. Current user message wins. "
            "assistant_reply and next_question must be warm Vietnamese. "
            "assistant_reply <= 18 words. next_question <= 22 words. "
            "Ask one natural follow-up for missing info, not a form. Stay within grammar/vocabulary practice. "
            "If level is unclear, reassure and offer a short starter quiz. "
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
                "temperature": 0.2,
                "num_ctx": 1024,
                "num_predict": 120,
            },
        }

        url = f"{self.config.ollama_base_url.rstrip('/')}/api/chat"
        request = urllib.request.Request(
            url,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.onboarding_llm_timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return _LLMInterpretation()

        raw_content = str(payload.get("message", {}).get("content", "")).strip()
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            return _LLMInterpretation(raw_response=raw_content)

        answers = (
            self._normalize_answers(parsed.get("answers"))
            if isinstance(parsed.get("answers"), dict)
            else {}
        )
        answers = self._filter_llm_answers(
            answers=answers,
            message=message,
            current_step_key=current_step_key,
            rule_answers=rule_answers,
        )
        assistant_reply = self._safe_string(parsed.get("assistant_reply"))
        next_question = self._safe_string(parsed.get("next_question"))
        confidence = self._clamp_float(parsed.get("confidence"), 0.0, 1.0)
        if confidence < 0.35:
            answers = {}
        return _LLMInterpretation(
            answers=answers,
            assistant_reply=assistant_reply,
            next_question=next_question,
            confidence=confidence,
            raw_response=raw_content,
        )

    def _filter_llm_answers(
        self,
        *,
        answers: dict[str, Any],
        message: str,
        current_step_key: str | None,
        rule_answers: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = self._normalize_text(message)
        filtered: dict[str, Any] = {}

        if answers.get("displayName") and (
            current_step_key == "displayName" or self._has_display_name_signal(normalized)
        ):
            filtered["displayName"] = answers["displayName"]

        if answers.get("level") and (
            current_step_key == "level"
            or rule_answers.get("level")
            or self._has_level_signal(normalized)
            or self._is_unclear_or_survey_request(normalized)
        ):
            filtered["level"] = answers["level"]

        if answers.get("goals") and (
            current_step_key == "goals"
            or rule_answers.get("goals")
            or self._has_goal_signal(normalized)
        ):
            filtered["goals"] = answers["goals"]

        if answers.get("weakTopics") and (
            current_step_key == "weakTopics"
            or rule_answers.get("weakTopics")
            or self._has_topic_signal(normalized)
        ):
            filtered["weakTopics"] = answers["weakTopics"]

        if answers.get("preferredDifficulty") and (
            current_step_key == "preferredDifficulty"
            or rule_answers.get("preferredDifficulty")
            or self._has_difficulty_signal(normalized)
        ):
            filtered["preferredDifficulty"] = answers["preferredDifficulty"]

        if answers.get("preferredNumQuestions") and (
            current_step_key == "preferredNumQuestions"
            or rule_answers.get("preferredNumQuestions")
            or re.search(r"\b\d{1,2}\b", normalized)
        ):
            filtered["preferredNumQuestions"] = answers["preferredNumQuestions"]

        return filtered

    def _parse_step_answer(self, step_key: str | None, message: str) -> dict[str, Any]:
        if step_key == "displayName":
            return {"displayName": self._parse_display_name(message)}
        if step_key == "level":
            normalized = self._normalize_text(message)
            if self._is_unclear_or_survey_request(normalized):
                return {}
            return {"level": self._parse_level(normalized)}
        if step_key == "goals":
            return {"goals": self._parse_goals(self._normalize_text(message), message)}
        if step_key == "weakTopics":
            return {
                "weakTopics": self._parse_topics(self._normalize_text(message), message)
            }
        if step_key == "preferredDifficulty":
            return {"preferredDifficulty": self._parse_difficulty(self._normalize_text(message))}
        if step_key == "preferredNumQuestions":
            return {"preferredNumQuestions": self._parse_question_count(message)}
        return {}

    def _extract_rule_hints(self, message: str) -> dict[str, Any]:
        normalized = self._normalize_text(message)
        hints: dict[str, Any] = {}
        if self._has_level_signal(normalized):
            hints["level"] = self._parse_level(normalized)
        if self._has_goal_signal(normalized):
            hints["goals"] = self._parse_goals(normalized, message)
        if self._has_topic_signal(normalized):
            hints["weakTopics"] = self._parse_topics(normalized, message)
        if self._has_difficulty_signal(normalized):
            hints["preferredDifficulty"] = self._parse_difficulty(normalized)
        if re.search(r"\b\d{1,2}\b", normalized):
            hints["preferredNumQuestions"] = self._parse_question_count(message)
        return hints

    def _merge_answers(
        self,
        *patches: dict[str, Any],
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for patch in patches:
            normalized = self._normalize_answers(patch)
            if normalized.get("displayName"):
                merged["displayName"] = normalized["displayName"]
            if normalized.get("level"):
                merged["level"] = normalized["level"]
            if normalized.get("goals"):
                merged["goals"] = self._merge_unique(
                    merged.get("goals"),
                    normalized["goals"],
                )
            if normalized.get("weakTopics"):
                merged["weakTopics"] = self._merge_unique(
                    merged.get("weakTopics"),
                    normalized["weakTopics"],
                )
            if normalized.get("preferredDifficulty"):
                merged["preferredDifficulty"] = normalized["preferredDifficulty"]
            if normalized.get("preferredNumQuestions"):
                merged["preferredNumQuestions"] = normalized["preferredNumQuestions"]
        return merged

    def _normalize_answers(self, raw_answers: object) -> dict[str, Any]:
        if not isinstance(raw_answers, dict):
            return {}
        normalized: dict[str, Any] = {}

        display_name = self._safe_string(raw_answers.get("displayName"))
        if display_name:
            normalized["displayName"] = self._parse_display_name(display_name)

        level = self._safe_string(raw_answers.get("level")).lower()
        if level in {"beginner", "intermediate", "advanced"}:
            normalized["level"] = level

        goals = self._normalize_string_list(raw_answers.get("goals"))
        if goals:
            normalized["goals"] = [
                goal
                for goal in self._merge_unique(None, [self._normalize_goal(goal) for goal in goals])
                if goal
            ]

        weak_topics = self._normalize_string_list(raw_answers.get("weakTopics"))
        if weak_topics:
            normalized["weakTopics"] = [
                topic
                for topic in self._merge_unique(
                    None,
                    [self._normalize_topic_code(topic) for topic in weak_topics],
                )
                if topic
            ]

        difficulty = self._safe_string(raw_answers.get("preferredDifficulty")).lower()
        if difficulty in {"easy", "medium", "hard"}:
            normalized["preferredDifficulty"] = difficulty

        question_count = self._coerce_int(raw_answers.get("preferredNumQuestions"))
        if question_count is not None:
            normalized["preferredNumQuestions"] = min(max(question_count, 1), 20)

        return normalized

    def _parse_display_name(self, message: str) -> str:
        trimmed = message.strip()
        if not trimmed:
            return ""
        patterns = [
            r"(?:^|[\s,.;!?])(?:cứ\s+)?(?:gọi|goi)\s+(?:(?:mình|minh|tôi|toi|em|anh|chị|chi|bạn|ban)\s+)?(?:là|la)\s+(.+)$",
            r"(?:^|[\s,.;!?])(?:tên|ten)\s+(?:(?:mình|minh|tôi|toi|em|anh|chị|chi|bạn|ban)\s+)?(?:là|la)?\s*(.+)$",
            r"(?:^|[\s,.;!?])(?:mình|minh|tôi|toi|em|anh|chị|chi)\s+(?:là|la)\s+(.+)$",
            r"(?:^|[\s,.;!?])(?:call me|my name is|i am|i'm)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, trimmed, re.IGNORECASE)
            if match:
                candidate = self._clean_display_name_candidate(match.group(1))
                if self._is_usable_display_name(candidate):
                    return self._title_display_name(candidate)

        candidate = self._clean_display_name_candidate(trimmed)
        return self._title_display_name(candidate) if self._is_usable_display_name(candidate) else ""

    def _clean_display_name_candidate(self, value: str) -> str:
        candidate = re.split(r"[,.;!?\n]", value, maxsplit=1)[0]
        candidate = " ".join(candidate.strip(" .,!?:;").split())
        candidate = re.sub(
            r"\s+(?:cũng được|cung duoc|được|duoc|đi|di|nhé|nhe|nha|ạ|a|ha|với|voi|thôi|thoi)$",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip()
        candidate = re.sub(r"^(?:là|la)\s+", "", candidate, flags=re.IGNORECASE)
        return candidate[:40]

    def _is_usable_display_name(self, candidate: str) -> bool:
        normalized = self._normalize_text(candidate)
        return bool(candidate) and len(candidate.split()) <= 6 and normalized not in {
            "beginner",
            "intermediate",
            "advanced",
            "easy",
            "medium",
            "hard",
            "co ban",
            "khong biet",
            "chua biet",
        }

    def _title_display_name(self, value: str) -> str:
        return " ".join(part[:1].upper() + part[1:] for part in value.split(" "))

    def _parse_level(self, normalized: str) -> str:
        if re.fullmatch(r"(?:chon\s+)?c", normalized):
            return "advanced"
        if re.search(r"\bc[12]\b", normalized) or any(
            token in normalized for token in ["advanced", "nang cao"]
        ):
            return "advanced"
        if re.fullmatch(r"(?:chon\s+)?b", normalized):
            return "intermediate"
        if re.search(r"\bb[12]\b", normalized) or any(
            token in normalized for token in ["intermediate", "trung cap", "trung binh", "vua"]
        ):
            return "intermediate"
        return "beginner"

    def _parse_difficulty(self, normalized: str) -> str:
        if self._has_any(normalized, ["hard", "kho", "thu thach", "nang cao"]):
            return "hard"
        if self._has_any(normalized, ["medium", "trung binh", "vua"]):
            return "medium"
        return "easy"

    def _parse_question_count(self, message: str) -> int:
        match = re.search(r"\b\d{1,2}\b", self._normalize_text(message))
        if not match:
            return self.config.default_num_questions
        return min(max(int(match.group(0)), 1), 20)

    def _parse_goals(self, normalized: str, message: str) -> list[str]:
        goals: list[str] = []
        if "giao tiep" in normalized:
            goals.append("daily_communication")
        if any(token in normalized for token in ["toeic", "ielts", "on thi", "thi toeic", "thi ielts", "kiem tra"]):
            goals.append("exam_preparation")
        if "ngu phap" in normalized or "grammar" in normalized:
            goals.append("grammar_foundation")
        if "tu vung" in normalized or "vocabulary" in normalized:
            goals.append("topic_vocabulary")
        if "du lich" in normalized or "travel" in normalized:
            goals.append("travel_english")
        return self._merge_unique(None, goals) or self._split_freeform_list(message)

    def _parse_topics(self, normalized: str, message: str) -> list[str]:
        topics: list[str] = []
        if "passive" in normalized or "bi dong" in normalized:
            topics.append("passive_voice")
        if "relative" in normalized or "quan he" in normalized:
            topics.append("relative_clause")
        if "conditional" in normalized or "dieu kien" in normalized:
            topics.append("conditional_sentence")
        if "reported" in normalized or "gian tiep" in normalized:
            topics.append("reported_speech")
        if self._has_tense_signal(normalized) or "ngu phap" in normalized or "grammar" in normalized:
            topics.append("tenses")
        if "preposition" in normalized or "gioi tu" in normalized:
            topics.append("prepositions")
        if "du lich" in normalized or "travel" in normalized:
            topics.append("travel_vocabulary")
        elif "tu vung" in normalized or "vocabulary" in normalized:
            topics.append("vocabulary")
        return self._merge_unique(None, topics) or self._split_freeform_list(message)

    def _build_rule_reply(
        self,
        *,
        step_key: str | None,
        message: str,
        answers: dict[str, Any],
        is_complete: bool,
    ) -> str:
        if is_complete:
            return (
                f"Ổn rồi {answers.get('displayName') or 'bạn'}, mình đã có đủ thông tin "
                "để tạo bài đầu tiên cho đúng nhịp hơn."
            )
        if step_key == "displayName":
            return f"Rất vui được đồng hành cùng {answers.get('displayName') or self._parse_display_name(message) or 'bạn'}."
        if step_key == "level":
            return "Ổn, mình sẽ giữ nhịp vừa đủ để bạn không bị ngợp."
        if step_key == "goals":
            return "Mục tiêu rõ hơn rồi. Mình sẽ ưu tiên bài tập có ích cho hướng đó."
        if step_key == "weakTopics":
            return "Hay, biết điểm vướng là mình cá nhân hóa bài tốt hơn nhiều."
        if step_key == "preferredDifficulty":
            difficulty = answers.get("preferredDifficulty", "easy")
            count = answers.get("preferredNumQuestions")
            if count:
                return f"Ok, mình ghi nhận mức {difficulty} và khoảng {count} câu cho mỗi lượt."
            return "Được, mình sẽ bắt đầu ở mức đó và tăng/giảm theo kết quả của bạn."
        return "Mình ghi nhận số câu này để mỗi lượt luyện vừa sức hơn."

    def _next_step_key(self, answers: dict[str, Any]) -> str | None:
        for step_key in STEP_KEYS:
            value = answers.get(step_key)
            if isinstance(value, list):
                if not value:
                    return step_key
            elif value in (None, ""):
                return step_key
        return None

    def _has_display_name_signal(self, normalized: str) -> bool:
        return self._has_any(
            normalized,
            [
                "goi minh la",
                "goi toi la",
                "ten minh la",
                "ten toi la",
                "minh la",
                "toi la",
                "call me",
                "my name is",
            ],
        )

    def _has_level_signal(self, normalized: str) -> bool:
        return bool(re.search(r"\b[abc][12]\b", normalized)) or self._has_any(
            normalized,
            ["beginner", "intermediate", "advanced", "moi hoc", "mat goc", "so cap"],
        )

    def _is_unclear_or_survey_request(self, normalized: str) -> bool:
        return self._has_any(
            normalized,
            [
                "khong ro",
                "ko ro",
                "k ro",
                "khong biet",
                "ko biet",
                "chua biet",
                "khong chac",
                "ko chac",
                "chua chac",
                "khao sat",
                "test thu",
                "kiem tra giup",
                "danh gia giup",
                "xem giup",
            ],
        )

    def _build_level_diagnostic_question(self) -> str:
        return (
            "Bạn chọn mô tả gần nhất nhé: Beginner nếu bạn mới học/mất gốc; "
            "Intermediate nếu đọc câu đơn giản ổn nhưng hay sai khi nói/viết; "
            "Advanced nếu bạn muốn luyện câu dài, sắc thái và lỗi khó."
        )

    def _build_conversational_next_question(
        self,
        *,
        next_step_key: str | None,
        answers: dict[str, Any],
    ) -> str | None:
        if next_step_key == "displayName":
            return (
                "Trước hết mình làm quen nhẹ nha: mình nên gọi bạn là gì? "
                "Nếu chưa muốn nói tên thật, nickname cũng được."
            )
        if next_step_key == "level":
            return (
                "Về trình độ thì bạn không cần tự gắn nhãn đâu. "
                "Bạn kể mình nghe hiện tại bạn đọc câu đơn giản có ổn không, "
                "hay đang học lại từ đầu?"
            )
        if next_step_key == "goals":
            name = answers.get("displayName") or "bạn"
            return (
                f"{name} muốn dùng tiếng Anh vào việc gì nhiều nhất lúc này: "
                "nói chuyện, đi học/đi thi, công việc, hay chỉ muốn lấy lại căn bản?"
            )
        if next_step_key == "weakTopics":
            return (
                "Khi học tiếng Anh, phần nào hay làm bạn đứng lại nhất? "
                "Nếu chưa biết, cứ nói 'mình chưa rõ', mình sẽ cho bài khởi động để đo dần."
            )
        if next_step_key == "preferredDifficulty":
            return (
                "Để bắt đầu cho đỡ ngợp, mình có thể tạo bài nhẹ trước rồi tăng dần. "
                "Bạn muốn đi chậm chắc hay thử thách hơn một chút?"
            )
        if next_step_key == "preferredNumQuestions":
            return (
                "Mỗi lượt mình nên tạo khoảng bao nhiêu câu để bạn thấy vừa sức? "
                "Nếu chưa rõ, mình sẽ mặc định 5 câu trước."
            )
        return None

    def _is_next_question_aligned(
        self,
        question: str,
        next_step_key: str | None,
    ) -> bool:
        if not question or not next_step_key:
            return False
        normalized = self._normalize_text(question)
        expected_signals = {
            "displayName": ["goi", "ten", "nickname", "xung ho"],
            "level": ["trinh do", "mat goc", "hoc lai", "doc cau", "beginner"],
            "goals": ["muc tieu", "dung tieng anh", "giao tiep", "thi", "cong viec", "du lich"],
            "weakTopics": ["phan nao", "hay sai", "bi", "loi", "khung", "dung lai"],
            "preferredDifficulty": ["nhe", "thu thach", "kho", "vua", "muc"],
            "preferredNumQuestions": ["bao nhieu", "may cau", "so cau", "cau"],
        }
        return any(
            signal in normalized
            for signal in expected_signals.get(next_step_key, [])
        )

    def _has_goal_signal(self, normalized: str) -> bool:
        return self._has_any(
            normalized,
            [
                "giao tiep",
                "toeic",
                "ielts",
                "kiem tra",
                "on thi",
                "thi toeic",
                "thi ielts",
                "ngu phap",
                "grammar",
                "tu vung",
                "vocabulary",
                "du lich",
                "travel",
            ],
        )

    def _has_topic_signal(self, normalized: str) -> bool:
        return self._has_any(
            normalized,
            [
                "passive",
                "bi dong",
                "relative",
                "quan he",
                "conditional",
                "dieu kien",
                "reported",
                "gian tiep",
                "preposition",
                "gioi tu",
                "ngu phap",
                "grammar",
                "tu vung",
                "vocabulary",
                "du lich",
                "travel",
            ],
        ) or self._has_tense_signal(normalized)

    def _has_difficulty_signal(self, normalized: str) -> bool:
        return self._has_any(
            normalized,
            [
                "easy",
                "co ban",
                "nhe",
                "muc de",
                "cau de",
                "medium",
                "trung binh",
                "vua",
                "hard",
                "kho",
                "thu thach",
                "nang cao",
            ],
        )

    def _has_preference_scope(self, normalized: str) -> bool:
        return self._has_any(
            normalized,
            [
                "tu gio",
                "tu bay gio",
                "lan sau",
                "moi lan",
                "mac dinh",
                "uu tien",
                "toi muon",
                "minh muon",
                "i want",
                "prefer",
                "preference",
            ],
        )

    def _has_question_count_signal(self, normalized: str) -> bool:
        return bool(re.search(r"\b\d{1,2}\b", normalized))

    def _has_weakness_marker(self, normalized: str) -> bool:
        return self._has_any(
            normalized,
            [
                "hay sai",
                "thuong sai",
                "yeu",
                "kem",
                "kho",
                "loi",
                "quen",
                "weak",
                "mistake",
                "struggle",
                "bad at",
            ],
        )

    def _extract_content_themes(self, normalized: str) -> list[str]:
        themes: list[str] = []
        if self._has_any(
            normalized,
            [
                "anime",
                "manga",
                "otaku",
                "anime character",
                "nhan vat anime",
            ],
        ):
            themes.append("anime")
        return themes

    def _has_tense_signal(self, normalized: str) -> bool:
        return normalized == "thi" or self._has_any(
            normalized,
            ["tense", "tenses", "cac thi", "chia thi", "thi dong tu"],
        )

    def _has_any(self, normalized: str, signals: list[str]) -> bool:
        return any(
            re.search(rf"(?<!\w){re.escape(signal)}(?!\w)", normalized)
            for signal in signals
        )

    def _split_freeform_list(self, message: str) -> list[str]:
        return [
            item
            for item in (
                self._normalize_text(part).replace(" ", "_")
                for part in re.split(r"[,;|]", message)
            )
            if item
        ][:5]

    def _normalize_goal(self, value: str) -> str:
        normalized = self._normalize_text(value).replace(" ", "_")
        aliases = {
            "communication": "daily_communication",
            "giao_tiep": "daily_communication",
            "toeic": "exam_preparation",
            "ielts": "exam_preparation",
            "exam": "exam_preparation",
            "grammar": "grammar_foundation",
            "ngu_phap": "grammar_foundation",
            "vocabulary": "topic_vocabulary",
            "tu_vung": "topic_vocabulary",
            "travel": "travel_english",
            "du_lich": "travel_english",
        }
        return aliases.get(normalized, normalized)

    def _normalize_topic_code(self, topic: str) -> str:
        normalized = self._normalize_text(topic).replace("-", "_").replace(" ", "_")
        aliases = {
            "passive": "passive_voice",
            "bi_dong": "passive_voice",
            "relative": "relative_clause",
            "quan_he": "relative_clause",
            "conditional": "conditional_sentence",
            "dieu_kien": "conditional_sentence",
            "reported": "reported_speech",
            "gian_tiep": "reported_speech",
            "tense": "tenses",
            "thi": "tenses",
            "ngu_phap": "tenses",
            "grammar": "tenses",
            "preposition": "prepositions",
            "gioi_tu": "prepositions",
            "travel": "travel_vocabulary",
            "du_lich": "travel_vocabulary",
            "tu_vung": "vocabulary",
        }
        return aliases.get(normalized, normalized)

    def _normalize_text(self, value: str) -> str:
        normalized = value.replace("đ", "d").replace("Đ", "D")
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(
            character
            for character in normalized
            if unicodedata.category(character) != "Mn"
        )
        return normalized.lower().strip()

    def _normalize_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _merge_unique(
        self,
        current: object,
        incoming: list[str],
    ) -> list[str]:
        values = [
            *(current if isinstance(current, list) else []),
            *incoming,
        ]
        seen: set[str] = set()
        merged: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                merged.append(value)
        return merged

    def _safe_string(self, value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    def _coerce_int(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    def _clamp_float(self, value: object, minimum: float, maximum: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(minimum, min(parsed, maximum))

    def _looks_english(self, value: str) -> bool:
        normalized = f" {value.lower()} "
        return any(
            marker in normalized
            for marker in [" this ", " learner ", " should ", " answer ", " question "]
        )
