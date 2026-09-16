from __future__ import annotations

import re
from dataclasses import dataclass

from knowledge_core.sources.egp.models import RawEGPRecord


@dataclass(slots=True, frozen=True)
class RuleDecision:
    canonical_skill: str | None
    secondary_candidates: tuple[str, ...]
    status: str
    confidence: float
    reason: str
    matched_terms: tuple[str, ...]


def decide_mapping(record: RawEGPRecord) -> RuleDecision:
    category_id = record.category_id
    if category_id == "present_simple":
        return _present_simple(record)
    if category_id == "present_continuous":
        return _present_continuous(record)
    if category_id == "past_simple":
        return _past_simple(record)
    if category_id == "past_continuous":
        return _past_continuous(record)
    if category_id == "present_perfect_simple":
        return _present_perfect(record)
    if category_id == "future_will":
        return _future_will(record)
    if category_id.startswith("modality_"):
        return _modality(record)
    if category_id == "articles":
        return _articles(record)
    if category_id == "conditional":
        return _conditionals(record)
    if category_id == "passives_form":
        return _passives(record)
    return _unmapped("No mapping rules exist for this source category.")


def _present_simple(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "negative question", "negative tag question"):
        return _ambiguous(
            (
                "grammar.present_simple.negative",
                "grammar.present_simple.questions",
            ),
            "Present simple negative-question feature fits two V1 skills.",
            ("negative question",),
        )
    if _has_any(record, "third person", "third-person", "3rd person", " -s", " -es"):
        return _exact(
            "grammar.present_simple.third_person_s",
            "Present simple third-person marker matched.",
            ("third person",),
        )
    if _has_any(record, "question", "interrogative", "do you know"):
        return _exact(
            "grammar.present_simple.questions",
            "Present simple question form matched.",
            ("question",),
        )
    if _has_any(record, "negative", "do not", "does not", "don't", "doesn't"):
        return _exact(
            "grammar.present_simple.negative",
            "Present simple negative form matched.",
            ("negative",),
        )
    if _has_feature(record, "FORM", "AFFIRMATIVE"):
        return _exact(
            "grammar.present_simple.affirmative",
            "Present simple affirmative feature matched.",
            ("FORM: AFFIRMATIVE",),
        )
    return _unmapped("Present simple feature is outside the current V1 atomic skills.")


def _present_continuous(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "temporary situation", "temporary situations", "temporary"):
        return _exact(
            "grammar.present_continuous.temporary_situation",
            "Present continuous temporary-situation use matched.",
            ("temporary",),
        )
    if _has_any(record, "events in progress", "happening now", "current action", "action now"):
        return _exact(
            "grammar.present_continuous.current_action",
            "Present continuous current-action use matched.",
            ("events in progress",),
        )
    if _feature_type_is(record, "FORM"):
        return _exact(
            "grammar.present_continuous.form",
            "Present continuous form feature matched.",
            ("FORM",),
        )
    if _has_feature_type(record, "FORM") or _has_any(record, "be + ing", "present progressive form"):
        return _candidate(
            "grammar.present_continuous.form",
            "Present continuous mixed form/use feature matched.",
            ("FORM",),
            confidence=0.78,
        )
    return _unmapped(
        "Present continuous feature is outside the current V1 atomic skills.",
    )


def _past_simple(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "question", "interrogative"):
        return _exact(
            "grammar.past_simple.questions",
            "Past simple question form matched.",
            ("question",),
        )
    if _has_any(record, "negative", "did not", "didn't"):
        return _exact(
            "grammar.past_simple.negative",
            "Past simple negative form matched.",
            ("negative",),
        )
    if _has_any(record, "regular and irregular"):
        return _ambiguous(
            (
                "grammar.past_simple.regular_verbs",
                "grammar.past_simple.irregular_verbs",
            ),
            "Past simple form mentions both regular and irregular verbs.",
            ("regular and irregular",),
        )
    if _has_any(record, "irregular"):
        return _exact(
            "grammar.past_simple.irregular_verbs",
            "Past simple irregular verb feature matched.",
            ("irregular",),
        )
    if _has_any(record, "regular", "-ed"):
        return _exact(
            "grammar.past_simple.regular_verbs",
            "Past simple regular verb feature matched.",
            ("regular",),
        )
    if _has_any(record, "finished past", "past time", "specific past time"):
        return _exact(
            "grammar.past_simple.finished_past",
            "Past simple finished-past-time use matched.",
            ("past time",),
        )
    return _unmapped("Past simple feature is outside the current V1 atomic skills.")


