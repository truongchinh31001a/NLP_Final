from collections import Counter

from app.learner.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph
from app.language.translation import BilingualTextNormalizer
from app.schemas import GeneratedExerciseSet, LearnerProfile, SessionResult


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
        skill_signal = self._strongest_skill_signal(
            generated=generated,
            selected_answers=selected_answers,
        )
        if skill_signal is not None:
            skill_id, misses = skill_signal
            node = self.skill_graph.get(skill_id)
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
            return (
                f"Next: practice {node.label} at {difficulty} difficulty. "
                f"{misses} missed item(s) pointed to this skill."
                f"{mastery_text}{readiness_text}"
            )

        weak_profile_skill = self._weak_profile_skill(profile, result.topic)
        if weak_profile_skill is not None:
            mastery = profile.skill_mastery.get(weak_profile_skill.skill_id, 0.0)
            difficulty = self._difficulty_from_mastery(mastery, result.score)
            return (
                f"Next: return to {weak_profile_skill.label} at {difficulty} "
                f"difficulty. Mastery is about {mastery:.0%}, so this is the "
                "best target before moving on."
            )

        if result.score < 0.6:
            return (
                f"Keep practicing {result.topic} at an easier or equal difficulty before changing topic."
            )
        if result.score < 0.8:
            return f"Practice {result.topic} again with similar difficulty to stabilize accuracy."
        return f"Increase difficulty or move to a related subtopic after {result.topic}."

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
