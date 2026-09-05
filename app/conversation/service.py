from dataclasses import asdict
from typing import Any

from app.activities.practice_service import (
    PracticeActivityGeneration,
    PracticeActivityService,
)
from app.activities.literacy_service import (
    LiteracyActivityGeneration,
    ReadingActivityService,
    WritingActivityService,
)
from app.config import AppConfig
from app.conversation.router import ConversationRouter
from app.conversation.schemas import ConversationRoute, ConversationTurnResult
from app.persistence.repository import LearningRepository
from app.personalization.service import (
    ProfileUpdateService,
    ProgressiveProfileService,
    ProgressService,
)
from app.review.service import ConversationReviewService
from app.schemas import (
    ConversationIntent,
    ConversationTurnContext,
    LearnerProfile,
    LearningActivity,
    LearningActivityStatus,
    PendingClarification,
)
from app.tutor.service import (
    GeneralTutorService,
    TutorCapabilityResult,
    TutorExplainService,
)


class ConversationService:
    """Canonical conversation facade backed by existing chat sessions."""

    def __init__(
        self,
        config: AppConfig,
        repository: LearningRepository,
        router: ConversationRouter,
    ) -> None:
        self.config = config
        self.repository = repository
        self.router = router
        self.practice_activity_service: PracticeActivityService | None = None
        self.explain_service: TutorExplainService | None = None
        self.review_service: ConversationReviewService | None = None
        self.progress_service: ProgressService | None = None
        self.profile_update_service: ProfileUpdateService | None = None
        self.progressive_profile_service: ProgressiveProfileService | None = None
        self.general_tutor_service: GeneralTutorService | None = None
        self.reading_activity_service: ReadingActivityService | None = None
        self.writing_activity_service: WritingActivityService | None = None

    def create_conversation(self, user_id: str) -> dict[str, Any]:
        resume = self.repository.create_chat_session(user_id)
        return self._conversation_detail(user_id, resume)

    def list_conversations(self, user_id: str, limit: int = 20) -> dict[str, Any]:
        payload = self.repository.list_chat_sessions(user_id, limit=limit)
        return {
            "conversations": [
                self._conversation_summary(item)
                for item in payload.get("sessions", [])
                if isinstance(item, dict)
            ],
        }

    def get_conversation(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 24,
    ) -> dict[str, Any]:
        resume = self.repository.get_chat_resume(
            user_id,
            limit=limit,
            session_id=conversation_id,
        )
        return self._conversation_detail(user_id, resume)

    def handle_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationTurnResult:
        before_resume = self.repository.get_chat_resume(
            user_id,
            session_id=conversation_id,
        )
        pending_clarification = self._stored_pending_clarification(
            user_id,
            conversation_id,
        ) or self._latest_pending_clarification(
            before_resume.get("messages", []),
        )
        active_intent = self._latest_assistant_intent(
            before_resume.get("messages", []),
        )
        user_saved = self.repository.save_chat_message(
            user_id=user_id,
            role="user",
            content=message,
            session_id=conversation_id,
            metadata={
                "conversation_api": True,
                "client_metadata": metadata or {},
            },
            update_memory=True,
        )
        profile_enrichment: dict[str, Any] = {}
        if self.progressive_profile_service is not None:
            profile_enrichment = self.progressive_profile_service.enrich(
                user_id=user_id,
                message=message,
                conversation_id=conversation_id,
            )
        after_resume = self.repository.get_chat_resume(
            user_id,
            limit=12,
            session_id=conversation_id,
        )
        context = self.build_turn_context(
            user_id=user_id,
            resume=after_resume,
            pending_clarification=pending_clarification,
            active_intent=active_intent,
        )
        route = self.router.route(message=message, context=context)
        if self.profile_update_service is None:
            self._apply_profile_enrichment(user_id, route)

        capability = self._handle_route_capability(
            user_id=user_id,
            message=message,
            route=route,
            context=context,
        )
        assistant_reply = capability.assistant_reply
        ui_action = capability.ui_action
        activity = capability.activity
        assistant_saved = self.repository.save_chat_message(
            user_id=user_id,
            role="assistant",
            content=assistant_reply,
            session_id=conversation_id,
            metadata=self._assistant_metadata(
                route,
                ui_action,
                activity,
                capability.metadata,
                profile_enrichment,
            ),
            update_memory=False,
        )
        self._save_pending_clarification(
            user_id,
            str(user_saved["session_id"]),
            route.pending_clarification,
        )

        return ConversationTurnResult(
            conversation_id=str(user_saved["session_id"]),
            message=dict(user_saved["message"]),
            intent=route.intent,
            assistant_reply=assistant_reply,
            pending_clarification=route.pending_clarification,
            activity=activity,
            ui_action=ui_action,
            assistant_message=dict(assistant_saved["message"]),
            route=route,
        )

    def build_turn_context(
        self,
        *,
        user_id: str,
        resume: dict[str, Any],
        pending_clarification: PendingClarification | None = None,
        active_intent: ConversationIntent | None = None,
    ) -> ConversationTurnContext:
        conversation_id = str(resume.get("session_id") or "")
        profile = self.repository.get_profile(user_id)
        latest_activity = self.repository.get_latest_learning_activity(
            user_id,
            conversation_id,
        )
        latest_reviewable_activity = self.repository.get_latest_learning_activity(
            user_id,
            conversation_id,
            statuses=[
                LearningActivityStatus.SUBMITTED,
                LearningActivityStatus.GRADED,
                LearningActivityStatus.COMPLETED,
            ],
        )
        if pending_clarification is None:
            pending_clarification = self._clarification_from_payload(
                resume.get("pending_clarification"),
            )
        messages = [
            {
                "role": str(item.get("role") or ""),
                "content": str(item.get("content") or "")[:500],
                "created_at": item.get("created_at"),
                "metadata": item.get("metadata") if isinstance(item, dict) else {},
            }
            for item in resume.get("messages", [])
            if isinstance(item, dict)
        ]
        extracted_facts = resume.get("extracted_facts", {})
        return ConversationTurnContext(
            conversation_id=conversation_id,
            learner_id=user_id,
            profile=profile,
            recent_messages=messages,
            memory_summary=str(resume.get("memory_summary") or ""),
            active_intent=active_intent,
            pending_clarification=pending_clarification,
            active_activity=latest_activity,
            recent_context={
                "chat_extracted_facts": (
                    extracted_facts if isinstance(extracted_facts, dict) else {}
                ),
                "latest_activity": latest_activity,
                "latest_reviewable_activity": latest_reviewable_activity,
                "recent_activity_ids": [
                    activity.activity_id
                    for activity in (latest_activity, latest_reviewable_activity)
                    if activity is not None
                ],
            },
        )

    def _conversation_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "conversation_id": item.get("session_id"),
            "title": item.get("title") or "Phien chat moi",
            "preview": item.get("preview") or "",
            "message_count": item.get("message_count") or 0,
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }

    def _conversation_detail(
        self,
        user_id: str,
        resume: dict[str, Any],
    ) -> dict[str, Any]:
        conversation_id = str(resume.get("session_id") or "")
        latest_activity = self.repository.get_latest_learning_activity(
            user_id,
            conversation_id,
        )
        pending = self._clarification_from_payload(
            resume.get("pending_clarification"),
        ) or self._latest_pending_clarification(resume.get("messages", []))
        return {
            "conversation_id": conversation_id,
            "has_history": bool(resume.get("has_history")),
            "memory_summary": resume.get("memory_summary") or "",
            "extracted_facts": resume.get("extracted_facts") or {},
            "suggested_next_question": resume.get("suggested_next_question") or "",
            "messages": resume.get("messages") or [],
            "pending_clarification": self._clarification_payload(pending),
            "active_activity": self._activity_payload(latest_activity),
        }

    def _assistant_reply(self, route: ConversationRoute) -> str:
        if route.needs_clarification and route.clarification_question:
            return route.clarification_question

        if route.intent == ConversationIntent.PRACTICE:
            return route.assistant_reply or (
                "Minh da hieu yeu cau luyen tap. "
                "Minh se chuan bi bai practice theo dung thong tin ban vua gui."
            )
        if route.intent == ConversationIntent.EXPLAIN:
            concept = str(route.slots.get("concept") or "phan ngu phap nay")
            return (
                f"Minh se giai thich {concept.replace('_', ' ')} theo tung buoc. "
                "Minh se uu tien vi du ngan va dau hieu nhan biet de ban de ap dung."
            )
        if route.intent == ConversationIntent.REVIEW:
            question_number = route.slots.get("question_number")
            suffix = f" cau {question_number}" if question_number else ""
            return f"Minh se xem lai{suffix} dua tren bai gan nhat cua ban."
        if route.intent == ConversationIntent.PROGRESS:
            return "Minh se doc tien do va diem yeu hien tai cua ban."
        if route.intent == ConversationIntent.PROFILE_UPDATE:
            return "Minh da ghi nhan dieu chinh cho cac bai tiep theo."
        return "Minh dang nghe. Ban muon hoc, hoi ly thuyet, hay luyen bai nao?"

    def _handle_route_capability(
        self,
        *,
        user_id: str,
        message: str,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> TutorCapabilityResult:
        if route.needs_clarification:
            return TutorCapabilityResult(
                assistant_reply=self._assistant_reply(route),
                ui_action=self._ui_action(route),
                activity=self._activity_payload_for_route(route, context),
            )
        if (
            route.intent == ConversationIntent.PRACTICE
            and self.practice_activity_service is not None
        ):
            generated = self.practice_activity_service.create_practice_activity(
                user_id=user_id,
                raw_text=message,
                conversation_id=context.conversation_id,
                request_overrides=route.practice_request,
            )
            return TutorCapabilityResult(
                assistant_reply=route.assistant_reply
                or "Minh da tao bai luyen tap cho ban.",
                ui_action="practice.start",
                activity=self._practice_generation_payload(generated),
                metadata={
                    "activity_id": generated.activity.activity_id,
                    "generation_run_id": generated.generated.generation_run_id,
                },
            )
        if (
            route.intent == ConversationIntent.READING
            and self.reading_activity_service is not None
        ):
            generated = self.reading_activity_service.create_reading_activity(
                user_id=user_id,
                raw_text=message,
                conversation_id=context.conversation_id,
                topic=str(route.slots.get("topic") or "") or None,
            )
            return TutorCapabilityResult(
                assistant_reply=route.assistant_reply
                or "Minh da chuan bi mot bai doc ngan cho ban.",
                ui_action="reading.start",
                activity=self._literacy_generation_payload(generated),
                metadata={
                    "activity_id": generated.activity.activity_id,
                    "generation_run_id": (
                        generated.generated.generation_run_id
                        if generated.generated is not None
                        else None
                    ),
                },
            )
        if (
            route.intent == ConversationIntent.WRITING
            and self.writing_activity_service is not None
        ):
            generated = self.writing_activity_service.create_writing_activity(
                user_id=user_id,
                raw_text=message,
                conversation_id=context.conversation_id,
                topic=str(route.slots.get("topic") or "") or None,
            )
            return TutorCapabilityResult(
                assistant_reply=route.assistant_reply
                or "Minh da mo mot bai viet ngan de minh sua theo rubric.",
                ui_action="writing.start",
                activity=self._literacy_generation_payload(generated),
                metadata={"activity_id": generated.activity.activity_id},
            )
        if route.intent == ConversationIntent.EXPLAIN and self.explain_service is not None:
            return self.explain_service.explain(route=route, context=context)
        if route.intent == ConversationIntent.REVIEW and self.review_service is not None:
            return self.review_service.review(route=route, context=context)
        if (
            route.intent == ConversationIntent.PROGRESS
            and self.progress_service is not None
        ):
            return self.progress_service.summarize(
                user_id=user_id,
                route=route,
                context=context,
            )
        if (
            route.intent == ConversationIntent.PROFILE_UPDATE
            and self.profile_update_service is not None
        ):
            return self.profile_update_service.apply(
                user_id=user_id,
                route=route,
                message=message,
            )
        if (
            route.intent == ConversationIntent.GENERAL
            and self.general_tutor_service is not None
        ):
            return self.general_tutor_service.respond(route=route, context=context)
        return TutorCapabilityResult(
            assistant_reply=self._assistant_reply(route),
            ui_action=self._ui_action(route),
            activity=self._activity_payload_for_route(route, context),
        )

    def _ui_action(self, route: ConversationRoute) -> str:
        if route.needs_clarification:
            return "clarification.ask"
        actions = {
            ConversationIntent.PRACTICE: "practice.interpret",
            ConversationIntent.READING: "reading.start",
            ConversationIntent.WRITING: "writing.start",
            ConversationIntent.EXPLAIN: "explain.respond",
            ConversationIntent.REVIEW: "review.open",
            ConversationIntent.PROGRESS: "progress.open",
            ConversationIntent.PROFILE_UPDATE: "profile.update",
            ConversationIntent.GENERAL: "conversation.reply",
        }
        return actions[route.intent]

    def _activity_payload_for_route(
        self,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> dict[str, Any] | None:
        if route.slots.get("activity_id") and context.active_activity is not None:
            return self._activity_payload(context.active_activity)
        return self._activity_payload(context.active_activity)

    def _activity_payload(
        self,
        activity: LearningActivity | None,
    ) -> dict[str, Any] | None:
        if activity is None:
            return None
        return self._json_safe(asdict(activity))

    def _practice_generation_payload(
        self,
        generated: PracticeActivityGeneration,
    ) -> dict[str, Any]:
        return self._json_safe(
            {
                **asdict(generated.activity),
                "request": asdict(generated.generated.request),
                "plan": asdict(generated.generated.plan),
                "exercises": [
                    asdict(exercise) for exercise in generated.generated.exercises
                ],
                "recommendation": generated.recommendation,
            }
        )

    def _literacy_generation_payload(
        self,
        generated: LiteracyActivityGeneration,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **asdict(generated.activity),
            "recommendation": generated.recommendation,
            "next_activity_suggestion": None,
        }
        if generated.generated is not None:
            payload.update(
                {
                    "request": asdict(generated.generated.request),
                    "plan": asdict(generated.generated.plan),
                    "exercises": [
                        asdict(exercise)
                        for exercise in generated.generated.exercises
                    ],
                }
            )
        else:
            payload.update({"request": None, "plan": None, "exercises": []})
        return self._json_safe(payload)

    def _assistant_metadata(
        self,
        route: ConversationRoute,
        ui_action: str,
        activity: dict[str, Any] | None,
        capability_metadata: dict[str, Any] | None = None,
        profile_enrichment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "conversation_api": True,
            "intent": route.intent.value,
            "ui_action": ui_action,
            "route": self._route_payload(route),
            "pending_clarification": self._clarification_payload(
                route.pending_clarification,
            ),
            "activity": activity,
            "capability": self._json_safe(capability_metadata or {}),
            "profile_enrichment": self._json_safe(profile_enrichment or {}),
        }

    def _route_payload(self, route: ConversationRoute) -> dict[str, Any]:
        return {
            "intent": route.intent.value,
            "confidence": route.confidence,
            "source": route.source,
            "reason": route.reason,
            "slots": self._json_safe(route.slots),
            "missing_slots": (
                route.pending_clarification.missing_fields
                if route.pending_clarification is not None
                else []
            ),
            "referenced_activity_id": (
                str(route.slots["activity_id"])
                if route.slots.get("activity_id")
                else None
            ),
            "needs_clarification": route.needs_clarification,
            "clarification_question": route.clarification_question,
        }

    def _latest_pending_clarification(
        self,
        messages: object,
    ) -> PendingClarification | None:
        latest_assistant = self._latest_assistant_metadata(messages)
        if latest_assistant is None:
            return None
        return self._clarification_from_payload(
            latest_assistant.get("pending_clarification"),
        )

    def _stored_pending_clarification(
        self,
        user_id: str,
        conversation_id: str,
    ) -> PendingClarification | None:
        try:
            return self.repository.get_pending_clarification(user_id, conversation_id)
        except LookupError:
            return None

    def _save_pending_clarification(
        self,
        user_id: str,
        conversation_id: str,
        clarification: PendingClarification | None,
    ) -> None:
        try:
            self.repository.save_pending_clarification(
                user_id,
                conversation_id,
                clarification,
            )
        except LookupError:
            return

    def _latest_assistant_intent(
        self,
        messages: object,
    ) -> ConversationIntent | None:
        latest_assistant = self._latest_assistant_metadata(messages)
        if latest_assistant is None:
            return None
        intent = latest_assistant.get("intent")
        try:
            return ConversationIntent(str(intent))
        except ValueError:
            return None

    def _latest_assistant_metadata(
        self,
        messages: object,
    ) -> dict[str, Any] | None:
        if not isinstance(messages, list):
            return None
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            metadata = message.get("metadata")
            if isinstance(metadata, dict):
                return metadata
        return None

    def _clarification_payload(
        self,
        clarification: PendingClarification | None,
    ) -> dict[str, Any] | None:
        if clarification is None:
            return None
        return {
            "pending_intent": clarification.pending_intent.value,
            "missing_fields": list(clarification.missing_fields),
            "collected_slots": self._json_safe(clarification.collected_slots),
            "question": clarification.question,
        }

    def _clarification_from_payload(
        self,
        payload: object,
    ) -> PendingClarification | None:
        if not isinstance(payload, dict):
            return None
        try:
            pending_intent = ConversationIntent(str(payload.get("pending_intent")))
        except ValueError:
            return None
        missing_fields = payload.get("missing_fields")
        collected_slots = payload.get("collected_slots")
        return PendingClarification(
            pending_intent=pending_intent,
            missing_fields=[
                str(item)
                for item in (missing_fields if isinstance(missing_fields, list) else [])
            ],
            collected_slots=(
                dict(collected_slots) if isinstance(collected_slots, dict) else {}
            ),
            question=str(payload.get("question") or ""),
        )

    def _apply_profile_enrichment(
        self,
        user_id: str,
        route: ConversationRoute,
    ) -> None:
        if route.intent != ConversationIntent.PROFILE_UPDATE:
            return

        profile = self.repository.get_profile(user_id)
        changed = False
        preferred_num_questions = route.slots.get("preferred_num_questions")
        if isinstance(preferred_num_questions, int):
            profile.preferred_num_questions = preferred_num_questions
            changed = True

        preferred_difficulty = route.slots.get("preferred_difficulty")
        if isinstance(preferred_difficulty, str):
            profile.preferred_difficulty = preferred_difficulty
            changed = True
        elif route.slots.get("difficulty_delta") in {"harder", "easier"}:
            profile.preferred_difficulty = self._shift_difficulty(
                profile,
                str(route.slots["difficulty_delta"]),
            )
            changed = True

        if changed:
            self.repository.save_profile(profile)

    def _shift_difficulty(self, profile: LearnerProfile, direction: str) -> str:
        levels = ["easy", "medium", "hard"]
        current = profile.preferred_difficulty or self.config.default_difficulty
        index = levels.index(current) if current in levels else 0
        if direction == "harder":
            return levels[min(index + 1, len(levels) - 1)]
        return levels[max(index - 1, 0)]

    def _json_safe(self, value: Any) -> Any:
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value
