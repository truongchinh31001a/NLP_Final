from app.config import AppConfig
from app.agent.learning_agent import LearningAgent
from app.agent.workflow_graph import LearningWorkflowGraph
from app.activities.practice_service import (
    PracticeActivityGeneration,
    PracticeActivityService,
    PracticeActivitySubmission,
)
from app.conversation.router import ConversationRouter
from app.conversation.schemas import ConversationRoute, ConversationTurnResult
from app.conversation.service import ConversationService
from app.diagnosis.service import ErrorDiagnosisService
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.interpreter import (
    PracticeIntentInterpretation,
    PracticeIntentInterpreter,
)
from app.intent.parser import IntentParser
from app.onboarding.service import OnboardingInterpreter, OnboardingInterpretation
from app.personalization.service import (
    PersonalizationService,
    ProfileUpdateService,
    ProgressiveProfileService,
    ProgressService,
)
from app.persistence.repository import LearningRepository
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.review.service import ConversationReviewService, PracticeReviewService
from app.schemas import (
    ActivityRecommendation,
    ConversationTurnContext,
    GeneratedExerciseSet,
    PracticeRequest,
    SessionResult,
    SubmittedAnswer,
)
from app.tutor.service import GeneralTutorService, TutorExplainService, TutorResponseLLM


