import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any

from langchain_core.runnables import Runnable

from app.config import AppConfig
from app.conversation.schemas import ConversationRoute
from app.retrieval.service import RetrievalService
from app.schemas import ConversationTurnContext, KnowledgeChunk, PracticePlan


@dataclass(slots=True)
class TutorCapabilityResult:
    assistant_reply: str
    ui_action: str = "conversation.reply"
    activity: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TutorResponseLLM:
    """Small text-response adapter for optional tutor conversation LLM calls."""

    def __init__(
        self,
        *,
        config: AppConfig,
        runnable: Runnable[Any, Any] | None,
        backend_name: str,
    ) -> None:
        self.config = config
        self.runnable = runnable
        self.backend_name = backend_name

    def generate(self, messages: list[dict[str, str]]) -> str | None:
        if self.runnable is None or not self.config.tutor_response_llm_enabled:
            return None

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.runnable.invoke, messages)
        try:
            result = future.result(
                timeout=self.config.tutor_response_llm_timeout_seconds,
            )
        except TimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return None
        except Exception:
            executor.shutdown(wait=False, cancel_futures=True)
            return None
        finally:
            if future.done():
                executor.shutdown(wait=True)

        content = self._extract_content(result)
        return content if content else None

    def _extract_content(self, result: Any) -> str:
        content = getattr(result, "content", result)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return " ".join(part.strip() for part in parts if part.strip()).strip()
        return str(content).strip()


