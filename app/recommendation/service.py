from collections import Counter

from app.learner.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph
from app.language.translation import BilingualTextNormalizer
from app.schemas import (
    ActivityRecommendation,
    GeneratedExerciseSet,
    LearnerProfile,
    LearningActivity,
    LearningActivityStatus,
    PracticeRequest,
    SessionResult,
)


class RecommendationService:
    def __init__(self, skill_graph: SkillGraph | None = None) -> None:
        self.skill_graph = skill_graph or DEFAULT_SKILL_GRAPH
        self.text_normalizer = BilingualTextNormalizer()

    def recommend(
        self,
        result: SessionResult,
        profile: LearnerProfile | None = None,
        generated: GeneratedExerciseSet | None = None,
        selected_answers: dict[str, str] | None = None,
    ) -> str:
        return self.build_next_activity_recommendation(
            result=result,
            profile=profile,
            generated=generated,
            selected_answers=selected_answers,
        ).reason

    def build_next_activity_recommendation(
        self,
        *,
        result: SessionResult,
        profile: LearnerProfile | None = None,
        generated: GeneratedExerciseSet | None = None,
        selected_answers: dict[str, str] | None = None,
        source_activity_id: str | None = None,
        conversation_id: str | None = None,
    ) -> ActivityRecommendation:
        topic = generated.plan.topic if generated is not None else result.topic
        exercise_type = (
            generated.plan.exercise_type
            if generated is not None
            else self._exercise_type_for_topic(result.topic)
        )
        num_questions = min(max(result.total_questions or 5, 5), 10)
        subtopic = generated.plan.target_subtopic if generated is not None else None
        skill = generated.plan.target_skill_id if generated is not None else None
        difficulty = (
            generated.plan.difficulty
            if generated is not None
            else self._difficulty_from_mastery(None, result.score)
        )

        skill_signal = self._strongest_skill_signal(
            generated=generated,
            selected_answers=selected_answers,
        ) or self._strongest_diagnosis_signal(result)
        if skill_signal is not None:
            skill_id, misses = skill_signal
            node = self.skill_graph.get(skill_id)
            skill = skill_id
            topic = node.topic or topic
            subtopic = self.skill_graph.subtopic_from_skill_id(skill_id) or subtopic
            exercise_type = self._exercise_type_for_skill_type(node.skill_type)
            mastery = (profile.skill_mastery.get(skill_id) if profile else None)
            readiness = (
                self.skill_graph.prerequisite_readiness(
                    skill_id,
                    profile.skill_mastery,
                )
                if profile
                else 1.0
            )
            difficulty = self._difficulty_from_mastery(mastery, result.score)
            mastery_text = (
                f" Current mastery is about {mastery:.0%}."
                if mastery is not None
                else ""
            )
            readiness_text = (
                " Prerequisites look ready."
                if readiness >= 0.8
                else " Review prerequisite skills first."
            )
            reason = (
                f"Next: practice {node.label} at {difficulty} difficulty. "
                f"{misses} missed item(s) pointed to this skill."
                f"{mastery_text}{readiness_text}"
            )
        else:
            weak_profile_skill = self._weak_profile_skill(profile, result.topic)
            if weak_profile_skill is not None:
                mastery = profile.skill_mastery.get(
                    weak_profile_skill.skill_id,
                    0.0,
                )
                skill = weak_profile_skill.skill_id
                topic = weak_profile_skill.topic or topic
                subtopic = (
                    self.skill_graph.subtopic_from_skill_id(
                        weak_profile_skill.skill_id,
                    )
                    or subtopic
                )
                exercise_type = self._exercise_type_for_skill_type(
                    weak_profile_skill.skill_type,
                )
                difficulty = self._difficulty_from_mastery(mastery, result.score)
                reason = (
                    f"Next: return to {weak_profile_skill.label} at {difficulty} "
                    f"difficulty. Mastery is about {mastery:.0%}, so this is the "
                    "best target before moving on."
                )
            elif result.score < 0.6:
                difficulty = "easy"
                reason = (
                    f"Keep practicing {result.topic} at an easier or equal difficulty before changing topic."
                )
            elif result.score < 0.8:
                reason = (
                    f"Practice {result.topic} again with similar difficulty to stabilize accuracy."
                )
            else:
                difficulty = "hard"
                reason = (
                    f"Increase difficulty or move to a related subtopic after {result.topic}."
                )

        source_id = (
            source_activity_id
            or result.activity_id
            or (generated.activity_id if generated is not None else None)
        )
        recommendation_id = self.recommendation_id_for_source(source_id)
        return ActivityRecommendation(
            recommendation_id=recommendation_id,
            user_id=result.user_id,
            source_activity_id=source_id,
            conversation_id=conversation_id,
            skill=skill,
            topic=topic,
            subtopic=subtopic,
            difficulty=difficulty,
            exercise_type=exercise_type,
            num_questions=num_questions,
            reason=reason,
            prompt=self._prompt_for_recommendation(
                topic=topic,
                subtopic=subtopic,
                difficulty=difficulty,
                exercise_type=exercise_type,
                num_questions=num_questions,
            ),
        )

    def list_current(
        self,
        *,
        user_id: str,
        repository,
        limit: int = 5,
    ) -> list[ActivityRecommendation]:
        sessions = repository.list_chat_sessions(
            user_id,
            limit=max(limit * 3, limit),
        ).get("sessions", [])
        recommendations: list[ActivityRecommendation] = []
        seen_activity_ids: set[str] = set()
        for session in sessions:
            if not isinstance(session, dict):
                continue
            conversation_id = str(session.get("session_id") or "")
            if not conversation_id:
                continue
            activity = repository.get_latest_learning_activity(
                user_id,
                conversation_id,
                statuses=[
                    LearningActivityStatus.COMPLETED,
                    LearningActivityStatus.GRADED,
                ],
            )
            if activity is None or activity.activity_id in seen_activity_ids:
                continue
            try:
                recommendations.append(
                    self.recommendation_for_activity(
                        user_id=user_id,
                        repository=repository,
                        activity=activity,
                    ),
                )
                seen_activity_ids.add(activity.activity_id)
            except LookupError:
                continue
            if len(recommendations) >= limit:
                break
        return recommendations

    def resolve_current(
        self,
        *,
        user_id: str,
        repository,
        recommendation_id: str,
    ) -> ActivityRecommendation:
        activity_id = self.source_activity_id_from_recommendation_id(
            recommendation_id,
        )
        if not activity_id:
            raise LookupError(f"Recommendation not found: {recommendation_id}")
        activity = repository.get_learning_activity(user_id, activity_id)
        if activity is None:
            raise LookupError(f"Recommendation not found: {recommendation_id}")
        return self.recommendation_for_activity(
            user_id=user_id,
            repository=repository,
            activity=activity,
        )

    def recommendation_for_activity(
        self,
        *,
        user_id: str,
        repository,
        activity: LearningActivity,
    ) -> ActivityRecommendation:
        if not activity.generation_run_id or not activity.session_code:
            raise LookupError("Recommendation source activity is incomplete.")
        generated = repository.get_generated_exercise_set(
            user_id,
            activity.generation_run_id,
        )
        result = repository.get_session_result(user_id, activity.session_code)
        if generated is None or result is None:
            raise LookupError("Recommendation source data is incomplete.")
        profile = repository.get_profile(user_id)
        return self.build_next_activity_recommendation(
            result=result,
            profile=profile,
            generated=generated,
            source_activity_id=activity.activity_id,
            conversation_id=activity.conversation_id,
        )

    def to_practice_request(
        self,
        recommendation: ActivityRecommendation,
    ) -> PracticeRequest:
        return PracticeRequest(
            user_id=recommendation.user_id,
            raw_text=recommendation.prompt,
            processing_text=recommendation.prompt,
            detected_language="en",
            topic=recommendation.topic,
            difficulty=recommendation.difficulty,
            exercise_type=recommendation.exercise_type,
            num_questions=recommendation.num_questions,
            target_subtopic=recommendation.subtopic,
        )

    def recommendation_id_for_source(self, source_activity_id: str | None) -> str:
        if source_activity_id:
            return f"rec_{source_activity_id}"
        return "rec_current"

    def source_activity_id_from_recommendation_id(
        self,
        recommendation_id: str,
    ) -> str | None:
        if not recommendation_id.startswith("rec_"):
            return None
        return recommendation_id.removeprefix("rec_")

    def _strongest_skill_signal(
        self,
        generated: GeneratedExerciseSet | None,
        selected_answers: dict[str, str] | None,
    ) -> tuple[str, int] | None:
        if generated is None:
            return None

        misses: Counter[str] = Counter()
        for exercise in generated.exercises:
            selected_answer = (
                selected_answers.get(exercise.exercise_id)
                if selected_answers is not None
                else None
            )
            is_correct = (
                selected_answers is None
                or self.text_normalizer.answers_match(
                    selected_answer,
                    exercise.correct_answer,
                )
            )
            if is_correct:
                continue
            skill_id = self.skill_graph.skill_id_for(
                topic=exercise.topic,
                skill_type=exercise.skill,
                subtopic=exercise.subtopic,
            )
            misses[skill_id] += 1

        if not misses:
            return None
        return misses.most_common(1)[0]

    def _strongest_diagnosis_signal(
        self,
        result: SessionResult,
    ) -> tuple[str, int] | None:
        misses: Counter[str] = Counter()
        for diagnosis in result.answer_diagnoses:
            if not diagnosis.is_correct and diagnosis.skill_id:
                misses[diagnosis.skill_id] += 1
        if not misses:
            return None
        return misses.most_common(1)[0]

    def _weak_profile_skill(
        self,
        profile: LearnerProfile | None,
        topic: str,
    ):
        if profile is None or not profile.skill_mastery:
            return None
        return self.skill_graph.weakest_ready_skill(
            profile.skill_mastery,
            topic=topic,
        )

    def _difficulty_from_mastery(
        self,
        mastery: float | None,
        fallback_score: float,
    ) -> str:
        signal = fallback_score if mastery is None else mastery
        if signal < 0.45:
            return "easy"
        if signal < 0.75:
            return "medium"
        return "hard"

    def _exercise_type_for_topic(self, topic: str) -> str:
        return "vocabulary_mcq" if "vocabulary" in topic else "grammar_mcq"

    def _exercise_type_for_skill_type(self, skill_type: str) -> str:
        return "vocabulary_mcq" if skill_type == "vocabulary" else "grammar_mcq"

    def _prompt_for_recommendation(
        self,
        *,
        topic: str,
        subtopic: str | None,
        difficulty: str,
        exercise_type: str,
        num_questions: int,
    ) -> str:
        focus = (subtopic or topic).replace("_", " ")
        mode = exercise_type.replace("_", " ")
        return (
            f"Create {num_questions} {mode} questions about {focus} "
            f"at {difficulty} difficulty."
        )
