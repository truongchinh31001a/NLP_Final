from app.config import AppConfig
from app.agent.learning_agent import LearningAgent
from app.agent.workflow_graph import LearningWorkflowGraph
from app.diagnosis.service import ErrorDiagnosisService
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.interpreter import (
    PracticeIntentInterpretation,
    PracticeIntentInterpreter,
)
from app.intent.parser import IntentParser
from app.onboarding.service import OnboardingInterpreter, OnboardingInterpretation
from app.personalization.service import PersonalizationService
from app.persistence.repository import LearningRepository
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.review.service import PracticeReviewService
from app.schemas import GeneratedExerciseSet, PracticeRequest, SessionResult, SubmittedAnswer


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

    def create_exercise_set(
        self,
        user_id: str,
        raw_text: str,
        request_overrides: PracticeRequest | None = None,
    ) -> GeneratedExerciseSet:
        return self.agent.create_exercise_set(
            user_id=user_id,
            raw_text=raw_text,
            request_overrides=request_overrides,
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
