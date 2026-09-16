import unittest

from app.config import AppConfig
from app.generation.validator import ExerciseValidator
from app.personalization.service import PersonalizationService
from app.practice import (
    PracticeGenerator,
    PracticeGrader,
    PracticePlanner,
    PracticeService,
    PracticeValidator,
)
from app.schemas import (
    ExerciseItem,
    ExerciseOption,
    KnowledgeChunk,
    LearnerProfile,
    PracticeRequest,
)


class PracticePackageTests(unittest.TestCase):
    def test_practice_wrappers_delegate_to_existing_modules(self) -> None:
        config = AppConfig(llm_backend="none", default_num_questions=1)
        profile = LearnerProfile(user_id="learner", level="beginner")
        request = PracticeRequest(
            user_id="learner",
            raw_text="practice passive voice",
            topic="grammar",
            num_questions=1,
        )
        plan = PracticePlanner(PersonalizationService(config)).build_plan(
            request,
            profile,
        )
        generator = PracticeGenerator(
            generator=FakeGenerator(),
            retrieval=FakeRetrieval(),
        )

        chunks = generator.retrieve_context(plan, profile)
        exercises = generator.generate(plan, chunks)
        PracticeValidator(ExerciseValidator()).validate(
            exercises,
            expected_count=1,
        )

        self.assertEqual(generator.backend_name, "fake-generator")
        self.assertEqual(chunks[0].topic, "grammar")
        self.assertTrue(issubclass(PracticeService, object))
        self.assertTrue(issubclass(PracticeGrader, object))


class FakeRetrieval:
    def retrieve(self, plan, learner_level):
        return [
            KnowledgeChunk(
                chunk_id="chunk-1",
                topic=plan.topic,
                level=learner_level,
                content="Passive voice uses be plus a past participle.",
                source="unit-test",
            )
        ]


class FakeGenerator:
    backend_name = "fake-generator"

    def generate(self, plan, chunks):
        _ = chunks
        return [
            ExerciseItem(
                exercise_id="q1",
                exercise_type=plan.exercise_type,
                topic=plan.topic,
                difficulty=plan.difficulty,
                skill="grammar",
                subtopic="passive_voice",
                error_tag="word_order",
                question_text="Choose the passive sentence.",
                options=[
                    ExerciseOption("A", "The cake is made by Minh.", True),
                    ExerciseOption("B", "Minh makes the cake."),
                    ExerciseOption("C", "Minh is cake made."),
                    ExerciseOption("D", "The cake Minh made."),
                ],
                correct_answer="A",
                explanation="'Is made' is passive voice.",
            )
        ]

    def generate_from_seed_bank(self, **kwargs):
        _ = kwargs
        return None


if __name__ == "__main__":
    unittest.main()
