from collections import Counter
from datetime import datetime, timezone
from typing import Any

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
        personalization_snapshot: dict[str, object] | None = None,
    ) -> str:
        return self.build_next_activity_recommendation(
            result=result,
            profile=profile,
            generated=generated,
            selected_answers=selected_answers,
            personalization_snapshot=personalization_snapshot,
        ).reason

    def build_next_activity_recommendation(
        self,
        *,
        result: SessionResult,
        profile: LearnerProfile | None = None,
        generated: GeneratedExerciseSet | None = None,
        selected_answers: dict[str, str] | None = None,
        personalization_snapshot: dict[str, object] | None = None,
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

        candidates = self._rank_candidates(
            result=result,
            profile=profile,
            generated=generated,
            selected_answers=selected_answers,
            personalization_snapshot=personalization_snapshot,
            fallback_skill=skill,
            fallback_topic=topic,
            fallback_subtopic=subtopic,
        )
        evidence: dict[str, Any] = {
            "strategy_version": "adaptive_v2",
            "result_score": round(result.score, 4),
            "correct_count": result.correct_count,
            "total_questions": result.total_questions,
            "candidate_scores": candidates[:5],
        }
        selected_candidate = candidates[0] if candidates else None
        if selected_candidate is not None:
            skill_id = str(selected_candidate["skill_id"])
            node = self.skill_graph.get(skill_id)
            skill = skill_id
            topic = node.topic or topic
            subtopic = self.skill_graph.subtopic_from_skill_id(skill_id) or subtopic
            exercise_type = self._exercise_type_for_skill_type(node.skill_type)
            mastery = self._float_or_none(selected_candidate.get("mastery"))
            difficulty = self._difficulty_from_mastery(mastery, result.score)
            evidence["selected_policy"] = selected_candidate["primary_signal"]
            evidence["selected_candidate"] = selected_candidate
            reason = self._ranked_skill_reason(
                node=node,
                difficulty=difficulty,
                candidate=selected_candidate,
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
                evidence["selected_policy"] = "weak_profile_fallback"
            elif result.score < 0.6:
                difficulty = "easy"
                reason = (
                    f"Keep practicing {result.topic} at an easier or equal difficulty before changing topic."
                )
                evidence["selected_policy"] = "score_fallback_easy"
            elif result.score < 0.8:
                reason = (
                    f"Practice {result.topic} again with similar difficulty to stabilize accuracy."
                )
                evidence["selected_policy"] = "score_fallback_stabilize"
            else:
                difficulty = "hard"
                reason = (
                    f"Increase difficulty or move to a related subtopic after {result.topic}."
                )
                evidence["selected_policy"] = "score_fallback_increase"
            evidence["selected_candidate"] = None

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
            evidence=evidence,
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
        snapshot = self._safe_personalization_snapshot(repository, user_id)
        return self.build_next_activity_recommendation(
            result=result,
            profile=profile,
            generated=generated,
            personalization_snapshot=snapshot,
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

    def _safe_personalization_snapshot(
        self,
        repository,
        user_id: str,
    ) -> dict[str, object] | None:
        try:
            snapshot = repository.get_personalization_snapshot(user_id)
        except Exception:
            return None
        return snapshot if isinstance(snapshot, dict) else None

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

    def _rank_candidates(
        self,
        *,
        result: SessionResult,
        profile: LearnerProfile | None,
        generated: GeneratedExerciseSet | None,
        selected_answers: dict[str, str] | None,
        personalization_snapshot: dict[str, object] | None,
        fallback_skill: str | None,
        fallback_topic: str,
        fallback_subtopic: str | None,
    ) -> list[dict[str, Any]]:
        raw_candidates: dict[str, dict[str, Any]] = {}

        def add_candidate(
            skill_id: str | None,
            *,
            signal: str,
            boost: float,
            misses: int = 0,
        ) -> None:
            if not skill_id:
                return
            candidate = raw_candidates.setdefault(
                skill_id,
                {
                    "skill_id": skill_id,
                    "signals": [],
                    "recent_misses": 0,
                    "signal_boost": 0.0,
                },
            )
            if signal not in candidate["signals"]:
                candidate["signals"].append(signal)
            candidate["recent_misses"] = int(candidate["recent_misses"]) + misses
            candidate["signal_boost"] = float(candidate["signal_boost"]) + boost

        for skill_id, misses in self._missed_skill_counts(
            generated=generated,
            selected_answers=selected_answers,
        ).items():
            add_candidate(
                skill_id,
                signal="recent_miss",
                boost=0.28,
                misses=misses,
            )

        for skill_id, misses in self._diagnosis_skill_counts(result).items():
            add_candidate(
                skill_id,
                signal="diagnosis",
                boost=0.24,
                misses=misses,
            )

        if profile is not None:
            for skill_id, mastery in profile.skill_mastery.items():
                if mastery >= 0.9:
                    continue
                node = self.skill_graph.get(skill_id)
                if node.topic == fallback_topic:
                    add_candidate(skill_id, signal="mastery_gap", boost=0.1)
                elif self._goal_relevance(profile.goals, node, fallback_topic) > 0:
                    add_candidate(skill_id, signal="learner_goal", boost=0.06)

        snapshot_rows = self._snapshot_skill_rows(personalization_snapshot)
        for skill_id, row in snapshot_rows.items():
            node = self.skill_graph.get(skill_id)
            goal_relevance = self._goal_relevance(
                profile.goals if profile is not None else [],
                node,
                fallback_topic,
            )
            review_risk = self._forgetting_risk(row.get("next_review_at"))
            if review_risk <= 0:
                continue
            if node.topic == fallback_topic or goal_relevance > 0:
                add_candidate(
                    skill_id,
                    signal="spaced_review",
                    boost=0.14 * review_risk,
                )

        add_candidate(
            fallback_skill,
            signal="current_activity",
            boost=0.03,
        )
        if fallback_skill is None and fallback_subtopic:
            node = self.skill_graph.resolve(
                topic=fallback_topic,
                skill_type=self.skill_graph.skill_type_for_topic(fallback_topic),
                subtopic=fallback_subtopic,
            )
            add_candidate(node.skill_id, signal="current_subtopic", boost=0.03)

        scored = [
            self._score_candidate(
                raw=candidate,
                result=result,
                profile=profile,
                generated=generated,
                snapshot_row=snapshot_rows.get(str(candidate["skill_id"])),
                fallback_topic=fallback_topic,
            )
            for candidate in raw_candidates.values()
        ]
        scored.sort(
            key=lambda item: (
                float(item["score"]),
                int(item["recent_misses"]),
                -float(item.get("mastery") or 0.0),
            ),
            reverse=True,
        )
        return scored

    def _score_candidate(
        self,
        *,
        raw: dict[str, Any],
        result: SessionResult,
        profile: LearnerProfile | None,
        generated: GeneratedExerciseSet | None,
        snapshot_row: dict[str, Any] | None,
        fallback_topic: str,
    ) -> dict[str, Any]:
        skill_id = str(raw["skill_id"])
        node = self.skill_graph.get(skill_id)
        mastery = self._candidate_mastery(skill_id, profile, snapshot_row)
        mastery_gap = 1.0 - mastery if mastery is not None else max(1.0 - result.score, 0.35)
        mastery_by_skill = profile.skill_mastery if profile is not None else {}
        readiness = self.skill_graph.prerequisite_readiness(skill_id, mastery_by_skill)
        forgetting_risk = self._forgetting_risk(
            snapshot_row.get("next_review_at") if snapshot_row else None,
        )
        goal_relevance = self._goal_relevance(
            profile.goals if profile is not None else [],
            node,
            fallback_topic,
        )
        topic_relevance = 1.0 if node.topic == fallback_topic else 0.0
        recent_misses = int(raw.get("recent_misses") or 0)
        recent_miss_score = min(recent_misses / max(result.total_questions, 1), 1.0)
        recent_performance_gap = (
            max(1.0 - result.score, 0.0)
            if node.topic == result.topic
            else 0.0
        )
        difficulty = self._difficulty_from_mastery(mastery, result.score)
        difficulty_match = self._difficulty_match(
            difficulty=difficulty,
            profile=profile,
            generated=generated,
        )
        score = (
            0.33 * mastery_gap
            + 0.22 * recent_miss_score
            + 0.15 * forgetting_risk
            + 0.12 * readiness
            + 0.08 * goal_relevance
            + 0.05 * topic_relevance
            + 0.06 * recent_performance_gap
            + 0.04 * difficulty_match
            + float(raw.get("signal_boost") or 0.0)
        )
        if readiness < 0.4 and recent_misses == 0:
            score -= 0.08
        signals = list(raw.get("signals") or [])
        return {
            "skill_id": skill_id,
            "label": node.label,
            "topic": node.topic,
            "subtopic": self.skill_graph.subtopic_from_skill_id(skill_id),
            "primary_signal": signals[0] if signals else "unknown",
            "signals": signals,
            "score": round(max(score, 0.0), 4),
            "mastery": round(mastery, 4) if mastery is not None else None,
            "mastery_gap": round(mastery_gap, 4),
            "forgetting_risk": round(forgetting_risk, 4),
            "prerequisite_readiness": round(readiness, 4),
            "goal_relevance": round(goal_relevance, 4),
            "topic_relevance": round(topic_relevance, 4),
            "recent_misses": recent_misses,
            "recent_performance_gap": round(recent_performance_gap, 4),
            "difficulty_match": round(difficulty_match, 4),
            "recommended_difficulty": difficulty,
            "next_review_at": (
                snapshot_row.get("next_review_at") if snapshot_row else None
            ),
        }

    def _ranked_skill_reason(
        self,
        *,
        node,
        difficulty: str,
        candidate: dict[str, Any],
    ) -> str:
        parts = [f"Next: practice {node.label} at {difficulty} difficulty."]
        misses = int(candidate.get("recent_misses") or 0)
        mastery = self._float_or_none(candidate.get("mastery"))
        readiness = float(candidate.get("prerequisite_readiness") or 0.0)
        if misses:
            parts.append(f"{misses} missed item(s) pointed to this skill.")
        if float(candidate.get("forgetting_risk") or 0.0) >= 0.65:
            parts.append("It is due for spaced review.")
        elif mastery is not None:
            parts.append(f"Current mastery is about {mastery:.0%}.")
        if readiness >= 0.8:
            parts.append("Prerequisites look ready.")
        else:
            parts.append("Review prerequisite skills first.")
        return " ".join(parts)

    def _missed_skill_counts(
        self,
        *,
        generated: GeneratedExerciseSet | None,
        selected_answers: dict[str, str] | None,
    ) -> Counter[str]:
        misses: Counter[str] = Counter()
        if generated is None:
            return misses
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
        return misses

    def _diagnosis_skill_counts(self, result: SessionResult) -> Counter[str]:
        misses: Counter[str] = Counter()
        for diagnosis in result.answer_diagnoses:
            if not diagnosis.is_correct and diagnosis.skill_id:
                misses[diagnosis.skill_id] += 1
        return misses

    def _snapshot_skill_rows(
        self,
        personalization_snapshot: dict[str, object] | None,
    ) -> dict[str, dict[str, Any]]:
        if not personalization_snapshot:
            return {}
        rows = personalization_snapshot.get("skill_mastery")
        if not isinstance(rows, list):
            return {}
        resolved: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            skill_id = str(row.get("code") or "").strip()
            if skill_id:
                resolved[skill_id] = row
        return resolved

    def _candidate_mastery(
        self,
        skill_id: str,
        profile: LearnerProfile | None,
        snapshot_row: dict[str, Any] | None,
    ) -> float | None:
        if profile is not None and skill_id in profile.skill_mastery:
            return float(profile.skill_mastery[skill_id])
        if snapshot_row is None:
            return None
        value = snapshot_row.get("mastery_probability")
        return self._float_or_none(value)

    def _forgetting_risk(self, value: object) -> float:
        if not value:
            return 0.0
        try:
            due_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        seconds_until_due = (due_at - now).total_seconds()
        if seconds_until_due <= 0:
            return 1.0
        if seconds_until_due <= 24 * 60 * 60:
            return 0.65
        if seconds_until_due <= 3 * 24 * 60 * 60:
            return 0.35
        return 0.0

    def _goal_relevance(
        self,
        goals: list[str],
        node,
        fallback_topic: str,
    ) -> float:
        _ = fallback_topic
        goal_text = " ".join(goals).lower().replace("_", " ")
        if not goal_text:
            return 0.0
        signals = {
            node.topic.replace("_", " "),
            node.label.lower(),
            node.skill_type.lower(),
        }
        if any(signal and signal in goal_text for signal in signals):
            return 1.0
        goal_tokens = set(goal_text.split())
        node_tokens = set(node.topic.replace("_", " ").split())
        node_tokens.update(node.label.lower().split())
        return min(len(goal_tokens.intersection(node_tokens)) / 2, 1.0)

    def _difficulty_match(
        self,
        *,
        difficulty: str,
        profile: LearnerProfile | None,
        generated: GeneratedExerciseSet | None,
    ) -> float:
        target = (
            profile.preferred_difficulty
            if profile is not None and profile.preferred_difficulty
            else generated.plan.difficulty if generated is not None else None
        )
        if not target:
            return 0.5
        if target == difficulty:
            return 1.0
        order = {"easy": 0, "medium": 1, "hard": 2}
        return 0.55 if abs(order.get(target, 1) - order.get(difficulty, 1)) == 1 else 0.2

    def _float_or_none(self, value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

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
