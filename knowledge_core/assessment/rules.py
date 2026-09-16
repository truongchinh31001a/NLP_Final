from __future__ import annotations

from dataclasses import dataclass

from knowledge_core.assessment.models import CriterionType, TaskType


@dataclass(frozen=True, slots=True)
class SkillAssessmentSpec:
    label: str
    kind: str
    observable: str
    evidence_requirements: tuple[str, ...]
    failure_signals: tuple[str, ...]


KIND_TO_CRITERION_TYPES: dict[str, tuple[CriterionType, ...]] = {
    "form": ("form_accuracy",),
    "morphology": ("form_accuracy", "error_correction"),
    "negative": ("form_accuracy", "production"),
    "question": ("form_accuracy", "production"),
    "meaning": ("meaning_use", "production"),
    "contrast": ("contrast_discrimination", "meaning_use"),
}

TASK_TYPES_BY_CRITERION_TYPE: dict[CriterionType, tuple[TaskType, ...]] = {
    "recognition": ("multiple_choice", "classification"),
    "form_accuracy": (
        "fill_blank",
        "sentence_transformation",
        "sentence_completion",
        "short_answer_generation",
    ),
    "meaning_use": (
        "multiple_choice",
        "contrast_choice",
        "sentence_completion",
        "constrained_generation",
        "short_answer_generation",
    ),
    "contrast_discrimination": (
        "contrast_choice",
        "classification",
        "sentence_completion",
        "error_correction",
        "constrained_generation",
    ),
    "production": (
        "short_answer_generation",
        "constrained_generation",
        "free_production",
        "dialogue_completion",
    ),
    "error_correction": (
        "error_correction",
        "sentence_transformation",
        "classification",
    ),
}

CONFIDENCE_BY_CRITERION_TYPE: dict[CriterionType, float] = {
    "form_accuracy": 0.96,
    "meaning_use": 0.90,
    "contrast_discrimination": 0.80,
    "production": 0.82,
    "recognition": 0.82,
    "error_correction": 0.78,
}

CRITERION_TYPE_LABELS: dict[CriterionType, str] = {
    "form_accuracy": "form accuracy",
    "meaning_use": "meaning and use",
    "contrast_discrimination": "contrast discrimination",
    "production": "controlled production",
    "recognition": "recognition",
    "error_correction": "error correction",
}


