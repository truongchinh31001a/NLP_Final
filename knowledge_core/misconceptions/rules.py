from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


MISCONCEPTION_MINING_RULE_VERSION = "misconception_mining_rules_v1"


@dataclass(frozen=True, slots=True)
class MisconceptionPatternRule:
    pattern_key: str
    name: str
    description: str
    expected_pattern: str
    observed_pattern: str
    diagnostic_rule: str
    reason: str


def pattern_rule_for(
    *,
    canonical_skill_id: str,
    error_category: str,
    error_subtype: str | None,
    source_labels: list[str],
) -> MisconceptionPatternRule:
    source_label_text = ", ".join(sorted(set(source_labels))) or "unknown source label"
    if (
        canonical_skill_id == "grammar.present_simple.third_person_s"
        and error_category == "subject_verb_agreement"
    ):
        return MisconceptionPatternRule(
            pattern_key="missing_or_wrong_third_person_s_agreement",
            name="Possible missing or wrong third-person singular -s agreement",
            description=(
                "Learner output is source-marked as a verb-agreement error in contexts "
                "aligned to the present simple third-person -s skill."
            ),
            expected_pattern=(
                "A third-person singular subject in present simple normally takes a "
                "finite verb form marked with -s or -es where required."
            ),
            observed_pattern=(
                "The learner response contains a source-native verb-agreement error "
                f"label ({source_label_text})."
            ),
            diagnostic_rule=(
                "If a source-native verb-agreement error maps to "
                "grammar.present_simple.third_person_s, group it as a pending "
                "third-person -s agreement misconception candidate."
            ),
            reason=(
                "The source label is strong evidence of agreement trouble, but it "
                "does not by itself prove a stable learner misconception."
            ),
        )

    subtype_text = error_subtype or "unspecified"
    return MisconceptionPatternRule(
        pattern_key=f"{error_category}.{subtype_text}",
        name=f"Possible {error_category.replace('_', ' ')} difficulty",
        description=(
            "Learner errors with the same normalized category and canonical skill "
            "are grouped as an interpretable pending misconception candidate."
        ),
        expected_pattern=f"Expected accurate use of {canonical_skill_id}.",
        observed_pattern=(
            f"Source-native labels ({source_label_text}) normalize to "
            f"{error_category}/{subtype_text}."
        ),
        diagnostic_rule=(
            "Group by canonical_skill_id, normalized error category, normalized "
            "subtype, and source label set."
        ),
        reason=(
            "This is a deterministic grouping candidate and requires human review "
            "before acceptance."
        ),
    )


def make_misconception_id(
    *,
    canonical_skill_id: str,
    pattern_key: str,
    error_category: str,
    error_subtype: str | None,
    source_labels: list[str],
) -> str:
    payload = {
        "canonical_skill_id": canonical_skill_id,
        "error_category": error_category,
        "error_subtype": error_subtype,
        "pattern_key": pattern_key,
        "source_labels": sorted(set(source_labels)),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "mis_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def severity_for(*, evidence_count: int, max_source_frequency: float) -> str:
    if evidence_count >= 1000 or max_source_frequency >= 0.05:
        return "high"
    if evidence_count >= 50 or max_source_frequency >= 0.005:
        return "medium"
    return "low"


def confidence_for(
    *,
    average_mapping_confidence: float,
    evidence_count: int,
    source_count: int,
) -> float:
    confidence = average_mapping_confidence
    if evidence_count >= 100:
        confidence += 0.08
    elif evidence_count >= 20:
        confidence += 0.04
    if source_count >= 2:
        confidence += 0.05
    return min(round(confidence, 3), 0.85)
