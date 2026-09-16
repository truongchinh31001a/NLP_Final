import unittest

from app.activities.service import ActivityService
from app.persistence.repository import InMemoryLearningRepository
from app.schemas import LearningActivityStatus, LearningActivityType


class ActivityServiceTests(unittest.TestCase):
    def test_create_and_transition_activity_lifecycle(self) -> None:
        repository = InMemoryLearningRepository()
        service = ActivityService(repository)

        activity = service.create_activity(
            user_id="learner",
            activity_type=LearningActivityType.PRACTICE,
            target_skills=["grammar.passive_voice"],
            difficulty="easy",
            metadata={"source": "unit-test"},
        )

        self.assertTrue(activity.activity_id)
        self.assertEqual(activity.status, LearningActivityStatus.CREATED)
        self.assertEqual(activity.learner_id, "learner")
        self.assertEqual(activity.target_skills, ["grammar.passive_voice"])
        self.assertEqual(activity.metadata["source"], "unit-test")

        activity = service.start_generation(
            user_id="learner",
            activity_id=activity.activity_id,
        )
        self.assertEqual(activity.status, LearningActivityStatus.GENERATING)

        activity = service.mark_ready(
            user_id="learner",
            activity_id=activity.activity_id,
            metadata={"generated_by": "fixture"},
        )
        self.assertEqual(activity.status, LearningActivityStatus.READY)
        self.assertEqual(activity.metadata["generated_by"], "fixture")

        activity = service.start_activity(
            user_id="learner",
            activity_id=activity.activity_id,
        )
        self.assertEqual(activity.status, LearningActivityStatus.IN_PROGRESS)
        self.assertIsNotNone(activity.started_at)

        activity = service.submit_activity(
            user_id="learner",
            activity_id=activity.activity_id,
            metadata={"answers_count": 2},
        )
        self.assertEqual(activity.status, LearningActivityStatus.SUBMITTED)
        self.assertEqual(activity.metadata["answers_count"], 2)
        self.assertIsNotNone(activity.submitted_at)

        activity = service.grade_activity(
            user_id="learner",
            activity_id=activity.activity_id,
        )
        self.assertEqual(activity.status, LearningActivityStatus.GRADED)

        activity = service.complete_activity(
            user_id="learner",
            activity_id=activity.activity_id,
        )
        self.assertEqual(activity.status, LearningActivityStatus.COMPLETED)
        self.assertIsNotNone(activity.completed_at)

        events = repository.list_activity_state_events(
            "learner",
            activity.activity_id,
        )
        self.assertEqual(events[0].to_status, LearningActivityStatus.CREATED)
        self.assertEqual(events[-1].to_status, LearningActivityStatus.COMPLETED)

    def test_get_activity_raises_for_unknown_activity(self) -> None:
        service = ActivityService(InMemoryLearningRepository())

        with self.assertRaises(LookupError):
            service.get_activity(
                user_id="learner",
                activity_id="missing",
            )

    def test_fail_activity_records_terminal_state(self) -> None:
        repository = InMemoryLearningRepository()
        service = ActivityService(repository)
        activity = service.create_activity(user_id="learner")

        failed = service.fail_activity(
            user_id="learner",
            activity_id=activity.activity_id,
            metadata={"error": "generation failed"},
        )

        self.assertEqual(failed.status, LearningActivityStatus.FAILED)
        self.assertEqual(failed.metadata["error"], "generation failed")
        self.assertIsNotNone(failed.completed_at)


if __name__ == "__main__":
    unittest.main()
