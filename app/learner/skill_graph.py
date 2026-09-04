from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SkillNode:
    skill_id: str
    label: str
    topic: str
    skill_type: str
    cefr: str = "A1"
    parent_id: str | None = None
    prerequisites: tuple[str, ...] = ()
    description: str = ""


class SkillGraph:
    def __init__(self, nodes: list[SkillNode]) -> None:
        self.nodes = {node.skill_id: node for node in nodes}

    def resolve(
        self,
        *,
        topic: str,
        skill_type: str | None = None,
        subtopic: str | None = None,
    ) -> SkillNode:
        normalized_topic = normalize_code(topic or "grammar")
        normalized_skill_type = normalize_code(skill_type or self.skill_type_for_topic(normalized_topic))
        normalized_subtopic = normalize_code(subtopic or normalized_topic)
        skill_id = self.skill_id_for(
            topic=normalized_topic,
            skill_type=normalized_skill_type,
            subtopic=normalized_subtopic,
        )
        if skill_id in self.nodes:
            return self.nodes[skill_id]

        parent_id = self.skill_id_for(
            topic=normalized_topic,
            skill_type=normalized_skill_type,
            subtopic=None,
        )
        return SkillNode(
            skill_id=skill_id,
            label=label_from_code(normalized_subtopic),
            topic=normalized_topic,
            skill_type=normalized_skill_type,
            parent_id=parent_id,
            prerequisites=(),
            description=f"Auto-discovered skill for {label_from_code(normalized_topic)}.",
        )

    def get(self, skill_id: str) -> SkillNode:
        if skill_id in self.nodes:
            return self.nodes[skill_id]

        parts = skill_id.split(".")
        skill_type = parts[0] if parts else "grammar"
        topic = parts[1] if len(parts) > 1 else "grammar"
        subtopic = parts[-1] if len(parts) > 2 else topic
        return SkillNode(
            skill_id=skill_id,
            label=label_from_code(subtopic),
            topic=topic,
            skill_type=skill_type,
            parent_id=self.skill_id_for(topic=topic, skill_type=skill_type),
            prerequisites=(),
            description=f"Auto-discovered skill for {label_from_code(topic)}.",
        )

    def skill_id_for(
        self,
        *,
        topic: str,
        skill_type: str | None = None,
        subtopic: str | None = None,
    ) -> str:
        normalized_topic = normalize_code(topic or "grammar")
        normalized_skill_type = normalize_code(skill_type or self.skill_type_for_topic(normalized_topic))
        if not subtopic:
            return f"{normalized_skill_type}.{normalized_topic}"
        return f"{normalized_skill_type}.{normalized_topic}.{normalize_code(subtopic)}"

    def subtopic_from_skill_id(self, skill_id: str) -> str | None:
        parts = skill_id.split(".")
        if len(parts) < 3:
            return None
        return parts[-1]

    def skill_type_for_topic(self, topic: str) -> str:
        return "vocabulary" if "vocabulary" in topic else "grammar"

    def prerequisite_readiness(
        self,
        skill_id: str,
        mastery_by_skill: dict[str, float],
        threshold: float = 0.65,
    ) -> float:
        prerequisites = self.get(skill_id).prerequisites
        if not prerequisites:
            return 1.0
        ready = [
            min(mastery_by_skill.get(prerequisite_id, 0.0) / threshold, 1.0)
            for prerequisite_id in prerequisites
        ]
        return sum(ready) / len(ready)

    def weakest_ready_skill(
        self,
        mastery_by_skill: dict[str, float],
        *,
        topic: str | None = None,
        mastery_ceiling: float = 0.85,
        readiness_threshold: float = 0.65,
    ) -> SkillNode | None:
        candidates: list[tuple[float, SkillNode]] = []
        for skill_id, mastery in mastery_by_skill.items():
            node = self.get(skill_id)
            if topic and node.topic != topic:
                continue
            if mastery >= mastery_ceiling:
                continue
            readiness = self.prerequisite_readiness(
                skill_id,
                mastery_by_skill,
                threshold=readiness_threshold,
            )
            candidates.append((mastery + (1.0 - readiness), node))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]


