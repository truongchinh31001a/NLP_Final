from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET
from knowledge_core.sources.ud_ewt import features
from knowledge_core.sources.ud_ewt.models import SkillStructuralEvidence, UDSentenceRecord
from knowledge_core.sources.ud_ewt.paths import SOURCE_KEY


MAX_SENTENCE_EXAMPLES = 25


@dataclass(frozen=True, slots=True)
class StructuralPatternRule:
    canonical_skill_id: str
    pattern_type: str
    description: str
    matcher: Callable[[UDSentenceRecord], bool]
    ud_features: tuple[str, ...] = ()
    dependency_relations: tuple[str, ...] = ()
    lexical_constraints: tuple[str, ...] = ()
    confidence: float = 0.7
    status: str = "candidate"
    review_status: str = "pending"
    reason: str = ""


STRUCTURAL_PATTERN_RULES: tuple[StructuralPatternRule, ...] = (
    StructuralPatternRule(
        canonical_skill_id="grammar.present_simple.third_person_s",
        pattern_type="present_third_person_subject_verb_agreement",
        description="Third-person singular subject with a present finite verbal head.",
        matcher=features.has_subject_verb_agreement_pattern,
        ud_features=("subject Person=3", "subject Number=Sing", "verb Tense=Pres", "verb VerbForm=Fin"),
        dependency_relations=("nsubj",),
        confidence=0.72,
        reason="UD morphology and subject dependencies can support agreement-pattern detection, but do not prove learner mastery.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.present_simple.negative",
        pattern_type="present_do_support_negation",
        description="Present-tense do-support with negation.",
        matcher=features.has_present_simple_negative,
        ud_features=("aux lemma=do", "aux Tense=Pres", "Polarity=Neg or not"),
        dependency_relations=("aux", "advmod"),
        lexical_constraints=("do", "not"),
        confidence=0.68,
        reason="The pattern identifies a structural negative form; semantic use remains outside UD evidence.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.present_simple.questions",
        pattern_type="present_do_support_question",
        description="Question punctuation with present-tense do-support.",
        matcher=features.has_present_simple_question,
        ud_features=("aux lemma=do", "aux Tense=Pres"),
        dependency_relations=("aux",),
        lexical_constraints=("?", "do"),
        confidence=0.64,
        reason="The pattern is structural support for present simple questions, not a curriculum claim.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.present_continuous.form",
        pattern_type="present_progressive_aux_be_participle",
        description="Present-tense be auxiliary with present participial verbal head.",
        matcher=lambda sentence: features.has_progressive_structure(sentence, tense="Pres"),
        ud_features=("aux be Tense=Pres", "head VerbForm=Part", "head Tense=Pres or XPOS=VBG"),
        dependency_relations=("aux",),
        lexical_constraints=("be",),
        confidence=0.78,
        reason="UD auxiliaries and participial morphology provide structural evidence for the form.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.past_continuous.form",
        pattern_type="past_progressive_aux_be_participle",
        description="Past-tense be auxiliary with present participial verbal head.",
        matcher=lambda sentence: features.has_progressive_structure(sentence, tense="Past"),
        ud_features=("aux be Tense=Past", "head VerbForm=Part", "head Tense=Pres or XPOS=VBG"),
        dependency_relations=("aux",),
        lexical_constraints=("be",),
        confidence=0.78,
        reason="UD auxiliaries and participial morphology provide structural evidence for the form.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.present_perfect.form",
        pattern_type="present_perfect_aux_have_past_participle",
        description="Present-tense have auxiliary with past participial verbal head.",
        matcher=features.has_present_perfect_structure,
        ud_features=("aux have Tense=Pres", "head VerbForm=Part", "head Tense=Past or XPOS=VBN"),
        dependency_relations=("aux",),
        lexical_constraints=("have",),
        confidence=0.78,
        reason="UD auxiliaries and participial morphology provide structural evidence for the form.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.present_perfect.past_participle",
        pattern_type="past_participle_in_perfect_structure",
        description="Past participle detected in a present perfect auxiliary structure.",
        matcher=features.has_present_perfect_structure,
        ud_features=("VerbForm=Part", "Tense=Past or XPOS=VBN"),
        dependency_relations=("aux",),
        lexical_constraints=("have",),
        confidence=0.72,
        reason="This is shared participial morphology evidence scoped to the existing V1 skill; it is not a new morphology skill.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.passive.be_past_participle",
        pattern_type="passive_aux_or_subject_relation",
        description="Passive auxiliary, passive subject relation, or Voice=Pass morphology.",
        matcher=features.has_passive_structure,
        ud_features=("Voice=Pass", "VerbForm=Part"),
        dependency_relations=("aux:pass", "nsubj:pass", "csubj:pass"),
        lexical_constraints=("be",),
        confidence=0.82,
        reason="UD passive relations are direct structural evidence, but remain pending review for canonical skill use.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.passive.present_simple",
        pattern_type="present_passive_aux",
        description="Present-tense passive auxiliary structure.",
        matcher=lambda sentence: features.has_passive_structure_with_tense(sentence, tense="Pres"),
        ud_features=("aux:pass Tense=Pres",),
        dependency_relations=("aux:pass",),
        lexical_constraints=("be",),
        confidence=0.76,
        reason="Tense on the passive auxiliary supports a present passive structural pattern.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.passive.past_simple",
        pattern_type="past_passive_aux",
        description="Past-tense passive auxiliary structure.",
        matcher=lambda sentence: features.has_passive_structure_with_tense(sentence, tense="Past"),
        ud_features=("aux:pass Tense=Past",),
        dependency_relations=("aux:pass",),
        lexical_constraints=("be",),
        confidence=0.76,
        reason="Tense on the passive auxiliary supports a past passive structural pattern.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.passive.agent_by",
        pattern_type="passive_agent_by_oblique",
        description="Passive agent relation or by-marked agent oblique.",
        matcher=features.has_agent_by_structure,
        dependency_relations=("obl:agent", "case"),
        lexical_constraints=("by",),
        confidence=0.74,
        reason="UD agentive oblique structure is source-faithful evidence for by-agent patterns.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.articles.a_an",
        pattern_type="indefinite_article_determiner",
        description="Determiner-noun structure with article lemma a or an.",
        matcher=lambda sentence: features.has_article_noun_structure(sentence, article="a")
        or features.has_article_noun_structure(sentence, article="an"),
        dependency_relations=("det",),
        lexical_constraints=("a", "an"),
        confidence=0.7,
        reason="Article determiner structure is directly represented, while usage appropriacy is not.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.articles.the_specific_reference",
        pattern_type="definite_article_determiner",
        description="Determiner-noun structure with article lemma the.",
        matcher=lambda sentence: features.has_article_noun_structure(sentence, article="the"),
        dependency_relations=("det",),
        lexical_constraints=("the",),
        confidence=0.7,
        reason="The definite article form is directly represented, but specificity is semantic and remains review-bound.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.modality.can_ability",
        pattern_type="modal_auxiliary_can",
        description="Modal auxiliary can.",
        matcher=lambda sentence: features.has_modal_auxiliary(sentence, "can"),
        dependency_relations=("aux",),
        lexical_constraints=("can",),
        confidence=0.56,
        status="ambiguous",
        reason="UD can identify the modal form can, but cannot distinguish ability from permission without semantics.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.modality.can_permission",
        pattern_type="modal_auxiliary_can",
        description="Modal auxiliary can.",
        matcher=lambda sentence: features.has_modal_auxiliary(sentence, "can"),
        dependency_relations=("aux",),
        lexical_constraints=("can",),
        confidence=0.56,
        status="ambiguous",
        reason="UD can identify the modal form can, but cannot distinguish permission from ability without semantics.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.modality.could_past_ability",
        pattern_type="modal_auxiliary_could",
        description="Modal auxiliary could.",
        matcher=lambda sentence: features.has_modal_auxiliary(sentence, "could"),
        dependency_relations=("aux",),
        lexical_constraints=("could",),
        confidence=0.54,
        status="ambiguous",
        reason="UD can identify the modal form could, but cannot prove past-ability semantics.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.modality.must_obligation",
        pattern_type="modal_auxiliary_must",
        description="Modal auxiliary must.",
        matcher=lambda sentence: features.has_modal_auxiliary(sentence, "must"),
        dependency_relations=("aux",),
        lexical_constraints=("must",),
        confidence=0.6,
        status="ambiguous",
        reason="UD can identify the modal form must, but obligation force remains semantic.",
    ),
    StructuralPatternRule(
        canonical_skill_id="grammar.modality.should_advice",
        pattern_type="modal_auxiliary_should",
        description="Modal auxiliary should.",
        matcher=lambda sentence: features.has_modal_auxiliary(sentence, "should"),
        dependency_relations=("aux",),
        lexical_constraints=("should",),
        confidence=0.6,
        status="ambiguous",
        reason="UD can identify the modal form should, but advice function remains semantic.",
    ),
)