class TutorExplainService:
    """Grounded, lightweight explanation capability for conversation turns."""

    def __init__(
        self,
        config: AppConfig,
        retrieval: RetrievalService | None = None,
        response_llm: TutorResponseLLM | None = None,
    ) -> None:
        self.config = config
        self.retrieval = retrieval
        self.response_llm = response_llm

    def explain(
        self,
        *,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> TutorCapabilityResult:
        concept = self._normalize_concept(route.slots.get("concept"))
        spec = self._concept_spec(concept)
        chunks = self._retrieve_context(spec, context)
        llm_reply = self._try_llm_explanation(
            route=route,
            context=context,
            concept=concept,
            spec=spec,
            chunks=chunks,
        )
        if llm_reply:
            return TutorCapabilityResult(
                assistant_reply=llm_reply,
                ui_action="explain.respond",
                metadata=self._metadata(
                    concept=concept,
                    spec=spec,
                    chunks=chunks,
                    response_source="llm",
                ),
            )

        rag_line = self._rag_line(chunks)
        reply = (
            f"{spec['title']}: {spec['rule']} {spec['example']} "
            f"{spec['tip']}{rag_line}"
        )
        return TutorCapabilityResult(
            assistant_reply=reply,
            ui_action="explain.respond",
            metadata=self._metadata(
                concept=concept,
                spec=spec,
                chunks=chunks,
                response_source="rule-fallback",
            ),
        )

    def _try_llm_explanation(
        self,
        *,
        route: ConversationRoute,
        context: ConversationTurnContext,
        concept: str,
        spec: dict[str, str | None],
        chunks: list[KnowledgeChunk],
    ) -> str | None:
        if self.response_llm is None:
            return None
        message = _latest_user_message(context)
        payload = {
            "message": message,
            "concept": concept,
            "route_slots": route.slots,
            "learner": _learner_payload(context),
            "retrieved_context": [
                {
                    "chunk_id": chunk.chunk_id,
                    "topic": chunk.topic,
                    "source": chunk.source,
                    "content": " ".join(chunk.content.split())[:700],
                }
                for chunk in chunks[:3]
            ],
            "fallback_outline": {
                "title": spec["title"],
                "rule": spec["rule"],
                "example": spec["example"],
                "tip": spec["tip"],
            },
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an English tutor for a Vietnamese learner. "
                    "Answer in Vietnamese unless the learner asks otherwise. "
                    "Use the retrieved context when relevant. Be natural, concise, "
                    "and explain with one short example. Do not create exercises "
                    "unless explicitly asked."
                ),
            },
            {
                "role": "user",
                "content": f"EXPLAIN_PAYLOAD={json.dumps(payload, ensure_ascii=False)}",
            },
        ]
        return _clean_llm_reply(self.response_llm.generate(messages))

    def _retrieve_context(
        self,
        spec: dict[str, str | None],
        context: ConversationTurnContext,
    ) -> list[KnowledgeChunk]:
        if self.retrieval is None:
            return []
        plan = PracticePlan(
            user_id=context.learner_id,
            topic=str(spec["topic"] or "grammar"),
            difficulty=(
                context.profile.preferred_difficulty
                or self.config.default_difficulty
            ),
            exercise_type="explanation_context",
            num_questions=1,
            focus_reason="Retrieve context for tutor explanation.",
            target_subtopic=spec.get("subtopic"),
        )
        try:
            return self.retrieval.retrieve(plan, context.profile.level)
        except Exception:
            return []

    def _rag_line(self, chunks: list[KnowledgeChunk]) -> str:
        if not chunks:
            return ""
        content = " ".join(chunks[0].content.split())
        if not content:
            return ""
        return f" Tai lieu lien quan: {content[:220]}"

    def _metadata(
        self,
        *,
        concept: str,
        spec: dict[str, str | None],
        chunks: list[KnowledgeChunk],
        response_source: str,
    ) -> dict[str, Any]:
        return {
            "concept": concept,
            "topic": spec["topic"],
            "subtopic": spec.get("subtopic"),
            "response_source": response_source,
            "llm_backend": (
                self.response_llm.backend_name if self.response_llm is not None else None
            ),
            "sources": [
                {
                    "chunk_id": chunk.chunk_id,
                    "topic": chunk.topic,
                    "source": chunk.source,
                }
                for chunk in chunks
            ],
        }

    def _normalize_concept(self, value: object) -> str:
        concept = str(value or "").strip().lower().replace(" ", "_")
        if concept in {"preposition"}:
            return "prepositions"
        if concept:
            return concept
        return "grammar"

    def _concept_spec(self, concept: str) -> dict[str, str | None]:
        concepts: dict[str, dict[str, str | None]] = {
            "past_perfect": {
                "title": "Past Perfect",
                "topic": "tenses",
                "subtopic": "past_perfect_sequence",
                "rule": "Dung `had + V3` de noi ve mot hanh dong xay ra truoc mot moc khac trong qua khu.",
                "example": "Vi du: `When I arrived, she had left`.",
                "tip": "Hay tim hai moc thoi gian qua khu va dat hanh dong som hon o Past Perfect.",
            },
            "passive_voice": {
                "title": "Passive Voice",
                "topic": "passive_voice",
                "subtopic": "present_simple_passive",
                "rule": "Dung `be + V3` khi muon nhan vao nguoi/vat nhan hanh dong hon la nguoi lam.",
                "example": "Vi du: `The room is cleaned every day`.",
                "tip": "Doi tan ngu cua cau chu dong len lam chu ngu va chia `be` theo thi.",
            },
            "relative_clause": {
                "title": "Relative Clauses",
                "topic": "relative_clause",
                "subtopic": "who_for_people",
                "rule": "Dung menh de quan he de bo sung thong tin cho danh tu truoc no.",
                "example": "Vi du: `The student who sits near me is friendly`.",
                "tip": "`Who` thuong dung cho nguoi, `which` cho vat, `that` co the dung trong nhieu truong hop than mat.",
            },
            "conditional": {
                "title": "Conditionals",
                "topic": "conditional_sentence",
                "subtopic": "first_conditional",
                "rule": "Cau dieu kien noi ve ket qua phu thuoc vao mot dieu kien.",
                "example": "Vi du: `If it rains, I will stay home`.",
                "tip": "Xac dinh dieu kien that/hien tai/gia dinh truoc khi chon type 1, 2 hay 3.",
            },
            "reported_speech": {
                "title": "Reported Speech",
                "topic": "reported_speech",
                "subtopic": "reported_speech_general",
                "rule": "Dung reported speech de thuat lai loi noi, thuong can lui thi va doi dai tu/thoi gian.",
                "example": "Vi du: `She said that she was busy`.",
                "tip": "Hay kiem tra nguoi noi, thoi diem noi va thi cua cau goc.",
            },
            "prepositions": {
                "title": "Prepositions",
                "topic": "prepositions",
                "subtopic": None,
                "rule": "Prepositions noi danh tu/cum danh tu voi phan con lai cua cau.",
                "example": "Vi du: `interested in`, `good at`, `on Monday`.",
                "tip": "Hoc theo cum co dinh va ngu canh thay vi dich tung tu.",
            },
            "vocabulary": {
                "title": "Vocabulary",
                "topic": "vocabulary",
                "subtopic": None,
                "rule": "Hoc tu vung tot nhat khi gan nghia, dang tu va collocation vao ngu canh that.",
                "example": "Vi du: hoc `make a decision` nhu mot cum, khong chi hoc rieng `decision`.",
                "tip": "Ghi lai mot cau vi du ngan cho moi tu moi.",
            },
        }
        return concepts.get(
            concept,
            {
                "title": concept.replace("_", " ").title() or "Grammar",
                "topic": "grammar",
                "subtopic": None,
                "rule": "Khai niem nay nen duoc hoc bang cong thuc, vi du va dau hieu nhan biet.",
                "example": "Hay gui them mot cau mau neu ban muon minh giai thich sat ngu canh hon.",
                "tip": "Bat dau bang cach hoi: no dung de lam gi, cau truc la gi, va de nham voi diem nao.",
            },
        )