def normalize_code(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def label_from_code(value: str) -> str:
    return normalize_code(value).replace("_", " ").title()


DEFAULT_SKILL_GRAPH = SkillGraph(
    [
        SkillNode(
            "grammar.tenses",
            "Tenses",
            "tenses",
            "grammar",
            "A1",
            description="Core tense system.",
        ),
        SkillNode(
            "grammar.tenses.present_simple_habits",
            "Present Simple Habits",
            "tenses",
            "grammar",
            "A1",
            parent_id="grammar.tenses",
        ),
        SkillNode(
            "grammar.tenses.present_continuous_now",
            "Present Continuous Now",
            "tenses",
            "grammar",
            "A1",
            parent_id="grammar.tenses",
            prerequisites=("grammar.tenses.present_simple_habits",),
        ),
        SkillNode(
            "grammar.tenses.past_simple_finished_time",
            "Past Simple Finished Time",
            "tenses",
            "grammar",
            "A2",
            parent_id="grammar.tenses",
            prerequisites=("grammar.tenses.present_simple_habits",),
        ),
        SkillNode(
            "grammar.tenses.present_perfect_since",
            "Present Perfect With Since",
            "tenses",
            "grammar",
            "B1",
            parent_id="grammar.tenses",
            prerequisites=("grammar.tenses.past_simple_finished_time",),
        ),
        SkillNode(
            "grammar.tenses.present_perfect_experience",
            "Present Perfect Experience",
            "tenses",
            "grammar",
            "B1",
            parent_id="grammar.tenses",
            prerequisites=("grammar.tenses.past_simple_finished_time",),
        ),
        SkillNode(
            "grammar.tenses.past_continuous_interrupted_action",
            "Past Continuous Interrupted Action",
            "tenses",
            "grammar",
            "B1",
            parent_id="grammar.tenses",
            prerequisites=("grammar.tenses.past_simple_finished_time",),
        ),
        SkillNode(
            "grammar.tenses.past_perfect_sequence",
            "Past Perfect Sequence",
            "tenses",
            "grammar",
            "B1",
            parent_id="grammar.tenses",
            prerequisites=("grammar.tenses.past_simple_finished_time",),
        ),
        SkillNode(
            "grammar.passive_voice",
            "Passive Voice",
            "passive_voice",
            "grammar",
            "A2",
        ),
        SkillNode(
            "grammar.passive_voice.present_simple_passive",
            "Present Simple Passive",
            "passive_voice",
            "grammar",
            "A2",
            parent_id="grammar.passive_voice",
            prerequisites=("grammar.tenses.present_simple_habits",),
        ),
        SkillNode(
            "grammar.passive_voice.past_simple_passive",
            "Past Simple Passive",
            "passive_voice",
            "grammar",
            "A2",
            parent_id="grammar.passive_voice",
            prerequisites=("grammar.tenses.past_simple_finished_time",),
        ),
        SkillNode(
            "grammar.passive_voice.future_passive",
            "Future Passive",
            "passive_voice",
            "grammar",
            "B1",
            parent_id="grammar.passive_voice",
            prerequisites=("grammar.passive_voice.present_simple_passive",),
        ),
        SkillNode(
            "grammar.passive_voice.modal_passive",
            "Modal Passive",
            "passive_voice",
            "grammar",
            "B1",
            parent_id="grammar.passive_voice",
            prerequisites=("grammar.passive_voice.present_simple_passive",),
        ),
        SkillNode(
            "grammar.passive_voice.present_perfect_passive",
            "Present Perfect Passive",
            "passive_voice",
            "grammar",
            "B1",
            parent_id="grammar.passive_voice",
            prerequisites=("grammar.passive_voice.present_simple_passive",),
        ),
        SkillNode(
            "grammar.relative_clause",
            "Relative Clauses",
            "relative_clause",
            "grammar",
            "A2",
        ),
        SkillNode(
            "grammar.relative_clause.who_for_people",
            "Who For People",
            "relative_clause",
            "grammar",
            "A2",
            parent_id="grammar.relative_clause",
        ),
        SkillNode(
            "grammar.relative_clause.which_for_things",
            "Which For Things",
            "relative_clause",
            "grammar",
            "A2",
            parent_id="grammar.relative_clause",
        ),
        SkillNode(
            "grammar.conditional_sentence",
            "Conditional Sentences",
            "conditional_sentence",
            "grammar",
            "B1",
        ),
        SkillNode(
            "grammar.conditional_sentence.first_conditional",
            "First Conditional",
            "conditional_sentence",
            "grammar",
            "A2",
            parent_id="grammar.conditional_sentence",
        ),
        SkillNode(
            "grammar.conditional_sentence.second_conditional",
            "Second Conditional",
            "conditional_sentence",
            "grammar",
            "B1",
            parent_id="grammar.conditional_sentence",
            prerequisites=("grammar.conditional_sentence.first_conditional",),
        ),
        SkillNode(
            "grammar.conditional_sentence.third_conditional",
            "Third Conditional",
            "conditional_sentence",
            "grammar",
            "B2",
            parent_id="grammar.conditional_sentence",
            prerequisites=("grammar.conditional_sentence.second_conditional",),
        ),
        SkillNode(
            "grammar.reported_speech",
            "Reported Speech",
            "reported_speech",
            "grammar",
            "B1",
        ),
        SkillNode(
            "grammar.reported_speech.reported_speech_general",
            "Reported Speech General",
            "reported_speech",
            "grammar",
            "B1",
            parent_id="grammar.reported_speech",
            prerequisites=("grammar.tenses.past_simple_finished_time",),
        ),
        SkillNode(
            "grammar.prepositions",
            "Prepositions",
            "prepositions",
            "grammar",
            "A1",
        ),
        SkillNode(
            "vocabulary.vocabulary",
            "Vocabulary",
            "vocabulary",
            "vocabulary",
            "A1",
        ),
        SkillNode(
            "vocabulary.vocabulary.collocations",
            "Collocations",
            "vocabulary",
            "vocabulary",
            "B1",
            parent_id="vocabulary.vocabulary",
        ),
        SkillNode(
            "vocabulary.vocabulary.word_forms",
            "Word Forms",
            "vocabulary",
            "vocabulary",
            "A2",
            parent_id="vocabulary.vocabulary",
        ),
        SkillNode(
            "vocabulary.vocabulary.synonym_antonym",
            "Synonym And Antonym",
            "vocabulary",
            "vocabulary",
            "B1",
            parent_id="vocabulary.vocabulary",
        ),
        SkillNode(
            "vocabulary.vocabulary.communication_phrases",
            "Communication Phrases",
            "vocabulary",
            "vocabulary",
            "A2",
            parent_id="vocabulary.vocabulary",
        ),
        SkillNode(
            "vocabulary.travel_vocabulary",
            "Travel Vocabulary",
            "travel_vocabulary",
            "vocabulary",
            "A1",
        ),
        SkillNode(
            "vocabulary.travel_vocabulary.airport_vocabulary",
            "Airport Vocabulary",
            "travel_vocabulary",
            "vocabulary",
            "A1",
            parent_id="vocabulary.travel_vocabulary",
        ),
        SkillNode(
            "vocabulary.travel_vocabulary.hotel_vocabulary",
            "Hotel Vocabulary",
            "travel_vocabulary",
            "vocabulary",
            "A1",
            parent_id="vocabulary.travel_vocabulary",
        ),
    ]
)