class PracticePipeline:
    def __init__(
        self,
        config: AppConfig,
        repository: LearningRepository,
        parser: IntentParser,
        personalization: PersonalizationService,
        retrieval: RetrievalService,
        generator: ExerciseGenerationService,
        validator: ExerciseValidator,
        recommendation: RecommendationService,
        review: PracticeReviewService,
        diagnosis: ErrorDiagnosisService,
        onboarding: OnboardingInterpreter,
        practice_intent: PracticeIntentInterpreter,
        conversation_router: ConversationRouter | None = None,
        tutor_response_llm: TutorResponseLLM | None = None,
    ) -> None:
        self.config = config
        self.repository = repository
        self.parser = parser
        self.personalization = personalization
        self.retrieval = retrieval
        self.generator = generator
        self.validator = validator
        self.recommendation = recommendation
        self.review = review
        self.diagnosis = diagnosis
        self.onboarding = onboarding
        self.practice_intent = practice_intent
        self.conversation_router = conversation_router or ConversationRouter(
            config,
            practice_intent,
        )
        self.conversation_service = ConversationService(
            config,
            repository,
            self.conversation_router,
        )
        self.workflow_graph = LearningWorkflowGraph()
        self.agent = LearningAgent(
            config=config,
            repository=repository,
            parser=parser,
            personalization=personalization,
            retrieval=retrieval,
            generator=generator,
            validator=validator,
            recommendation=recommendation,
            review=review,
            diagnosis=diagnosis,
        )
        self.practice_activity_service = PracticeActivityService(
            config=config,
            repository=repository,
            agent=self.agent,
        )
        self.conversation_service.practice_activity_service = (
            self.practice_activity_service
        )
        self.conversation_service.explain_service = TutorExplainService(
            config=config,
            retrieval=retrieval,
            response_llm=tutor_response_llm,
        )
        self.conversation_service.review_service = ConversationReviewService(
            repository,
        )
        self.conversation_service.progress_service = ProgressService(repository)
        self.conversation_service.profile_update_service = ProfileUpdateService(
            config,
            repository,
        )
        self.conversation_service.progressive_profile_service = (
            ProgressiveProfileService(
                repository,
                onboarding,
            )
        )
        self.conversation_service.general_tutor_service = GeneralTutorService(
            config=config,
            response_llm=tutor_response_llm,
        )

    def create_exercise_set(
        self,
        user_id: str,
        raw_text: str,
        request_overrides: PracticeRequest | None = None,
        activity_id: str | None = None,
    ) -> GeneratedExerciseSet:
        return self.agent.create_exercise_set(
            user_id=user_id,
            raw_text=raw_text,
            request_overrides=request_overrides,
            activity_id=activity_id,
        )

    def create_practice_activity(
        self,
        *,
        user_id: str,
        raw_text: str,
        conversation_id: str | None = None,
        request_overrides: PracticeRequest | None = None,
        skip_request_parser: bool = False,
    ) -> PracticeActivityGeneration:
        return self.practice_activity_service.create_practice_activity(
            user_id=user_id,
            raw_text=raw_text,
            conversation_id=conversation_id,
            request_overrides=request_overrides,
            skip_request_parser=skip_request_parser,
        )

    def submit_practice_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        answers: list[SubmittedAnswer],
    ) -> PracticeActivitySubmission:
        return self.practice_activity_service.submit_practice_activity(
            user_id=user_id,
            activity_id=activity_id,
            answers=answers,
        )

    def score_submission(
        self,
        user_id: str,
        generation_run_id: str,
        answers: list[SubmittedAnswer],
    ) -> SessionResult:
        return self.agent.score_submission(
            user_id=user_id,
            generation_run_id=generation_run_id,
            answers=answers,
        )

    def score_legacy_submission(
        self,
        *,
        user_id: str,
        generation_run_id: str,
        answers: list[SubmittedAnswer],
    ) -> SessionResult:
        generated = self.repository.get_generated_exercise_set(
            user_id,
            generation_run_id,
        )
        if generated is not None and generated.activity_id:
            return self.submit_practice_activity(
                user_id=user_id,
                activity_id=generated.activity_id,
                answers=answers,
            ).result
        return self.score_submission(
            user_id=user_id,
            generation_run_id=generation_run_id,
            answers=answers,
        )

    def list_recommendations(
        self,
        *,
        user_id: str,
        limit: int = 5,
    ) -> list[ActivityRecommendation]:
        return self.recommendation.list_current(
            user_id=user_id,
            repository=self.repository,
            limit=limit,
        )

    def accept_recommendation(
        self,
        *,
        user_id: str,
        recommendation_id: str,
        conversation_id: str | None = None,
    ) -> tuple[ActivityRecommendation, PracticeActivityGeneration]:
        recommendation = self.recommendation.resolve_current(
            user_id=user_id,
            repository=self.repository,
            recommendation_id=recommendation_id,
        )
        request = self.recommendation.to_practice_request(recommendation)
        generated = self.create_practice_activity(
            user_id=user_id,
            raw_text=recommendation.prompt,
            conversation_id=conversation_id or recommendation.conversation_id,
            request_overrides=request,
            skip_request_parser=True,
        )
        return recommendation, generated

    def interpret_onboarding_answer(
        self,
        *,
        message: str,
        current_answers: dict,
        current_step_key: str | None,
    ) -> OnboardingInterpretation:
        return self.onboarding.interpret(
            message=message,
            current_answers=current_answers,
            current_step_key=current_step_key,
        )

    def interpret_practice_request(
        self,
        *,
        user_id: str,
        message: str,
    ) -> PracticeIntentInterpretation:
        profile = self.repository.get_profile(user_id)
        chat_resume = self.repository.get_chat_resume(user_id, limit=12)
        weak_topics = [
            topic
            for topic, _score in sorted(
                profile.weak_topics.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:5]
        ]
        recent_chat_messages = [
            {
                "role": str(chat_message.get("role") or ""),
                "content": str(chat_message.get("content") or "")[:500],
            }
            for chat_message in chat_resume.get("messages", [])[-8:]
            if isinstance(chat_message, dict)
        ]
        return self.practice_intent.interpret(
            user_id=user_id,
            message=message,
            profile_context={
                "level": profile.level,
                "goals": profile.goals,
                "preferred_difficulty": profile.preferred_difficulty,
                "preferred_num_questions": profile.preferred_num_questions,
                "weak_topics": weak_topics,
                "chat_memory_summary": chat_resume.get("memory_summary", ""),
                "chat_extracted_facts": chat_resume.get("extracted_facts", {}),
                "recent_chat_messages": recent_chat_messages,
            },
        )

    def build_conversation_turn_context(
        self,
        *,
        user_id: str,
        conversation_id: str | None = None,
        limit: int = 12,
    ) -> ConversationTurnContext:
        chat_resume = self.repository.get_chat_resume(
            user_id,
            limit=limit,
            session_id=conversation_id,
        )
        return self.conversation_service.build_turn_context(
            user_id=user_id,
            resume=chat_resume,
        )

    def route_conversation_turn(
        self,
        *,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> ConversationRoute:
        context = self.build_conversation_turn_context(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return self.conversation_router.route(
            message=message,
            context=context,
        )

    def create_conversation(self, user_id: str) -> dict:
        return self.conversation_service.create_conversation(user_id)

    def list_conversations(self, user_id: str, limit: int = 20) -> dict:
        return self.conversation_service.list_conversations(user_id, limit=limit)

    def get_conversation(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 24,
    ) -> dict:
        return self.conversation_service.get_conversation(
            user_id,
            conversation_id,
            limit=limit,
        )

    def handle_conversation_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message: str,
        metadata: dict | None = None,
    ) -> ConversationTurnResult:
        return self.conversation_service.handle_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            metadata=metadata,
        )