class GeneralTutorService:
    """Friendly tutor response capability for non-practice conversation."""

    def __init__(
        self,
        config: AppConfig,
        response_llm: TutorResponseLLM | None = None,
    ) -> None:
        self.config = config
        self.response_llm = response_llm

    def respond(
        self,
        *,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> TutorCapabilityResult:
        message = _latest_user_message(context)
        learning_focus = _safe_learning_focus(route.slots.get("learning_focus"))
        if learning_focus is not None:
            return TutorCapabilityResult(
                assistant_reply=self._learning_focus_response(learning_focus, context),
                ui_action="conversation.reply",
                metadata={
                    "scope": "english_tutor_general",
                    "response_source": "guided-choice",
                    "llm_backend": None,
                    "matched_template": f"learning_focus_{learning_focus}",
                    "used_message": message[:240],
                    "learning_focus": learning_focus,
                },
            )

        llm_reply = self._try_llm_response(
            message=message,
            route=route,
            context=context,
        )
        if llm_reply:
            return TutorCapabilityResult(
                assistant_reply=llm_reply,
                ui_action="conversation.reply",
                metadata={
                    "scope": "english_tutor_general",
                    "response_source": "llm",
                    "llm_backend": self.response_llm.backend_name
                    if self.response_llm is not None
                    else None,
                    "matched_template": None,
                    "used_message": message[:240],
                },
            )

        reply, template = self._fallback_response(message, context)
        return TutorCapabilityResult(
            assistant_reply=reply,
            ui_action="conversation.reply",
            metadata={
                "scope": "english_tutor_general",
                "response_source": "context-fallback",
                "llm_backend": None,
                "matched_template": template,
                "used_message": message[:240],
            },
        )

    def _try_llm_response(
        self,
        *,
        message: str,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> str | None:
        if self.response_llm is None:
            return None
        payload = {
            "message": message,
            "intent": route.intent.value,
            "route_reason": route.reason,
            "route_slots": route.slots,
            "learner": _learner_payload(context),
            "memory_summary": context.memory_summary[:500],
            "recent_messages": _recent_messages_payload(context),
            "active_activity": _activity_payload(context),
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a warm English tutor for a Vietnamese learner. "
                    "Reply naturally in Vietnamese unless the learner asks for English. "
                    "Keep the answer within the English-learning scope. If the learner "
                    "is off-topic, acknowledge briefly and bridge it back to English "
                    "practice. If the learner picks speaking, listening, reading, or "
                    "writing from a previous menu, accept that choice and give the next "
                    "concrete step; do not ask the same menu again. Do not create a quiz "
                    "or exercise unless they clearly ask."
                ),
            },
            {
                "role": "user",
                "content": f"GENERAL_CHAT_PAYLOAD={json.dumps(payload, ensure_ascii=False)}",
            },
        ]
        return _clean_llm_reply(self.response_llm.generate(messages))

    def _fallback_response(
        self,
        message: str,
        context: ConversationTurnContext,
    ) -> tuple[str, str]:
        name = context.profile.display_name or "ban"
        normalized = _normalize_text(message)
        preferred = context.profile.preferred_difficulty or self.config.default_difficulty
        weak_topic = _top_weak_topic(context)
        active_activity = context.active_activity

        if _has_any(normalized, ("cam on", "thanks", "thank you", "tks")):
            return (
                f"Khong co gi, {name}. Neu ban muon, minh co the giai thich lai "
                "mot diem ngu phap vua hoc hoac tao tiep mot bai ngan theo diem yeu.",
                "thanks",
            )

        if _has_any(normalized, ("chao", "hello", "hi", "hey")):
            focus = (
                f" Hom nay minh goi y quay lai {weak_topic.replace('_', ' ')}."
                if weak_topic
                else " Hom nay minh co the giup ban chon mot bai khoi dong ngan."
            )
            return (
                f"Chao {name}, minh dang o day.{focus} Ban co the gui mot cau can sua, "
                "hoi ly thuyet ngu phap, hoac noi chu de muon luyen.",
                "greeting",
            )

        if _has_any(
            normalized,
            ("hoc gi", "luyen gi", "nen hoc", "bat dau", "study what"),
        ):
            if weak_topic:
                return (
                    f"Voi ho so hien tai, minh se uu tien {weak_topic.replace('_', ' ')} "
                    f"o muc {preferred}. Neu ban muon nhe nhang, minh tao 5 cau; "
                    "neu muon nhanh gon hon, minh co the chi giai thich mot vi du truoc.",
                    "study_suggestion",
                )
            return (
                f"Minh chua co du lieu yeu ro cua {name}, nen nen bat dau bang mot bai "
                f"{preferred} 5 cau de do nhip. Sau bai do minh se goi y chinh xac hon.",
                "study_suggestion_no_profile",
            )

        if active_activity is not None:
            status = active_activity.status.value.lower()
            topic = _label_list(active_activity.target_skills[:2]) or "bai hien tai"
            return (
                f"Minh van thay activity {status} ve {topic}. Neu ban dang ket o dau, "
                "gui so cau hoac dap an ban phan van, minh se giai thich theo bai do.",
                "active_activity",
            )

        if context.memory_summary:
            return (
                f"Minh co nho tom tat gan day: {context.memory_summary[:160]}. "
                "Tu do, ban co the hoi tiep mot diem ngu phap, gui cau can sua, "
                "hoac bao minh tao bai bam vao diem yeu.",
                "memory_summary",
            )

        if _looks_like_off_topic(normalized):
            topic = _off_topic_keyword(normalized) or "chu de nay"
            return (
                f"Minh khong phai tro ly tong quat cho {topic}, nhung minh co the bien "
                "no thanh mot bai hoc tieng Anh: tu vung lien quan, mau cau hoi-dap, "
                "hoac cach dien dat tu nhien hon.",
                "off_topic_bridge",
            )

        short_message = message.strip()[:80] or "y cua ban"
        return (
            f"Minh nghe y nay: \"{short_message}\". Trong pham vi hoc tieng Anh, "
            "minh co the giup ban sua cau, giai thich ngu phap, xem tien do, "
            "hoac tao bai luyen theo dung muc hien tai.",
            "generic_contextual",
        )

    def _learning_focus_response(
        self,
        learning_focus: str,
        context: ConversationTurnContext,
    ) -> str:
        level = context.profile.level or "beginner"
        preferred = context.profile.preferred_difficulty or self.config.default_difficulty
        replies = {
            "reading": (
                f"Ok, minh bat dau voi reading truoc nhe. Ban gui mot doan tieng Anh "
                f"muon doc, hoac noi mot chu de ban thich; neu chua co doan, minh se "
                f"chon mot doan ngan muc {level}/{preferred} roi giup ban nam y chinh, "
                "tu moi va cau kho."
            ),
            "listening": (
                f"Ok, minh bat dau voi listening truoc. Ban gui transcript/link audio "
                f"neu co; neu chua co, minh se tao mot doan hoi thoai ngan muc "
                f"{level}/{preferred} de ban nghe y chinh, tu khoa va cach phat am."
            ),
            "speaking": (
                f"Ok, minh bat dau voi speaking truoc. Ban chon mot tinh huong ngan "
                f"hoac de minh goi y tinh huong muc {level}/{preferred}; minh se dua "
                "mau cau tu nhien roi minh va ban hoi-dap tung luot."
            ),
            "writing": (
                f"Ok, minh bat dau voi writing truoc. Ban gui mot cau/doan ngan muon "
                f"viet, hoac noi chu de; minh se giup sua theo muc {level}/{preferred} "
                "va chi ra mot diem can nang cap."
            ),
        }
        return replies[learning_focus]