SKILL_ASSESSMENT_SPECS: dict[str, SkillAssessmentSpec] = {
    "grammar.present_simple.affirmative": SkillAssessmentSpec(
        label="present simple affirmative",
        kind="form",
        observable=(
            "Learner forms present simple affirmative clauses with appropriate "
            "subject-verb agreement for routine, general, or factual statements."
        ),
        evidence_requirements=(
            "correct lexical verb form",
            "appropriate subject-verb agreement",
            "affirmative declarative word order",
        ),
        failure_signals=(
            "unnecessary auxiliary in affirmative clauses",
            "incorrect subject-verb agreement",
            "uses progressive or past form where present simple is required",
        ),
    ),
    "grammar.present_simple.third_person_s": SkillAssessmentSpec(
        label="present simple third-person singular -s",
        kind="morphology",
        observable=(
            "Learner marks regular present simple lexical verbs with third-person "
            "singular -s or -es when the subject requires it."
        ),
        evidence_requirements=(
            "correct third-person singular marker",
            "correct choice of -s, -es, or irregular has/does",
            "no marking with non-third-person subjects",
        ),
        failure_signals=(
            "omitted third-person singular marker",
            "base verb used with a third-person singular subject",
            "overgeneralized -s marking where it is not required",
        ),
    ),
    "grammar.present_simple.negative": SkillAssessmentSpec(
        label="present simple negative",
        kind="negative",
        observable=(
            "Learner forms present simple negatives with do not or does not "
            "followed by the base form of the lexical verb."
        ),
        evidence_requirements=(
            "correct do/does auxiliary",
            "correct negative marker",
            "base lexical verb after the auxiliary",
        ),
        failure_signals=(
            "missing do/does auxiliary",
            "inflected lexical verb after do/does",
            "negative marker placed in the wrong position",
        ),
    ),
    "grammar.present_simple.questions": SkillAssessmentSpec(
        label="present simple questions",
        kind="question",
        observable=(
            "Learner forms present simple questions using do or does with "
            "appropriate subject-auxiliary order and a base lexical verb."
        ),
        evidence_requirements=(
            "correct do/does auxiliary",
            "correct subject-auxiliary order",
            "base lexical verb after do/does",
        ),
        failure_signals=(
            "missing do/does auxiliary",
            "incorrect subject-auxiliary order",
            "inflected lexical verb after do/does",
        ),
    ),
    "grammar.present_continuous.form": SkillAssessmentSpec(
        label="present continuous form",
        kind="form",
        observable=(
            "Learner constructs the present continuous using an appropriate form "
            "of be followed by the -ing form of the lexical verb."
        ),
        evidence_requirements=(
            "correct am/is/are auxiliary",
            "correct -ing verb morphology",
            "correct auxiliary-verb order",
        ),
        failure_signals=(
            "missing be auxiliary",
            "incorrect be agreement",
            "bare verb or infinitive used instead of -ing form",
        ),
    ),
    "grammar.present_continuous.current_action": SkillAssessmentSpec(
        label="present continuous for current action",
        kind="meaning",
        observable=(
            "Learner selects and uses the present continuous to describe an "
            "action in progress around the current moment."
        ),
        evidence_requirements=(
            "current in-progress context",
            "appropriate present continuous form",
            "clear connection between time context and verb choice",
        ),
        failure_signals=(
            "uses present simple for an action happening now",
            "uses present continuous without an in-progress context",
            "forms the progressive inaccurately",
        ),
    ),
    "grammar.present_continuous.temporary_situation": SkillAssessmentSpec(
        label="present continuous for temporary situations",
        kind="meaning",
        observable=(
            "Learner uses the present continuous to describe a temporary state, "
            "arrangement, or situation around the present period."
        ),
        evidence_requirements=(
            "temporary present-time context",
            "appropriate present continuous form",
            "contrast with permanent or habitual meaning when relevant",
        ),
        failure_signals=(
            "uses present simple for a clearly temporary situation",
            "uses present continuous for stable facts or routines",
            "does not mark the progressive form accurately",
        ),
    ),
    "grammar.past_simple.regular_verbs": SkillAssessmentSpec(
        label="past simple regular verbs",
        kind="morphology",
        observable=(
            "Learner forms regular past simple verbs with an appropriate -ed "
            "spelling or pronunciation-sensitive written form."
        ),
        evidence_requirements=(
            "correct regular -ed marking",
            "correct spelling changes such as studied or stopped",
            "appropriate past-time context",
        ),
        failure_signals=(
            "omitted regular past marker",
            "incorrect spelling of regular past form",
            "uses base or present form in a past-time context",
        ),
    ),
    "grammar.past_simple.irregular_verbs": SkillAssessmentSpec(
        label="past simple irregular verbs",
        kind="morphology",
        observable=(
            "Learner selects accurate irregular past simple verb forms in "
            "completed past contexts."
        ),
        evidence_requirements=(
            "correct irregular past form",
            "appropriate past-time context",
            "no overregularized -ed form for common irregular verbs",
        ),
        failure_signals=(
            "overregularized irregular verb",
            "base or present form used for past meaning",
            "wrong irregular form selected",
        ),
    ),
    "grammar.past_simple.negative": SkillAssessmentSpec(
        label="past simple negative",
        kind="negative",
        observable=(
            "Learner forms past simple negatives with did not followed by the "
            "base form of the lexical verb."
        ),
        evidence_requirements=(
            "correct did auxiliary",
            "correct negative marker",
            "base lexical verb after did",
        ),
        failure_signals=(
            "missing did auxiliary",
            "past-tense lexical verb after did",
            "negative marker placed in the wrong position",
        ),
    ),
    "grammar.past_simple.questions": SkillAssessmentSpec(
        label="past simple questions",
        kind="question",
        observable=(
            "Learner forms past simple questions with did, correct "
            "subject-auxiliary order, and a base lexical verb."
        ),
        evidence_requirements=(
            "correct did auxiliary",
            "correct subject-auxiliary order",
            "base lexical verb after did",
        ),
        failure_signals=(
            "missing did auxiliary",
            "incorrect subject-auxiliary order",
            "past-tense lexical verb after did",
        ),
    ),
    "grammar.past_simple.finished_past": SkillAssessmentSpec(
        label="past simple for finished past events",
        kind="meaning",
        observable=(
            "Learner uses the past simple to locate completed actions, events, "
            "or states in a finished past time."
        ),
        evidence_requirements=(
            "finished past-time context",
            "appropriate past simple verb form",
            "clear separation from present-time relevance",
        ),
        failure_signals=(
            "uses present tense for a finished past event",
            "uses present perfect with a finished time marker",
            "does not mark past time on the verb phrase",
        ),
    ),
    "grammar.past_continuous.form": SkillAssessmentSpec(
        label="past continuous form",
        kind="form",
        observable=(
            "Learner constructs the past continuous with was or were followed "
            "by the -ing form of the lexical verb."
        ),
        evidence_requirements=(
            "correct was/were auxiliary",
            "correct -ing verb morphology",
            "correct auxiliary-verb order",
        ),
        failure_signals=(
            "missing was/were auxiliary",
            "incorrect was/were agreement",
            "bare verb or past form used instead of -ing form",
        ),
    ),
    "grammar.past_continuous.background_action": SkillAssessmentSpec(
        label="past continuous for background action",
        kind="meaning",
        observable=(
            "Learner uses the past continuous to describe an action in progress "
            "as background to another past event."
        ),
        evidence_requirements=(
            "ongoing past background context",
            "appropriate past continuous form",
            "coherent relation to another past event when supplied",
        ),
        failure_signals=(
            "uses past simple for an ongoing background action",
            "uses past continuous for a completed sequence of events",
            "forms was/were + -ing inaccurately",
        ),
    ),
    "grammar.past_continuous.interrupted_action": SkillAssessmentSpec(
        label="past continuous for interrupted action",
        kind="meaning",
        observable=(
            "Learner uses the past continuous for an ongoing past action and "
            "the past simple for the interrupting event."
        ),
        evidence_requirements=(
            "ongoing past action",
            "interrupting completed past event",
            "appropriate tense choice in both clauses",
        ),
        failure_signals=(
            "uses the same tense for both ongoing and interrupting events",
            "places past continuous on the interrupting event",
            "forms the past continuous inaccurately",
        ),
    ),
    "grammar.present_perfect.form": SkillAssessmentSpec(
        label="present perfect form",
        kind="form",
        observable=(
            "Learner constructs the present perfect with have or has followed "
            "by a past participle."
        ),
        evidence_requirements=(
            "correct have/has auxiliary",
            "correct past participle form",
            "correct auxiliary-participle order",
        ),
        failure_signals=(
            "missing have/has auxiliary",
            "wrong auxiliary agreement",
            "non-participle verb form",
        ),
    ),
    "grammar.present_perfect.past_participle": SkillAssessmentSpec(
        label="past participle forms",
        kind="morphology",
        observable=(
            "Learner recognizes and supplies past participle forms needed in "
            "perfect and passive verb phrases."
        ),
        evidence_requirements=(
            "correct regular or irregular past participle",
            "distinction between past simple and past participle where relevant",
            "appropriate use after have/has or passive be when prompted",
        ),
        failure_signals=(
            "uses past simple form instead of past participle",
            "overregularizes common irregular participles",
            "uses base verb after have/has or passive be",
        ),
    ),
    "grammar.present_perfect.experience": SkillAssessmentSpec(
        label="present perfect for experience",
        kind="meaning",
        observable=(
            "Learner uses the present perfect to talk about life experience "
            "without anchoring the event to a finished past time."
        ),
        evidence_requirements=(
            "experience context",
            "appropriate present perfect form",
            "avoidance of finished past-time markers",
        ),
        failure_signals=(
            "uses past simple where experience relevance is intended",
            "adds a finished past-time marker with present perfect",
            "forms have/has + participle inaccurately",
        ),
    ),
    "grammar.present_perfect.unfinished_time": SkillAssessmentSpec(
        label="present perfect for unfinished time",
        kind="meaning",
        observable=(
            "Learner uses the present perfect for events or states connected "
            "to an unfinished time period."
        ),
        evidence_requirements=(
            "unfinished time frame such as today or this week",
            "appropriate present perfect form",
            "clear present relevance",
        ),
        failure_signals=(
            "uses past simple with an unfinished time period",
            "uses present perfect without present-time relevance",
            "forms have/has + participle inaccurately",
        ),
    ),
    "grammar.present_perfect.recent_result": SkillAssessmentSpec(
        label="present perfect for recent result",
        kind="meaning",
        observable=(
            "Learner uses the present perfect to express a recent event with "
            "a result or relevance at the present moment."
        ),
        evidence_requirements=(
            "recent event context",
            "present result or relevance",
            "appropriate present perfect form",
        ),
        failure_signals=(
            "uses past simple when the prompt emphasizes present result",
            "omits have/has",
            "uses a non-participle verb form",
        ),
    ),
    "grammar.present_perfect.since_for": SkillAssessmentSpec(
        label="present perfect with since and for",
        kind="meaning",
        observable=(
            "Learner uses the present perfect with since for a starting point "
            "and for for a duration continuing to the present."
        ),
        evidence_requirements=(
            "correct choice of since or for",
            "duration or starting-point meaning",
            "appropriate present perfect form",
        ),
        failure_signals=(
            "confuses since and for",
            "uses past simple for a situation continuing to the present",
            "forms have/has + participle inaccurately",
        ),
    ),
    "grammar.future.will_prediction": SkillAssessmentSpec(
        label="will for prediction",
        kind="meaning",
        observable=(
            "Learner uses will to make predictions about future events, states, "
            "or likely outcomes."
        ),
        evidence_requirements=(
            "future prediction context",
            "correct will + base verb form",
            "meaning distinct from offer or instant decision when relevant",
        ),
        failure_signals=(
            "uses will in a non-future context",
            "uses an inflected verb after will",
            "chooses will where another future form is clearly required",
        ),
    ),
    "grammar.future.will_spontaneous_decision": SkillAssessmentSpec(
        label="will for spontaneous decisions",
        kind="meaning",
        observable=(
            "Learner uses will to express a decision made at the moment of "
            "speaking."
        ),
        evidence_requirements=(
            "immediate decision context",
            "correct will + base verb form",
            "distinction from planned arrangements when relevant",
        ),
        failure_signals=(
            "uses will for a pre-arranged plan when contrast is required",
            "uses an inflected verb after will",
            "does not match the response to the immediate-decision context",
        ),
    ),
    "grammar.future.will_offer_promise": SkillAssessmentSpec(
        label="will for offers and promises",
        kind="meaning",
        observable=(
            "Learner uses will to make offers, promises, or voluntary future "
            "commitments in context."
        ),
        evidence_requirements=(
            "offer, promise, or voluntary commitment context",
            "correct will + base verb form",
            "appropriate communicative function",
        ),
        failure_signals=(
            "uses will without offer or promise force",
            "uses an inflected verb after will",
            "selects a form that does not match the communicative function",
        ),
    ),
    "grammar.modality.can_ability": SkillAssessmentSpec(
        label="can for ability",
        kind="meaning",
        observable=(
            "Learner uses can to express present ability or capability in a "
            "given context."
        ),
        evidence_requirements=(
            "ability meaning",
            "correct can + base verb form",
            "meaning distinct from permission when relevant",
        ),
        failure_signals=(
            "uses can for permission when ability is intended",
            "uses an inflected verb after can",
            "selects an inappropriate modal for ability meaning",
        ),
    ),
    "grammar.modality.can_permission": SkillAssessmentSpec(
        label="can for permission",
        kind="meaning",
        observable=(
            "Learner uses can to ask for, grant, or discuss permission in a "
            "context where permission is intended."
        ),
        evidence_requirements=(
            "permission meaning",
            "correct can + base verb form",
            "meaning distinct from ability when relevant",
        ),
        failure_signals=(
            "uses can for ability when permission is intended",
            "uses an inflected verb after can",
            "does not match modal choice to the permission context",
        ),
    ),
    "grammar.modality.could_past_ability": SkillAssessmentSpec(
        label="could for past ability",
        kind="meaning",
        observable=(
            "Learner uses could to describe general past ability or capability "
            "in an appropriate past context."
        ),
        evidence_requirements=(
            "past ability meaning",
            "correct could + base verb form",
            "appropriate past-time reference",
        ),
        failure_signals=(
            "uses can for past ability",
            "uses an inflected verb after could",
            "uses could where a single successful past event is intended",
        ),
    ),
    "grammar.modality.must_obligation": SkillAssessmentSpec(
        label="must for obligation",
        kind="meaning",
        observable=(
            "Learner uses must to express strong obligation, necessity, or rule "
            "force in context."
        ),
        evidence_requirements=(
            "strong obligation or necessity meaning",
            "correct must + base verb form",
            "appropriate force for the situation",
        ),
        failure_signals=(
            "uses must where advice or permission is intended",
            "uses an inflected verb after must",
            "understates or overstates the intended obligation",
        ),
    ),
    "grammar.modality.should_advice": SkillAssessmentSpec(
        label="should for advice",
        kind="meaning",
        observable=(
            "Learner uses should to give advice, recommendations, or mild "
            "obligation in context."
        ),
        evidence_requirements=(
            "advice or recommendation meaning",
            "correct should + base verb form",
            "appropriate strength compared with must",
        ),
        failure_signals=(
            "uses must when advice is intended",
            "uses an inflected verb after should",
            "modal force does not match the context",
        ),
    ),
    "grammar.modality.must_vs_have_to": SkillAssessmentSpec(
        label="must versus have to",
        kind="contrast",
        observable=(
            "Learner distinguishes must and have to according to the intended "
            "source, force, or framing of obligation."
        ),
        evidence_requirements=(
            "appropriate choice between must and have to",
            "correct verb form after the selected modal or semi-modal",
            "obligation meaning matched to context",
        ),
        failure_signals=(
            "uses must and have to interchangeably in a contrast task",
            "incorrect form after have to",
            "obligation source or force does not match the context",
        ),
    ),
    "grammar.articles.a_an": SkillAssessmentSpec(
        label="a/an indefinite article",
        kind="meaning",
        observable=(
            "Learner uses a or an with singular count nouns when introducing "
            "one non-specific referent."
        ),
        evidence_requirements=(
            "singular count noun context",
            "non-specific or first mention meaning",
            "appropriate choice of a or an by following sound",
        ),
        failure_signals=(
            "omits article before a singular count noun",
            "uses the where non-specific reference is intended",
            "chooses a/an inaccurately before vowel or consonant sounds",
        ),
    ),
    "grammar.articles.the_specific_reference": SkillAssessmentSpec(
        label="the for specific reference",
        kind="meaning",
        observable=(
            "Learner uses the when the referent is specific, known, unique, or "
            "recoverable from context."
        ),
        evidence_requirements=(
            "specific or shared reference context",
            "correct use of the",
            "distinction from indefinite or zero article when relevant",
        ),
        failure_signals=(
            "uses a/an where a specific referent is intended",
            "omits the for known or unique reference",
            "overuses the with generic or non-specific reference",
        ),
    ),
    "grammar.articles.zero_article": SkillAssessmentSpec(
        label="zero article",
        kind="meaning",
        observable=(
            "Learner omits the article appropriately with plural, uncountable, "
            "institutional, or generic noun phrases where zero article is required."
        ),
        evidence_requirements=(
            "noun phrase type that permits zero article",
            "appropriate generic or non-specific meaning",
            "contrast with a/an or the when relevant",
        ),
        failure_signals=(
            "adds an article where zero article is required",
            "omits an article before a singular count noun",
            "uses zero article where specific reference is intended",
        ),
    ),
    "grammar.articles.first_vs_subsequent_mention": SkillAssessmentSpec(
        label="first versus subsequent mention articles",
        kind="contrast",
        observable=(
            "Learner distinguishes first mention from subsequent mention by "
            "choosing a/an for introduction and the for later specific reference."
        ),
        evidence_requirements=(
            "first mention context",
            "subsequent mention context",
            "appropriate switch from a/an to the",
        ),
        failure_signals=(
            "uses the for first mention without shared reference",
            "continues using a/an after the referent is established",
            "does not track referent status across sentences",
        ),
    ),
    "grammar.articles.generic_reference": SkillAssessmentSpec(
        label="generic reference",
        kind="meaning",
        observable=(
            "Learner uses article patterns appropriately to make generic "
            "reference to a class, type, or general category."
        ),
        evidence_requirements=(
            "generic meaning",
            "appropriate article pattern for noun type",
            "distinction from specific reference when relevant",
        ),
        failure_signals=(
            "uses a specific article pattern for generic meaning",
            "omits needed article with singular count nouns",
            "does not distinguish class reference from individual reference",
        ),
    ),
    "grammar.conditionals.zero": SkillAssessmentSpec(
        label="zero conditional",
        kind="meaning",
        observable=(
            "Learner uses zero conditional structures to express general truths, "
            "rules, or regular cause-effect relationships."
        ),
        evidence_requirements=(
            "general truth or regular result context",
            "appropriate present simple in both clauses",
            "clear condition-result relation",
        ),
        failure_signals=(
            "uses will in a zero conditional context",
            "uses a one-time future meaning for a general rule",
            "does not maintain present simple in both clauses",
        ),
    ),
    "grammar.conditionals.first": SkillAssessmentSpec(
        label="first conditional",
        kind="meaning",
        observable=(
            "Learner uses first conditional structures to express a real or "
            "possible future condition and result."
        ),
        evidence_requirements=(
            "real or possible future condition",
            "present simple in the if-clause",
            "appropriate future or modal result clause",
        ),
        failure_signals=(
            "uses will in the if-clause",
            "uses second conditional form for a realistic future condition",
            "condition and result clauses do not match in meaning",
        ),
    ),
    "grammar.conditionals.second": SkillAssessmentSpec(
        label="second conditional",
        kind="meaning",
        observable=(
            "Learner uses second conditional structures to express hypothetical "
            "or less real present/future situations."
        ),
        evidence_requirements=(
            "hypothetical or less real meaning",
            "past-form verb in the if-clause",
            "would or similar modal in the result clause",
        ),
        failure_signals=(
            "uses first conditional for a hypothetical situation",
            "uses will instead of would in the result clause",
            "condition and result clauses do not match in hypothetical meaning",
        ),
    ),
    "grammar.conditionals.first_vs_second": SkillAssessmentSpec(
        label="first versus second conditional",
        kind="contrast",
        observable=(
            "Learner distinguishes first and second conditional according to "
            "the intended degree of reality, likelihood, or hypotheticality."
        ),
        evidence_requirements=(
            "accurate contrast between realistic and hypothetical conditions",
            "appropriate verb forms in if-clauses",
            "appropriate result-clause modal choice",
        ),
        failure_signals=(
            "chooses conditionals based only on surface time words",
            "uses will and would interchangeably",
            "does not distinguish likely from hypothetical meaning",
        ),
    ),
    "grammar.passive.be_past_participle": SkillAssessmentSpec(
        label="passive be plus past participle pattern",
        kind="form",
        observable=(
            "Learner constructs passive verb phrases with an appropriate form "
            "of be followed by a past participle."
        ),
        evidence_requirements=(
            "correct be auxiliary",
            "correct past participle form",
            "passive word order",
        ),
        failure_signals=(
            "missing be auxiliary",
            "uses base or past simple form instead of past participle",
            "uses active word order where passive is required",
        ),
    ),
    "grammar.passive.present_simple": SkillAssessmentSpec(
        label="present simple passive",
        kind="form",
        observable=(
            "Learner forms present simple passive clauses with am, is, or are "
            "plus a past participle."
        ),
        evidence_requirements=(
            "correct present form of be",
            "correct past participle",
            "patient or affected entity placed as subject",
        ),
        failure_signals=(
            "uses active present simple where passive is required",
            "wrong present be agreement",
            "non-participle verb after be",
        ),
    ),
    "grammar.passive.past_simple": SkillAssessmentSpec(
        label="past simple passive",
        kind="form",
        observable=(
            "Learner forms past simple passive clauses with was or were plus "
            "a past participle."
        ),
        evidence_requirements=(
            "correct was/were auxiliary",
            "correct past participle",
            "patient or affected entity placed as subject",
        ),
        failure_signals=(
            "uses active past simple where passive is required",
            "wrong was/were agreement",
            "non-participle verb after was/were",
        ),
    ),
    "grammar.passive.agent_by": SkillAssessmentSpec(
        label="by-agent passive phrases",
        kind="meaning",
        observable=(
            "Learner includes a by-agent phrase in a passive clause when the "
            "agent is communicatively relevant."
        ),
        evidence_requirements=(
            "appropriate passive clause",
            "relevant agent information",
            "correct placement and form of by-agent phrase",
        ),
        failure_signals=(
            "adds by-agent phrase when the agent is irrelevant or unknown",
            "omits relevant agent information when prompted",
            "uses incorrect preposition or active structure",
        ),
    ),
}


