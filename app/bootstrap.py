from app.config import AppConfig
from app.diagnosis.service import ErrorDiagnosisService
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
    repository = _build_repository(config)
    vector_store = _build_vector_store(config)
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
    diagnosis = ErrorDiagnosisService()
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
        diagnosis=diagnosis,
        onboarding=onboarding,
        practice_intent=practice_intent,
    )


def _build_repository(config: AppConfig):
    backend = config.learning_repository_backend.strip().lower()
    if backend == "inmemory":
        return InMemoryLearningRepository()
    if backend in {"postgres", "postgresql"}:
        from app.persistence.postgres_repository import PostgreSQLLearningRepository

        return PostgreSQLLearningRepository(config)
    if backend == "sqlite":
        return SQLiteLearningRepository(config)
    raise ValueError(
        "Unsupported LEARNING_REPOSITORY_BACKEND. Use sqlite, inmemory, or postgres."
    )


def _build_vector_store(config: AppConfig):
    backend = config.vector_store_backend.strip().lower()
    if backend == "pgvector":
        from app.retrieval.pgvector_store import PgVectorKnowledgeStore

        return PgVectorKnowledgeStore(config)
    return LangChainVectorStore(config)
