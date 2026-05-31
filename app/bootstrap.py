from app.config import AppConfig
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.parser import IntentParser
from app.llm.factory import LangChainModelFactory
from app.orchestrator.pipeline import PracticePipeline
from app.personalization.service import PersonalizationService
from app.persistence.repository import InMemoryLearningRepository
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import LangChainVectorStore


def build_baseline_pipeline() -> PracticePipeline:
    config = AppConfig()
    repository = InMemoryLearningRepository()
    vector_store = LangChainVectorStore(config)
    model_factory = LangChainModelFactory(config)

    parser = IntentParser(config)
    personalization = PersonalizationService(config)
    retrieval = RetrievalService(config, vector_store)
    generator = ExerciseGenerationService(
        llm_runnable=model_factory.build_generation_runnable(),
        backend_name=model_factory.get_backend_name(),
    )
    validator = ExerciseValidator()
    recommendation = RecommendationService()

    return PracticePipeline(
        config=config,
        repository=repository,
        parser=parser,
        personalization=personalization,
        retrieval=retrieval,
        generator=generator,
        validator=validator,
        recommendation=recommendation,
    )