def criterion_types_for_skill(skill_id: str) -> tuple[CriterionType, ...]:
    spec = SKILL_ASSESSMENT_SPECS[skill_id]
    return KIND_TO_CRITERION_TYPES[spec.kind]


def task_types_for_criterion(criterion_type: CriterionType) -> tuple[TaskType, ...]:
    return TASK_TYPES_BY_CRITERION_TYPE[criterion_type]


def confidence_for_criterion(criterion_type: CriterionType) -> float:
    return CONFIDENCE_BY_CRITERION_TYPE[criterion_type]


def name_for_criterion(spec: SkillAssessmentSpec, criterion_type: CriterionType) -> str:
    return f"{spec.label}: {CRITERION_TYPE_LABELS[criterion_type]}"


def description_for_criterion(
    spec: SkillAssessmentSpec,
    criterion_type: CriterionType,
) -> str:
    label = CRITERION_TYPE_LABELS[criterion_type]
    return f"Assess {label} evidence for {spec.label}."


def observable_for_criterion(
    spec: SkillAssessmentSpec,
    criterion_type: CriterionType,
) -> str:
    if criterion_type in {
        "form_accuracy",
        "meaning_use",
        "contrast_discrimination",
    }:
        return spec.observable
    if criterion_type == "production":
        return (
            f"Learner produces sentences or short responses that use "
            f"{spec.label} accurately and appropriately in the supplied context."
        )
    if criterion_type == "error_correction":
        return (
            f"Learner identifies and corrects errors involving {spec.label} "
            "without introducing a new grammar error."
        )
    return f"Learner recognizes accurate examples of {spec.label} in context."