def build_grammar_structural_evidence(
    sentences: Sequence[UDSentenceRecord],
    *,
    ud_version: str | None = None,
) -> list[SkillStructuralEvidence]:
    evidence: list[SkillStructuralEvidence] = []
    for rule in STRUCTURAL_PATTERN_RULES:
        if rule.canonical_skill_id not in CANONICAL_GRAMMAR_V1_SKILL_SET:
            raise KeyError(f"Unknown canonical Grammar V1 skill: {rule.canonical_skill_id}")
        sentence_ids: list[str] = []
        occurrences = 0
        for sentence in sentences:
            if rule.matcher(sentence):
                occurrences += 1
                if len(sentence_ids) < MAX_SENTENCE_EXAMPLES:
                    sentence_ids.append(sentence.sentence_id)
        if occurrences == 0:
            continue
        evidence.append(
            SkillStructuralEvidence(
                evidence_id=_evidence_id(rule),
                canonical_skill_id=rule.canonical_skill_id,
                pattern_type=rule.pattern_type,
                description=rule.description,
                ud_features=list(rule.ud_features),
                dependency_relations=list(rule.dependency_relations),
                lexical_constraints=list(rule.lexical_constraints),
                source_sentence_ids=sentence_ids,
                occurrence_count=occurrences,
                confidence=rule.confidence,
                status=rule.status,  # type: ignore[arg-type]
                review_status=rule.review_status,  # type: ignore[arg-type]
                reason=rule.reason,
                provenance={
                    "source_key": SOURCE_KEY,
                    "source_version": ud_version,
                    "source_sentence_id_sample_limit": MAX_SENTENCE_EXAMPLES,
                    "generated_by": "ud_ewt_structural_evidence_rules_v1",
                },
            ),
        )
    return evidence