def _clean_llm_reply(reply: str | None) -> str | None:
    if reply is None:
        return None
    cleaned = reply.strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"^```(?:json|text)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned[:1600] if cleaned else None


def _safe_learning_focus(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"reading", "listening", "speaking", "writing"}:
        return normalized
    return None


def _latest_user_message(context: ConversationTurnContext) -> str:
    for item in reversed(context.recent_messages):
        if item.get("role") == "user":
            return str(item.get("content") or "")
    return ""


def _learner_payload(context: ConversationTurnContext) -> dict[str, Any]:
    profile = context.profile
    return {
        "display_name": profile.display_name,
        "level": profile.level,
        "goals": profile.goals[:5],
        "preferred_difficulty": profile.preferred_difficulty,
        "preferred_num_questions": profile.preferred_num_questions,
        "weak_topics": dict(list(profile.weak_topics.items())[:5]),
        "skill_mastery": dict(list(profile.skill_mastery.items())[:5]),
    }


def _recent_messages_payload(
    context: ConversationTurnContext,
) -> list[dict[str, str]]:
    return [
        {
            "role": str(item.get("role") or "")[:20],
            "content": str(item.get("content") or "")[:240],
        }
        for item in context.recent_messages[-6:]
        if isinstance(item, dict)
    ]


