from app.config import AppConfig
from app.agent.learning_agent import LearningAgent
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.parser import IntentParser
from app.personalization.service import PersonalizationService
from app.persistence.repository import LearningRepository
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.schemas import GeneratedExerciseSet, SessionResult


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
        self.agent = LearningAgent(
            config=config,
            repository=repository,
            parser=parser,
            personalization=personalization,
            retrieval=retrieval,
            generator=generator,
            validator=validator,
            recommendation=recommendation,
        )

    def create_exercise_set(self, user_id: str, raw_text: str) -> GeneratedExerciseSet:
        return self.agent.create_exercise_set(user_id=user_id, raw_text=raw_text)

    def score_submission(
        self,
        user_id: str,
        topic: str,
        total_questions: int,
        correct_count: int,
    ) -> SessionResult:
        return self.agent.score_submission(
            user_id=user_id,
            topic=topic,
            total_questions=total_questions,
            correct_count=correct_count,
        )