def _past_continuous(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "interrupted", "interruption"):
        return _exact(
            "grammar.past_continuous.interrupted_action",
            "Past continuous interrupted-action use matched.",
            ("interrupted",),
        )
    if _has_any(record, "background", "background events", "background action"):
        return _exact(
            "grammar.past_continuous.background_action",
            "Past continuous background-action use matched.",
            ("background",),
        )
    if _feature_type_is(record, "FORM"):
        return _exact(
            "grammar.past_continuous.form",
            "Past continuous form feature matched.",
            ("FORM",),
        )
    if _has_feature_type(record, "FORM") or _has_any(record, "was + ing", "were + ing"):
        return _candidate(
            "grammar.past_continuous.form",
            "Past continuous mixed form/use feature matched.",
            ("FORM",),
            confidence=0.78,
        )
    return _unmapped(
        "Past continuous feature is outside the current V1 atomic skills.",
    )


def _present_perfect(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "since", "for", "duration"):
        return _exact(
            "grammar.present_perfect.since_for",
            "Present perfect since/for duration feature matched.",
            ("since/for",),
        )
    if _has_any(record, "already", "just", "yet", "recent result", "recent past"):
        return _exact(
            "grammar.present_perfect.recent_result",
            "Present perfect recent-result adverb/use matched.",
            ("already/just/yet",),
        )
    if _has_any(record, "experience", "experiences", "ever", "never", "before", "superlative"):
        return _exact(
            "grammar.present_perfect.experience",
            "Present perfect experience feature matched.",
            ("experience",),
        )
    if _has_any(record, "unfinished", "continuing situation", "unfinished time"):
        return _exact(
            "grammar.present_perfect.unfinished_time",
            "Present perfect unfinished-time feature matched.",
            ("unfinished",),
        )
    if _has_any(record, "past participle", " v3 "):
        return _exact(
            "grammar.present_perfect.past_participle",
            "Present perfect past participle feature matched.",
            ("past participle",),
        )
    if _feature_type_is(record, "FORM"):
        return _exact(
            "grammar.present_perfect.form",
            "Present perfect form feature matched.",
            ("FORM",),
        )
    if _has_feature_type(record, "FORM") or _has_any(record, "have + past participle", "has + past participle"):
        return _candidate(
            "grammar.present_perfect.form",
            "Present perfect mixed form/use feature matched.",
            ("FORM",),
            confidence=0.78,
        )
    return _unmapped(
        "Present perfect feature is outside the current V1 atomic skills.",
    )


def _future_will(record: RawEGPRecord) -> RuleDecision:
    if not _source_subcategory_is(record, "future simple (with will and shall)"):
        return _unmapped(
            "Future source row is not in EGP future simple with will/shall.",
        )
    if _has_any(record, "prediction", "predictions"):
        return _exact(
            "grammar.future.will_prediction",
            "Will/shall prediction use matched.",
            ("prediction",),
        )
    if _has_any(record, "spontaneous decision", "instant decision"):
        return _exact(
            "grammar.future.will_spontaneous_decision",
            "Will spontaneous decision use matched.",
            ("spontaneous decision",),
        )
    if _has_any(record, "offer", "offers", "promise", "promises"):
        return _exact(
            "grammar.future.will_offer_promise",
            "Will/shall offer or promise use matched.",
            ("offer/promise",),
        )
    return _unmapped(
        "Will/shall row is outside the current V1 future-will atomic skills.",
    )