def build_structural_inventory(sentences: Sequence[UDSentenceRecord]) -> dict[str, Any]:
    upos: set[str] = set()
    xpos: set[str] = set()
    feats: dict[str, set[str]] = {}
    deprels: set[str] = set()
    misc: dict[str, set[str]] = {}
    lemma_frequency: dict[str, int] = {}
    feature_combination_frequency: dict[str, int] = {}

    for sentence in sentences:
        for token in sentence.tokens:
            if token.is_multiword:
                continue
            if token.upos:
                upos.add(token.upos)
            if token.xpos:
                xpos.add(token.xpos)
            if token.deprel:
                deprels.add(token.deprel)
            if token.lemma:
                lemma = token.lemma.casefold()
                lemma_frequency[lemma] = lemma_frequency.get(lemma, 0) + 1
            for key, values in token.feats.items():
                feats.setdefault(key, set()).update(values)
            for key, values in token.misc.items():
                misc.setdefault(key, set()).update(values)
            if token.feats:
                combo = "|".join(
                    f"{key}={','.join(values)}"
                    for key, values in sorted(token.feats.items())
                )
                feature_combination_frequency[combo] = (
                    feature_combination_frequency.get(combo, 0) + 1
                )

    return {
        "upos_inventory": sorted(upos),
        "xpos_inventory": sorted(xpos),
        "morphological_feature_inventory": {
            key: sorted(values) for key, values in sorted(feats.items())
        },
        "dependency_relation_inventory": sorted(deprels),
        "misc_inventory": {key: sorted(values) for key, values in sorted(misc.items())},
        "top_lemmas": _top_counts(lemma_frequency, limit=100),
        "top_feature_combinations": _top_counts(feature_combination_frequency, limit=100),
    }


def _evidence_id(rule: StructuralPatternRule) -> str:
    skill = rule.canonical_skill_id.replace(".", "_")
    return f"ud_ewt__{skill}__{rule.pattern_type}"


def _top_counts(counter: dict[str, int], *, limit: int) -> list[dict[str, int | str]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]

