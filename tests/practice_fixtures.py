from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableLambda

from app.config import AppConfig
from app.diagnosis.service import ErrorDiagnosisService
from app.generation.seed_bank import SeedExerciseBank
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.interpreter import PracticeIntentInterpreter
from app.intent.parser import IntentParser
from app.orchestrator.pipeline import PracticePipeline
from app.persistence.repository import InMemoryLearningRepository
from app.personalization.service import PersonalizationService
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.review.service import PracticeReviewService
from app.onboarding.service import OnboardingInterpreter
from app.schemas import KnowledgeChunk


class StaticVectorStore:
    def search(
        self,
        topic: str,
        level: str,
        limit: int,
        subtopic: str | None = None,
    ) -> list[KnowledgeChunk]:
        return [
            KnowledgeChunk(
                chunk_id="fixture-passive-voice",
                topic=topic,
                level=level,
                content=(
                    "Passive voice uses a form of be plus a past participle. "
                    "The object of the active sentence becomes the subject."
                ),
                source="test-fixture",
                metadata={"subtopic": subtopic or "present_simple_passive"},
            )
        ][:limit]


def build_offline_practice_pipeline() -> PracticePipeline:
    root = Path(__file__).resolve().parents[1]
    config = AppConfig(
        default_num_questions=2,
        learning_repository_backend="inmemory",
        llm_backend="none",
        seed_exercises_path=str(root / "data" / "processed" / "seed_exercises.json"),
        seed_first_generation=True,
        retrieval_top_k=1,
    )
    parser = IntentParser(config)
    generator = ExerciseGenerationService(
        config=config,
        llm_runnable=RunnableLambda(_raise_if_llm_is_used),
        backend_name="test-seed-bank",
        seed_bank=SeedExerciseBank(config.seed_exercises_path),
    )

    return PracticePipeline(
        config=config,
        repository=InMemoryLearningRepository(),
        parser=parser,
        personalization=PersonalizationService(config),
        retrieval=RetrievalService(config, StaticVectorStore()),
        generator=generator,
        validator=ExerciseValidator(),
        recommendation=RecommendationService(),
        review=PracticeReviewService(config),
        diagnosis=ErrorDiagnosisService(),
        onboarding=OnboardingInterpreter(config),
        practice_intent=PracticeIntentInterpreter(config, parser),
    )


def _raise_if_llm_is_used(_: Any) -> str:
    raise AssertionError("Offline practice fixture must use the seed bank, not an LLM.")