def _activity_payload(context: ConversationTurnContext) -> dict[str, Any] | None:
    activity = context.active_activity
    if activity is None:
        return None
    return {
        "activity_id": activity.activity_id,
        "type": activity.type.value,
        "status": activity.status.value,
        "target_skills": activity.target_skills[:5],
        "difficulty": activity.difficulty,
        "generation_run_id": activity.generation_run_id,
        "session_code": activity.session_code,
    }


def _top_weak_topic(context: ConversationTurnContext) -> str | None:
    weak_topics = context.profile.weak_topics
    if not weak_topics:
        facts = context.recent_context.get("chat_extracted_facts")
        if isinstance(facts, dict):
            values = facts.get("weak_topics") or facts.get("recent_topics")
            if isinstance(values, list) and values:
                return str(values[0])
        return None
    return max(weak_topics.items(), key=lambda item: item[1])[0]


def _normalize_text(value: str) -> str:
    normalized = value.replace("\u0111", "d").replace("\u0110", "D")
    normalized = (
        unicodedata.normalize("NFD", normalized)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )
    return re.sub(r"\s+", " ", normalized)


def _has_any(normalized: str, signals: tuple[str, ...]) -> bool:
    return any(signal in normalized for signal in signals)


def _looks_like_off_topic(normalized: str) -> bool:
    return _has_any(
        normalized,
        (
            "thoi tiet",
            "weather",
            "bong da",
            "football",
            "code",
            "lap trinh",
            "nau an",
            "game",
            "phim",
            "music",
            "nhac",
        ),
    )


def _off_topic_keyword(normalized: str) -> str | None:
    for keyword in (
        "thoi tiet",
        "weather",
        "bong da",
        "football",
        "code",
        "lap trinh",
        "nau an",
        "game",
        "phim",
        "music",
        "nhac",
    ):
        if keyword in normalized:
            return keyword
    return None


def _label_list(values: list[str]) -> str:
    return ", ".join(value.replace("_", " ") for value in values if value)