def evidence_requirements_for_criterion(
    spec: SkillAssessmentSpec,
    criterion_type: CriterionType,
) -> tuple[str, ...]:
    extra: tuple[str, ...]
    if criterion_type == "production":
        extra = (
            "appropriate response to prompt",
            "controlled use in generated language",
        )
    elif criterion_type == "error_correction":
        extra = (
            "accurate identification of the target error",
            "accurate correction of the target structure",
        )
    elif criterion_type == "contrast_discrimination":
        extra = (
            "selection of the contextually appropriate option",
            "clear contrast between the target forms or meanings",
        )
    elif criterion_type == "recognition":
        extra = (
            "accurate recognition of target examples",
            "accurate rejection of distractors",
        )
    else:
        extra = ()
    return _dedupe((*spec.evidence_requirements, *extra))


def failure_signals_for_criterion(
    spec: SkillAssessmentSpec,
    criterion_type: CriterionType,
) -> tuple[str, ...]:
    extra: tuple[str, ...]
    if criterion_type == "production":
        extra = (
            "avoids the target structure where it is required",
            "produces memorized fragments without context control",
        )
    elif criterion_type == "error_correction":
        extra = (
            "fails to notice the target error",
            "introduces a new error in the correction",
        )
    elif criterion_type == "contrast_discrimination":
        extra = (
            "chooses based on surface cues rather than intended meaning",
        )
    elif criterion_type == "recognition":
        extra = (
            "accepts distractors that violate the target criterion",
        )
    else:
        extra = ()
    return _dedupe((*spec.failure_signals, *extra))


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)
