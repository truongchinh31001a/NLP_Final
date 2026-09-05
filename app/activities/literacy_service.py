import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from app.config import AppConfig
from app.persistence.repository import LearningRepository
from app.schemas import (
    AnswerDiagnosis,
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PracticePlan,
    PracticeRequest,
    PracticeReview,
    SessionResult,
)


@dataclass(slots=True)
class LiteracyActivityGeneration:
    activity: LearningActivity
    generated: GeneratedExerciseSet | None = None
    recommendation: str = ""


@dataclass(slots=True)
class WritingActivitySubmission:
    activity: LearningActivity
    result: SessionResult
    writing_text: str
    next_activity_suggestion: dict[str, Any] | None = None


class ReadingActivityService:
    def __init__(self, config: AppConfig, repository: LearningRepository) -> None:
        self.config = config
        self.repository = repository

    def create_reading_activity(
        self,
        *,
        user_id: str,
        raw_text: str,
        conversation_id: str | None = None,
        topic: str | None = None,
    ) -> LiteracyActivityGeneration:
        conversation = self.repository.get_chat_resume(
            user_id,
            session_id=conversation_id,
        )
        profile = self.repository.get_profile(user_id)
        resolved_topic = topic or self._topic_from_profile(profile.weak_topics)
        difficulty = profile.preferred_difficulty or self.config.default_difficulty
        passage = self._passage_for(topic=resolved_topic, difficulty=difficulty)
        vocabulary = self._vocabulary_for(passage)
        activity = self.repository.create_learning_activity(
            LearningActivity(
                activity_id=f"activity_{uuid.uuid4().hex}",
                conversation_id=str(conversation["session_id"]),
                learner_id=user_id,
                type=LearningActivityType.READING,
                target_skills=["reading", "reading_comprehension", resolved_topic],
                difficulty=difficulty,
                metadata={
                    "raw_text": raw_text,
                    "passage": passage,
                    "vocabulary_support": vocabulary,
                    "instructions": (
                        "Read the passage, use the vocabulary hints, then answer "
                        "the comprehension questions."
                    ),
                },
            ),
        )
        self.repository.update_learning_activity_status(
            user_id,
            activity.activity_id,
            LearningActivityStatus.GENERATING,
        )
        request = PracticeRequest(
            user_id=user_id,
            raw_text=raw_text,
            processing_text=raw_text,
            detected_language="vi",
            topic=resolved_topic,
            difficulty=difficulty,
            exercise_type="reading_comprehension",
            num_questions=3,
            content_theme="short_passage",
        )
        plan = PracticePlan(
            user_id=user_id,
            topic=resolved_topic,
            difficulty=difficulty,
            exercise_type="reading_comprehension",
            num_questions=3,
            focus_reason="Learner selected reading as the next study focus.",
            target_subtopic="main_idea_and_detail",
            target_error_tag="reading_comprehension",
            content_theme="short_passage",
            learner_summary=(
                f"Level: {profile.level}; goals: {', '.join(profile.goals) or 'general English'}"
            ),
        )
        exercises = self._questions_for(
            passage=passage,
            topic=resolved_topic,
            difficulty=difficulty,
        )
        generated = GeneratedExerciseSet(
            request=request,
            plan=plan,
            retrieved_chunks=[],
            exercises=exercises,
            activity_id=activity.activity_id,
            prompt_snapshot=(
                "Deterministic reading comprehension activity generated from "
                "the literacy service."
            ),
            agent_trace=[
                {
                    "tool": "literacy.reading.create",
                    "status": "ok",
                    "detail": "Created a passage with vocabulary support and MCQ comprehension checks.",
                    "metadata": {"topic": resolved_topic, "difficulty": difficulty},
                }
            ],
        )
        self.repository.save_generated_exercise_set(
            generated,
            "literacy-reading-service",
        )
        activity = self.repository.update_learning_activity_status(
            user_id,
            activity.activity_id,
            LearningActivityStatus.READY,
        )
        generated.generation_run_id = activity.generation_run_id or generated.generation_run_id
        return LiteracyActivityGeneration(
            activity=activity,
            generated=generated,
            recommendation="Read the passage first, then answer the three questions.",
        )

    def _topic_from_profile(self, weak_topics: dict[str, float]) -> str:
        if weak_topics:
            return max(weak_topics.items(), key=lambda item: item[1])[0]
        return "daily_life"

    def _passage_for(self, *, topic: str, difficulty: str) -> str:
        if "travel" in topic:
            return (
                "Mina is planning a weekend trip. She checks the train schedule, "
                "packs a small bag, and books a room near the station. On Saturday "
                "morning, she leaves early because she wants enough time to find "
                "the hotel and visit the old market."
            )
        if difficulty == "hard":
            return (
                "A small language club meets every Thursday after work. Members "
                "bring short articles, underline useful expressions, and explain "
                "why those expressions matter in real conversations. Over time, "
                "the group becomes more confident because everyone learns from "
                "specific examples instead of memorizing long lists."
            )
        return (
            "Lan studies English for twenty minutes every evening. She reads one "
            "short story, writes five new words in her notebook, and says each word "
            "aloud. After two weeks, she can understand simple messages from her "
            "teacher more quickly."
        )

    def _vocabulary_for(self, passage: str) -> list[dict[str, str]]:
        hints = {
            "schedule": "a plan that shows when events happen",
            "packs": "puts things into a bag",
            "confident": "sure that you can do something",
            "specific": "clear and exact",
            "quickly": "fast",
            "understand": "know the meaning of something",
        }
        lowered = passage.lower()
        return [
            {"word": word, "meaning": meaning}
            for word, meaning in hints.items()
            if word in lowered
        ][:4]

    def _questions_for(
        self,
        *,
        passage: str,
        topic: str,
        difficulty: str,
    ) -> list[ExerciseItem]:
        travel = "weekend trip" in passage
        club = "language club" in passage
        if travel:
            payload = [
                (
                    "read_1",
                    "What is Mina planning?",
                    [
                        ("A", "A weekend trip", True),
                        ("B", "A job interview", False),
                        ("C", "A school exam", False),
                        ("D", "A cooking class", False),
                    ],
                    "A",
                    "The passage says Mina is planning a weekend trip.",
                ),
                (
                    "read_2",
                    "Why does Mina leave early?",
                    [
                        ("A", "She wants to miss the train", False),
                        ("B", "She wants enough time to find the hotel", True),
                        ("C", "She forgot her bag", False),
                        ("D", "She needs to buy a ticket for a friend", False),
                    ],
                    "B",
                    "She leaves early so she has enough time to find the hotel and visit the market.",
                ),
                (
                    "read_3",
                    "Which place does Mina want to visit?",
                    [
                        ("A", "The old market", True),
                        ("B", "The airport", False),
                        ("C", "A language club", False),
                        ("D", "Her office", False),
                    ],
                    "A",
                    "The final sentence mentions the old market.",
                ),
            ]
        elif club:
            payload = [
                (
                    "read_1",
                    "When does the language club meet?",
                    [
                        ("A", "Every Monday morning", False),
                        ("B", "Every Thursday after work", True),
                        ("C", "Only on weekends", False),
                        ("D", "Before school", False),
                    ],
                    "B",
                    "The first sentence gives the meeting time.",
                ),
                (
                    "read_2",
                    "What do members bring?",
                    [
                        ("A", "Short articles", True),
                        ("B", "Old tests", False),
                        ("C", "Travel bags", False),
                        ("D", "Long vocabulary lists only", False),
                    ],
                    "A",
                    "Members bring short articles and study expressions from them.",
                ),
                (
                    "read_3",
                    "Why does the group become more confident?",
                    [
                        ("A", "They stop speaking English", False),
                        ("B", "They memorize random lists", False),
                        ("C", "They learn from specific examples", True),
                        ("D", "They meet once a year", False),
                    ],
                    "C",
                    "The passage contrasts specific examples with memorizing long lists.",
                ),
            ]
        else:
            payload = [
                (
                    "read_1",
                    "How long does Lan study English each evening?",
                    [
                        ("A", "Five minutes", False),
                        ("B", "Twenty minutes", True),
                        ("C", "Two hours", False),
                        ("D", "All night", False),
                    ],
                    "B",
                    "The first sentence says she studies for twenty minutes every evening.",
                ),
                (
                    "read_2",
                    "What does Lan write in her notebook?",
                    [
                        ("A", "Five new words", True),
                        ("B", "Her shopping list", False),
                        ("C", "Her teacher's phone number", False),
                        ("D", "A train schedule", False),
                    ],
                    "A",
                    "She writes five new words in her notebook.",
                ),
                (
                    "read_3",
                    "What improves after two weeks?",
                    [
                        ("A", "Her cooking", False),
                        ("B", "Her drawing", False),
                        ("C", "Her understanding of simple messages", True),
                        ("D", "Her running speed", False),
                    ],
                    "C",
                    "The last sentence says she understands simple messages more quickly.",
                ),
            ]

        return [
            ExerciseItem(
                exercise_id=f"reading_{uuid.uuid4().hex[:8]}_{index}",
                exercise_type="reading_comprehension",
                topic=topic,
                difficulty=difficulty,
                skill="reading",
                subtopic="main_idea_and_detail",
                error_tag="reading_comprehension",
                question_text=question,
                options=[
                    ExerciseOption(label=label, text=text, is_correct=is_correct)
                    for label, text, is_correct in options
                ],
                correct_answer=correct,
                explanation=explanation,
                source_chunk_ids=[f"activity_passage:{index}"],
            )
            for index, (seed_id, question, options, correct, explanation) in enumerate(
                payload,
                start=1,
            )
        ]


