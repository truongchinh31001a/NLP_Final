from app.config import AppConfig
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.parser import IntentParser
from app.personalization.service import PersonalizationService
from app.persistence.repository import LearningRepository
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.schemas import GeneratedExerciseSet, PracticeRequest, SessionResult


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
    ) -> None:
        self.config = config
        self.repository = repository
        self.parser = parser
        self.personalization = personalization
        self.retrieval = retrieval
        self.generator = generator
        self.validator = validator
        self.recommendation = recommendation

    def create_exercise_set(self, user_id: str, raw_text: str) -> GeneratedExerciseSet:
        request: PracticeRequest = self.parser.parse(user_id=user_id, raw_text=raw_text)
        profile = self.repository.get_profile(user_id)
        plan = self.personalization.build_plan(request, profile)
        chunks = self.retrieval.retrieve(plan, profile.level)
        exercises = self.generator.generate(plan, chunks)
        self.validator.validate(exercises, expected_count=plan.num_questions)

        return GeneratedExerciseSet(
            request=request,
            plan=plan,
            retrieved_chunks=chunks,
            exercises=exercises,
        )

    def score_submission(
        self,
        user_id: str,
        topic: str,
        total_questions: int,
        correct_count: int,
    ) -> SessionResult:
        score = correct_count / max(total_questions, 1)
        result = SessionResult(
            user_id=user_id,
            topic=topic,
            score=score,
            correct_count=correct_count,
            total_questions=total_questions,
            weak_topics_detected=[topic] if score < 0.8 else [],
        )
        result.recommendation = self.recommendation.recommend(result)

        profile = self.repository.get_profile(user_id)
        updated_profile = self.personalization.update_profile(profile, result)

        self.repository.save_profile(updated_profile)
        self.repository.save_session_result(result)
        return result
