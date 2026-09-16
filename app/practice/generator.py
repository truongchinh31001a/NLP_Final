from app.generation.seed_bank import SeedExercise
from app.generation.service import ExerciseGenerationService
from app.retrieval.service import RetrievalService
from app.schemas import ExerciseItem, KnowledgeChunk, LearnerProfile, PracticePlan


class PracticeGenerator:
    """Practice-facing wrapper for retrieval and exercise generation."""

    def __init__(
        self,
        generator: ExerciseGenerationService,
        retrieval: RetrievalService | None = None,
    ) -> None:
        self.generator = generator
        self.retrieval = retrieval

    @property
    def backend_name(self) -> str:
        return self.generator.backend_name

    def retrieve_context(
        self,
        plan: PracticePlan,
        profile: LearnerProfile,
    ) -> list[KnowledgeChunk]:
        if self.retrieval is None:
            raise RuntimeError("PracticeGenerator requires a RetrievalService.")
        return self.retrieval.retrieve(plan, profile.level)

    def generate(
        self,
        plan: PracticePlan,
        chunks: list[KnowledgeChunk],
    ) -> list[ExerciseItem]:
        return self.generator.generate(plan, chunks)

    def generate_from_seed_bank(
        self,
        *,
        plan: PracticePlan,
        chunks: list[KnowledgeChunk],
        seed_examples: list[SeedExercise] | None = None,
    ) -> list[ExerciseItem] | None:
        return self.generator.generate_from_seed_bank(
            plan=plan,
            chunks=chunks,
            seed_examples=seed_examples,
        )


__all__ = ["PracticeGenerator"]