def _modality(record: RawEGPRecord) -> RuleDecision:
    if record.category_id == "modality_can":
        if _has_any(record, "ability"):
            return _exact(
                "grammar.modality.can_ability",
                "Can ability use matched.",
                ("ability",),
            )
        if _has_any(record, "permission"):
            return _exact(
                "grammar.modality.can_permission",
                "Can permission use matched.",
                ("permission",),
            )
        return _unmapped("Can feature is outside the current V1 modality skills.")

    if record.category_id == "modality_could":
        if _has_any(record, "ability", "inability"):
            return _candidate(
                "grammar.modality.could_past_ability",
                "Could ability/inability feature matched.",
                ("ability",),
                confidence=0.88,
            )
        return _unmapped("Could feature is outside the current V1 modality skills.")

    if record.category_id == "modality_must":
        if _has_any(record, "obligation", "necessity", "rules", "not permitted"):
            return _exact(
                "grammar.modality.must_obligation",
                "Must obligation/necessity use matched.",
                ("obligation",),
            )
        return _unmapped("Must feature is outside the current V1 modality skills.")

    if record.category_id == "modality_should":
        if _has_any(record, "advice", "recommendation", "recommendations", "suggestions"):
            return _exact(
                "grammar.modality.should_advice",
                "Should advice/recommendation use matched.",
                ("advice",),
            )
        return _unmapped("Should feature is outside the current V1 modality skills.")

    if record.category_id == "modality_have_got_to":
        if _has_any(record, "obligation", "have got to", "have to"):
            return _candidate(
                "grammar.modality.must_vs_have_to",
                "Have (got) to obligation is related to the V1 must-vs-have-to skill.",
                ("have got to", "obligation"),
                confidence=0.78,
            )
        return _unmapped(
            "Have (got) to feature is outside the current V1 modality skills.",
        )

    return _unmapped("Modality category has no configured rule.")


def _articles(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "first mention", "subsequent mention"):
        return _exact(
            "grammar.articles.first_vs_subsequent_mention",
            "Article first/subsequent mention use matched.",
            ("first/subsequent mention",),
        )
    if _has_any(record, "no article", "zero article"):
        secondary = (
            ("grammar.articles.generic_reference",)
            if _has_any(record, "general", "generic")
            else ()
        )
        return RuleDecision(
            canonical_skill="grammar.articles.zero_article",
            secondary_candidates=secondary,
            status="candidate" if secondary else "exact",
            confidence=0.86 if secondary else 1.0,
            reason="No-article feature matched; generic reference kept as secondary when present.",
            matched_terms=("no article",),
        )
    if _has_any(record, "generic reference", "generic meaning", "things in general", "in general"):
        return _exact(
            "grammar.articles.generic_reference",
            "Article generic-reference use matched.",
            ("generic",),
        )
    if _has_any(record, "a and an", "a / an", "indefinite article", "'a'", "'an'"):
        return _exact(
            "grammar.articles.a_an",
            "A/an article feature matched.",
            ("a/an",),
        )
    if _has_any(record, "the", "definite article", "specific reference", "specify", "specifying"):
        return _candidate(
            "grammar.articles.the_specific_reference",
            "The/specific-reference article feature matched.",
            ("the",),
            confidence=0.82,
        )
    return _unmapped("Article feature is outside the current V1 article skills.")


def _conditionals(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "first vs second", "contrast first and second"):
        return _exact(
            "grammar.conditionals.first_vs_second",
            "First-vs-second conditional contrast matched.",
            ("first vs second",),
        )
    if _has_any(record, "first conditional", "if + present simple + will", "'will', future, likely outcome"):
        return _exact(
            "grammar.conditionals.first",
            "First conditional feature matched.",
            ("first conditional",),
        )
    if _has_any(record, "second conditional", "past simple + 'would'", "past simple + would"):
        return _exact(
            "grammar.conditionals.second",
            "Second conditional feature matched.",
            ("second conditional",),
        )
    if _has_any(record, "zero conditional"):
        return _exact(
            "grammar.conditionals.zero",
            "Zero conditional feature matched.",
            ("zero conditional",),
        )
    if _has_any(record, "things that are true now", "real conditions", "'if' + present simple"):
        return _candidate(
            "grammar.conditionals.zero",
            "Real present condition is a category-aware zero conditional candidate.",
            ("if + present simple",),
            confidence=0.78,
        )
    return _unmapped(
        "Conditional feature is outside the current V1 conditional skills.",
    )