class WritingActivityService:
    def __init__(self, config: AppConfig, repository: LearningRepository) -> None:
        self.config = config
        self.repository = repository

    def create_writing_activity(
        self,
        *,
        user_id: str,
        raw_text: str,
        conversation_id: str | None = None,
        topic: str | None = None,
    ) -> LiteracyActivityGeneration:
        conversation = self.repository.get_chat_resume(
            user_id,
            session_id=conversation_id,
        )
        profile = self.repository.get_profile(user_id)
        difficulty = profile.preferred_difficulty or self.config.default_difficulty
        resolved_topic = topic or "daily_life"
        prompt = self._prompt_for(resolved_topic, difficulty)
        rubric = [
            "Task response: answer the prompt clearly.",
            "Grammar: use simple, correct sentence patterns.",
            "Vocabulary: choose precise everyday words.",
            "Coherence: connect ideas in a logical order.",
        ]
        activity = self.repository.create_learning_activity(
            LearningActivity(
                activity_id=f"activity_{uuid.uuid4().hex}",
                conversation_id=str(conversation["session_id"]),
                learner_id=user_id,
                type=LearningActivityType.WRITING,
                target_skills=["writing", "grammar", "coherence"],
                difficulty=difficulty,
                metadata={
                    "raw_text": raw_text,
                    "writing_prompt": prompt,
                    "rubric": rubric,
                    "min_words": 35 if difficulty == "easy" else 60,
                    "instructions": "Write a short answer, then submit it for rubric feedback.",
                },
            ),
        )
        activity = self.repository.update_learning_activity_status(
            user_id,
            activity.activity_id,
            LearningActivityStatus.READY,
        )
        return LiteracyActivityGeneration(
            activity=activity,
            recommendation="Write your answer in the box, then submit it for feedback.",
        )

    def submit_writing_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        writing_text: str,
    ) -> WritingActivitySubmission:
        activity = self._require_writing_activity(user_id, activity_id)
        text = " ".join(writing_text.strip().split())
        if len(text) < 20:
            raise ValueError("Writing submission is too short to assess.")
        if activity.status == LearningActivityStatus.READY:
            self.repository.update_learning_activity_status(
                user_id,
                activity_id,
                LearningActivityStatus.IN_PROGRESS,
            )
        self.repository.update_learning_activity_status(
            user_id,
            activity_id,
            LearningActivityStatus.SUBMITTED,
        )
        assessment = self._assess(text, activity)
        result = SessionResult(
            user_id=user_id,
            topic="writing",
            score=assessment["score"],
            correct_count=assessment["correct_count"],
            total_questions=4,
            weak_topics_detected=assessment["weak_topics"],
            recommendation=assessment["recommendation"],
            activity_id=activity_id,
            answer_diagnoses=assessment["diagnoses"],
            practice_review=assessment["review"],
        )
        session_code = self.repository.save_session_result(
            result,
            activity_id=activity_id,
        )
        result.session_code = session_code
        self.repository.save_practice_review(
            user_id=user_id,
            session_code=session_code,
            review=assessment["review"],
        )
        activity = self.repository.update_learning_activity_metadata(
            user_id,
            activity_id,
            {
                "submitted_text": text,
                "corrected_version": assessment["corrected_version"],
                "rubric_scores": assessment["rubric_scores"],
                "target_skill_diagnosis": assessment["target_skill_diagnosis"],
            }
        )
        return WritingActivitySubmission(
            activity=activity,
            result=result,
            writing_text=text,
            next_activity_suggestion={
                "recommendation_id": f"rec_{activity_id}",
                "user_id": user_id,
                "topic": "writing",
                "difficulty": activity.difficulty or self.config.default_difficulty,
                "exercise_type": "writing_revision",
                "num_questions": 1,
                "reason": assessment["next_reason"],
                "prompt": "Revise the writing using the feedback from the last submission.",
                "source_activity_id": activity_id,
                "conversation_id": activity.conversation_id,
                "evidence": {
                    "rubric_scores": assessment["rubric_scores"],
                    "target_skill_diagnosis": assessment["target_skill_diagnosis"],
                },
            },
        )

    def _require_writing_activity(
        self,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity:
        activity = self.repository.get_learning_activity(user_id, activity_id)
        if activity is None:
            raise LookupError(f"Learning activity not found: {activity_id}")
        if activity.type != LearningActivityType.WRITING:
            raise ValueError("Learning activity is not a writing activity.")
        if activity.status in {
            LearningActivityStatus.CANCELLED,
            LearningActivityStatus.FAILED,
        }:
            raise ValueError(
                f"Cannot submit a {activity.status.value.lower()} activity.",
            )
        return activity

    def _prompt_for(self, topic: str, difficulty: str) -> str:
        if "travel" in topic:
            return "Write 5-7 sentences about a trip you want to take next year."
        if difficulty == "hard":
            return (
                "Write a short paragraph explaining one habit that helps you learn "
                "English and why it works."
            )
        return "Write 4-6 simple sentences about your daily English study routine."

    def _assess(self, text: str, activity: LearningActivity) -> dict[str, Any]:
        words = re.findall(r"[A-Za-z']+", text)
        sentences = [item.strip() for item in re.split(r"[.!?]+", text) if item.strip()]
        unique_words = {word.lower() for word in words}
        task = min(1.0, len(words) / max(float(activity.metadata.get("min_words") or 35), 1.0))
        grammar = self._grammar_score(text, sentences)
        vocabulary = min(1.0, len(unique_words) / max(len(words), 1) * 1.8)
        coherence = self._coherence_score(text, sentences)
        rubric_scores = {
            "task_response": round(task, 2),
            "grammar": round(grammar, 2),
            "vocabulary": round(vocabulary, 2),
            "coherence": round(coherence, 2),
        }
        score = round(sum(rubric_scores.values()) / 4, 2)
        weak_topics = [
            skill for skill, value in rubric_scores.items() if value < 0.7
        ]
        target_skill = weak_topics[0] if weak_topics else "writing_fluency"
        corrected = self._corrected_version(text)
        diagnoses = [
            AnswerDiagnosis(
                exercise_id=f"writing_{skill}",
                is_correct=value >= 0.7,
                error_type="writing_rubric" if value < 0.7 else "correct",
                skill_id=f"writing:{skill}",
                topic="writing",
                subtopic=skill,
                subtype=skill,
                severity=round(1.0 - value, 2),
                mastery_impact=round(0.06 if value >= 0.7 else -0.16 * (1.0 - value), 3),
                explanation=self._rubric_explanation(skill, value),
                evidence={"score": value, "submitted_words": len(words)},
            )
            for skill, value in rubric_scores.items()
        ]
        review = PracticeReview(
            review_code=f"review_{uuid.uuid4().hex[:12]}",
            evaluator="writing-rubric",
            summary=(
                f"Writing score {round(score * 100)}%. "
                f"Main target: {target_skill.replace('_', ' ')}."
            ),
            strengths=[
                self._rubric_explanation(skill, value)
                for skill, value in rubric_scores.items()
                if value >= 0.7
            ]
            or ["You submitted enough text for a useful review."],
            weaknesses=[
                self._rubric_explanation(skill, value)
                for skill, value in rubric_scores.items()
                if value < 0.7
            ],
            next_steps=[
                "Rewrite one sentence with a clear subject and verb.",
                "Add one connector such as because, then, or after that.",
                "Read the corrected version aloud once.",
            ],
            next_practice_prompt="Revise this paragraph using the rubric feedback.",
            raw_response="deterministic-writing-rubric",
        )
        return {
            "score": score,
            "correct_count": sum(1 for value in rubric_scores.values() if value >= 0.7),
            "weak_topics": weak_topics,
            "recommendation": (
                "Good start. Revise the lowest rubric area, then write one more "
                "short paragraph with clearer sentence links."
            ),
            "diagnoses": diagnoses,
            "review": review,
            "corrected_version": corrected,
            "rubric_scores": rubric_scores,
            "target_skill_diagnosis": target_skill,
            "next_reason": f"Focus on {target_skill.replace('_', ' ')} in the next draft.",
        }

    def _grammar_score(self, text: str, sentences: list[str]) -> float:
        if not sentences:
            return 0.2
        sentence_like = sum(1 for sentence in sentences if len(sentence.split()) >= 4)
        has_capital_start = sum(
            1 for sentence in sentences if sentence[:1].isupper()
        )
        has_basic_verbs = len(
            re.findall(
                r"\b(am|is|are|was|were|study|studies|learn|learns|go|goes|have|has|like|likes)\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        return min(
            1.0,
            0.25
            + 0.35 * (sentence_like / max(len(sentences), 1))
            + 0.2 * (has_capital_start / max(len(sentences), 1))
            + min(0.2, has_basic_verbs * 0.05),
        )

    def _coherence_score(self, text: str, sentences: list[str]) -> float:
        connector_count = len(
            re.findall(
                r"\b(and|but|because|so|then|after|first|also|finally)\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        sentence_bonus = 0.35 if len(sentences) >= 3 else 0.15
        return min(1.0, 0.35 + sentence_bonus + min(0.3, connector_count * 0.08))

    def _corrected_version(self, text: str) -> str:
        sentences = [item.strip() for item in re.split(r"([.!?])", text) if item.strip()]
        rebuilt: list[str] = []
        buffer = ""
        for item in sentences:
            if item in {".", "!", "?"}:
                rebuilt.append((buffer.strip().capitalize() + item).strip())
                buffer = ""
            else:
                buffer = item
        if buffer:
            rebuilt.append(buffer.strip().capitalize() + ".")
        corrected = " ".join(rebuilt)
        corrected = re.sub(r"\bi\b", "I", corrected)
        return corrected or text

    def _rubric_explanation(self, skill: str, value: float) -> str:
        label = skill.replace("_", " ")
        if value >= 0.85:
            return f"{label}: strong and clear."
        if value >= 0.7:
            return f"{label}: understandable with small room to improve."
        return f"{label}: revise this area first."
