from app.config import AppConfig
from app.generation.seed_bank import SeedExerciseBank
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.interpreter import PracticeIntentInterpreter
from app.intent.parser import IntentParser
from app.llm.factory import LangChainModelFactory
from app.onboarding.service import OnboardingInterpreter
from app.orchestrator.pipeline import PracticePipeline
from app.personalization.service import PersonalizationService
from app.persistence.repository import InMemoryLearningRepository
from app.persistence.sqlite_repository import SQLiteLearningRepository
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import LangChainVectorStore
from app.review.service import PracticeReviewService


def build_baseline_pipeline() -> PracticePipeline:
    config = AppConfig()
    repository = (
        InMemoryLearningRepository()
        if config.learning_repository_backend.lower() == "inmemory"
        else SQLiteLearningRepository(config)
    )
    vector_store = LangChainVectorStore(config)
    model_factory = LangChainModelFactory(config)

    parser = IntentParser(config)
    personalization = PersonalizationService(config)
    retrieval = RetrievalService(config, vector_store)
    seed_bank = SeedExerciseBank(config.seed_exercises_path)
    generator = ExerciseGenerationService(
        config=config,
        llm_runnable=model_factory.build_generation_runnable(),
        backend_name=model_factory.get_backend_name(),
        seed_bank=seed_bank,
    )
    validator = ExerciseValidator()
    recommendation = RecommendationService()
    review = PracticeReviewService(config)
    onboarding = OnboardingInterpreter(config)
    practice_intent = PracticeIntentInterpreter(config, parser)

    return PracticePipeline(
        config=config,
        repository=repository,
        parser=parser,
        personalization=personalization,
        retrieval=retrieval,
        generator=generator,
        validator=validator,
        recommendation=recommendation,
        review=review,
        onboarding=onboarding,
        practice_intent=practice_intent,
    )