def _passives(record: RawEGPRecord) -> RuleDecision:
    if _has_any(record, "by agent", "agent introduced by by", "with 'by'", " by "):
        return _exact(
            "grammar.passive.agent_by",
            "Passive by-agent feature matched.",
            ("by agent",),
        )
    if _has_any(record, "present simple passive", "present simple"):
        return _exact(
            "grammar.passive.present_simple",
            "Present simple passive feature matched.",
            ("present simple passive",),
        )
    if _has_any(record, "past simple passive", "past simple"):
        return _exact(
            "grammar.passive.past_simple",
            "Past simple passive feature matched.",
            ("past simple passive",),
        )
    if _has_any(record, "be + past participle", "passive form") or _has_feature_type(record, "FORM"):
        return _candidate(
            "grammar.passive.be_past_participle",
            "General passive form feature matched.",
            ("FORM",),
            confidence=0.8,
        )
    return _unmapped("Passive feature is outside the current V1 passive skills.")


def _exact(skill: str, reason: str, terms: tuple[str, ...]) -> RuleDecision:
    return RuleDecision(
        canonical_skill=skill,
        secondary_candidates=(),
        status="exact",
        confidence=1.0,
        reason=reason,
        matched_terms=terms,
    )


def _candidate(
    skill: str,
    reason: str,
    terms: tuple[str, ...],
    *,
    confidence: float,
) -> RuleDecision:
    return RuleDecision(
        canonical_skill=skill,
        secondary_candidates=(),
        status="candidate",
        confidence=confidence,
        reason=reason,
        matched_terms=terms,
    )


def _ambiguous(
    candidates: tuple[str, ...],
    reason: str,
    terms: tuple[str, ...],
) -> RuleDecision:
    return RuleDecision(
        canonical_skill=None,
        secondary_candidates=candidates,
        status="ambiguous",
        confidence=0.55,
        reason=reason,
        matched_terms=terms,
    )


def _unmapped(reason: str) -> RuleDecision:
    return RuleDecision(
        canonical_skill=None,
        secondary_candidates=(),
        status="unmapped",
        confidence=0.0,
        reason=reason,
        matched_terms=(),
    )


def _has_feature(record: RawEGPRecord, feature_type: str, feature_name: str) -> bool:
    return _norm(record.feature_type) == _norm(feature_type) and _norm(feature_name) in _norm(
        record.feature_name,
    )


def _has_feature_type(record: RawEGPRecord, feature_type: str) -> bool:
    actual = _norm(record.feature_type)
    expected = _norm(feature_type)
    return actual == expected or expected in actual.split()


def _feature_type_is(record: RawEGPRecord, feature_type: str) -> bool:
    return _norm(record.feature_type) == _norm(feature_type)


def _source_subcategory_is(record: RawEGPRecord, value: str) -> bool:
    return _norm(record.sub_category) == _norm(value)


def _has_any(record: RawEGPRecord, *terms: str) -> bool:
    haystack = _search_text(record)
    return any(_contains(haystack, term) for term in terms)


def _search_text(record: RawEGPRecord) -> str:
    parts = [
        record.category_id,
        record.super_category,
        record.sub_category,
        record.feature_type,
        record.feature_name,
        record.can_do_statement,
        _raw_value(record, "Guideword"),
        _raw_value(record, "Lexical Range"),
    ]
    return " " + _norm(" ".join(part for part in parts if part)) + " "


def _raw_value(record: RawEGPRecord, key: str) -> str | None:
    if not record.raw_payload:
        return None
    value = record.raw_payload.get(key)
    if value is None:
        return None
    return str(value)


def _contains(haystack: str, term: str) -> bool:
    normalized_term = _norm(term)
    if not normalized_term:
        return False
    if re.fullmatch(r"[a-z0-9]+", normalized_term):
        return f" {normalized_term} " in haystack
    return normalized_term in haystack


def _norm(value: object) -> str:
    if value is None:
        return ""
    text = str(value).casefold()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("…", " ")
    text = re.sub(r"[^a-z0-9'+/-]+", " ", text)
    text = text.replace("/", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text
