from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET
from knowledge_core.normalization.corpus_errors.models import ErrorSkillMapping
from knowledge_core.normalization.error_taxonomy.ids import (
    make_normalized_error_id,
    stable_hash,
)
from knowledge_core.normalization.error_taxonomy.models import (
    ErrorInstance,
    MappingStatus,
    NormalizedErrorInstance,
)
from knowledge_core.normalization.error_taxonomy.vocabulary import (
    ERROR_TAXONOMY_VERSION,
    NormalizedErrorCategory,
)


NORMALIZATION_RULE_VERSION = "corpus_error_normalization_rules_v1"
SKILL_MAPPING_RULE_VERSION = "corpus_error_skill_mapping_rules_v1"

_CLC_ATOMIC_RE = re.compile(r"[A-Z]+")
_MULTI_LABEL_MARKERS = (" and ", ";", ",")


@dataclass(frozen=True, slots=True)
class NormalizationRule:
    category: NormalizedErrorCategory
    subtype: str | None
    status: MappingStatus
    confidence: float
    reason: str
    review_required: bool = False


def normalize_error_instance(error: ErrorInstance) -> NormalizedErrorInstance:
    """Normalize one source-native ErrorInstance with pydantic validation."""

    return NormalizedErrorInstance.model_validate(normalize_error_payload(error.model_dump(mode="json")))


def normalize_error_payload(error_payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize one ErrorInstance payload without copying source learner text."""

    source_key = str(error_payload.get("source_key") or "")
    label_payload = error_payload.get("source_native_label") or {}
    label = str(label_payload.get("label") or "").strip()
    label_system = str(label_payload.get("label_system") or "").strip()
    rule, label_metadata = rule_for_label(source_key=source_key, label=label)
    skill_candidates = canonical_skill_candidates(
        source_key=source_key,
        label=label,
        rule=rule,
        label_metadata=label_metadata,
    )
    error_instance_id = str(error_payload["error_instance_id"])
    normalized_id = make_normalized_error_id(
        error_instance_id=error_instance_id,
        category=rule.category,
        subtype=rule.subtype,
    )
    return {
        "normalized_error_id": normalized_id,
        "error_instance_id": error_instance_id,
        "source_record_id": str(error_payload["source_record_id"]),
        "source_key": source_key,
        "category": rule.category,
        "subtype": rule.subtype,
        "status": rule.status,
        "confidence": rule.confidence,
        "reason": rule.reason,
        "review_status": "needs_review" if _requires_review(rule, label_metadata) else "pending",
        "taxonomy_version": ERROR_TAXONOMY_VERSION,
        "canonical_skill_candidates": skill_candidates,
        "metadata": {
            "source_label": label or None,
            "source_label_system": label_system or None,
            **label_metadata,
        },
        "provenance": {
            "normalization_rule_version": NORMALIZATION_RULE_VERSION,
            "source_error_instance_id": error_instance_id,
        },
    }


def skill_mapping_payloads(
    normalized_payload: dict[str, Any],
    error_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build deterministic candidate skill links for normalized errors."""

    mappings: list[dict[str, Any]] = []
    for skill_id in normalized_payload.get("canonical_skill_candidates", []):
        if skill_id not in CANONICAL_GRAMMAR_V1_SKILL_SET:
            raise ValueError(f"Unknown canonical skill candidate: {skill_id}")
        status: MappingStatus = "candidate"
        confidence = 0.62
        reason = (
            "Source-native verb-agreement label is relevant evidence for the "
            "present-simple third-person agreement skill, but the corpus label "
            "does not prove the exact tense/use; keep pending review."
        )
        mapping_id = make_error_skill_mapping_id(
            normalized_error_id=str(normalized_payload["normalized_error_id"]),
            canonical_skill_id=skill_id,
        )
        mappings.append(
            {
                "mapping_id": mapping_id,
                "normalized_error_id": normalized_payload["normalized_error_id"],
                "error_instance_id": normalized_payload["error_instance_id"],
                "source_record_id": normalized_payload["source_record_id"],
                "source_key": normalized_payload["source_key"],
                "canonical_skill_id": skill_id,
                "status": status,
                "confidence": confidence,
                "reason": reason,
                "review_status": "pending",
                "provenance": {
                    "skill_mapping_rule_version": SKILL_MAPPING_RULE_VERSION,
                    "source_label": (
                        (error_payload.get("source_native_label") or {}).get("label")
                    ),
                },
            },
        )
    return mappings


def build_error_skill_mapping(
    normalized: NormalizedErrorInstance,
    error: ErrorInstance,
) -> list[ErrorSkillMapping]:
    return [
        ErrorSkillMapping.model_validate(payload)
        for payload in skill_mapping_payloads(
            normalized.model_dump(mode="json"),
            error.model_dump(mode="json"),
        )
    ]


def make_error_skill_mapping_id(*, normalized_error_id: str, canonical_skill_id: str) -> str:
    payload = {
        "canonical_skill_id": canonical_skill_id,
        "normalized_error_id": normalized_error_id,
    }
    return f"errskill__{stable_hash(payload)}"


def rule_for_label(*, source_key: str, label: str) -> tuple[NormalizationRule, dict[str, Any]]:
    if source_key == "clc_fce":
        return _clc_rule(label)
    if source_key == "efcamdat":
        return _efcamdat_rule(label)
    return (
        NormalizationRule(
            category="unmapped",
            subtype=None,
            status="unmapped",
            confidence=0.0,
            reason=f"Unsupported learner corpus source for V1 normalization: {source_key}.",
            review_required=True,
        ),
        {"primary_source_label": label or None, "all_source_labels": [label] if label else []},
    )


def canonical_skill_candidates(
    *,
    source_key: str,
    label: str,
    rule: NormalizationRule,
    label_metadata: dict[str, Any],
) -> list[str]:
    if (
        source_key == "clc_fce"
        and rule.category == "subject_verb_agreement"
        and rule.status == "exact"
        and label_metadata.get("primary_source_label") == "AGV"
        and not label_metadata.get("compound_source_label")
    ):
        return ["grammar.present_simple.third_person_s"]
    return []


def _clc_rule(label: str) -> tuple[NormalizationRule, dict[str, Any]]:
    clean = label.strip().upper()
    atoms = _CLC_ATOMIC_RE.findall(clean)
    primary = atoms[0] if atoms else clean
    metadata = {
        "primary_source_label": primary or None,
        "all_source_labels": atoms or ([clean] if clean else []),
        "compound_source_label": _is_clc_compound(clean),
    }
    if not primary:
        return _unmapped("CLC FCE error label is missing."), metadata

    base_rule = _CLC_ATOMIC_RULES.get(primary) or _clc_pattern_rule(primary)
    if metadata["compound_source_label"] and base_rule.status != "unmapped":
        return (
            replace(
                base_rule,
                status="ambiguous",
                confidence=min(base_rule.confidence, 0.55),
                reason=(
                    f"{base_rule.reason} Compound CLC label preserves nested or "
                    "overlapping source annotation; review before using as a single category."
                ),
                review_required=True,
            ),
            metadata,
        )
    return base_rule, metadata


def _efcamdat_rule(label: str) -> tuple[NormalizationRule, dict[str, Any]]:
    clean = " ".join(label.strip().split())
    upper = clean.upper()
    multi_labels = _split_efcamdat_multi_label(clean)
    metadata = {
        "primary_source_label": multi_labels[0] if multi_labels else (clean or None),
        "all_source_labels": multi_labels or ([clean] if clean else []),
        "compound_source_label": len(multi_labels) > 1,
    }
    if not clean:
        return _unmapped("EFCAMDAT symbol label is missing."), metadata
    if len(multi_labels) > 1:
        return (
            NormalizationRule(
                category="other",
                subtype="multi_label",
                status="ambiguous",
                confidence=0.35,
                reason=(
                    "EFCAMDAT symbol contains multiple source-native labels; "
                    "preserve for review instead of flattening semantics."
                ),
                review_required=True,
            ),
            metadata,
        )
    rule = _EFCAMDAT_RULES.get(clean) or _EFCAMDAT_RULES.get(upper)
    if rule is not None:
        return rule, metadata
    return (
        NormalizationRule(
            category="unmapped",
            subtype=None,
            status="unmapped",
            confidence=0.0,
            reason="EFCAMDAT source label is not covered by V1 normalization rules.",
            review_required=True,
        ),
        metadata,
    )


def _clc_pattern_rule(label: str) -> NormalizationRule:
    if label.startswith("AG"):
        return _agreement_rule(label)
    if len(label) == 2:
        operation, word_class = label[0], label[1]
        if word_class == "A":
            return _rule("article", f"clc_{label.lower()}", "exact", 0.88, "CLC code targets article use.")
        if word_class in {"D", "Q"}:
            return _rule(
                "determiner",
                f"clc_{label.lower()}",
                "exact",
                0.86,
                "CLC code targets determiner or quantifier use.",
            )
        if word_class == "P":
            return _rule("punctuation", f"clc_{label.lower()}", "exact", 0.9, "CLC code targets punctuation.")
        if word_class == "T":
            return _rule(
                "preposition",
                f"clc_{label.lower()}",
                "exact",
                0.86,
                "CLC code targets preposition use.",
            )
        if word_class in {"J", "Y"}:
            return _rule(
                "adjective_adverb",
                f"clc_{label.lower()}",
                "exact",
                0.84,
                "CLC code targets adjective/adverb-class use.",
            )
        if word_class == "C":
            return _rule(
                "conjunction_clause",
                f"clc_{label.lower()}",
                "candidate",
                0.7,
                "CLC code targets a conjunction/clause-linking class; keep pending review.",
                review_required=True,
            )
        if word_class == "V":
            if operation in {"F", "I", "D"}:
                return _rule("verb_form", f"clc_{label.lower()}", "exact", 0.84, "CLC code targets verb form.")
            if operation == "R":
                return _rule(
                    "lexical_choice",
                    f"clc_{label.lower()}",
                    "candidate",
                    0.68,
                    "CLC replace-verb label may be lexical rather than grammatical form; keep pending review.",
                    review_required=True,
                )
            if operation in {"M", "U"}:
                return _rule(
                    "sentence_structure",
                    f"clc_{label.lower()}",
                    "candidate",
                    0.62,
                    "CLC missing/unnecessary verb label affects clause structure; keep pending review.",
                    review_required=True,
                )
        if word_class == "N":
            if operation in {"F", "D"}:
                return _rule("word_form", f"clc_{label.lower()}", "exact", 0.82, "CLC code targets noun form.")
            if operation == "R":
                return _rule("lexical_choice", f"clc_{label.lower()}", "exact", 0.86, "CLC code targets noun replacement.")
            if operation == "C":
                return _rule(
                    "noun_number",
                    f"clc_{label.lower()}",
                    "candidate",
                    0.72,
                    "CLC noun countability label is compatible with noun-number/countability errors.",
                    review_required=True,
                )
            return _rule(
                "other",
                f"clc_{label.lower()}",
                "ambiguous",
                0.45,
                "CLC noun-class operation is too broad for a V1 grammar category.",
                review_required=True,
            )
    if label in {"M", "R", "U"}:
        return _rule(
            "other",
            f"clc_{label.lower()}",
            "ambiguous",
            0.35,
            "CLC operation-only label lacks a word-class target.",
            review_required=True,
        )
    return _unmapped(f"CLC FCE source label '{label}' is not covered by V1 normalization rules.")


def _agreement_rule(label: str) -> NormalizationRule:
    target = label[-1:]
    if target == "V":
        return _rule(
            "subject_verb_agreement",
            "clc_agv",
            "exact",
            0.95,
            "CLC README defines AGV as a verb agreement error.",
        )
    if target == "N":
        return _rule(
            "noun_number",
            f"clc_{label.lower()}",
            "candidate",
            0.68,
            "CLC agreement label targets nouns; V1 treats it as noun-number/countability candidate.",
            review_required=True,
        )
    if target in {"D", "Q"}:
        return _rule(
            "determiner",
            f"clc_{label.lower()}",
            "candidate",
            0.66,
            "CLC agreement label targets determiners/quantifiers; keep pending review.",
            review_required=True,
        )
    if target in {"A", "J", "Y"}:
        return _rule(
            "adjective_adverb",
            f"clc_{label.lower()}",
            "candidate",
            0.62,
            "CLC agreement label targets adjective/adverb-class forms; keep pending review.",
            review_required=True,
        )
    return _rule(
        "other",
        f"clc_{label.lower()}",
        "ambiguous",
        0.4,
        "CLC agreement label target is outside deterministic V1 categories.",
        review_required=True,
    )


def _rule(
    category: NormalizedErrorCategory,
    subtype: str | None,
    status: MappingStatus,
    confidence: float,
    reason: str,
    *,
    review_required: bool = False,
) -> NormalizationRule:
    return NormalizationRule(
        category=category,
        subtype=subtype,
        status=status,
        confidence=confidence,
        reason=reason,
        review_required=review_required,
    )


def _unmapped(reason: str) -> NormalizationRule:
    return NormalizationRule(
        category="unmapped",
        subtype=None,
        status="unmapped",
        confidence=0.0,
        reason=reason,
        review_required=True,
    )


def _is_clc_compound(label: str) -> bool:
    return "(" in label or ")" in label


def _split_efcamdat_multi_label(label: str) -> list[str]:
    padded = f" {label.strip()} "
    if not any(marker in padded for marker in _MULTI_LABEL_MARKERS):
        return []
    parts = re.split(r"\s+and\s+|;|,", label, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _requires_review(rule: NormalizationRule, metadata: dict[str, Any]) -> bool:
    return rule.review_required or rule.status in {"ambiguous", "unmapped"} or bool(
        metadata.get("compound_source_label"),
    )


_CLC_ATOMIC_RULES: dict[str, NormalizationRule] = {
    "TV": _rule(
        "verb_tense",
        "clc_tv",
        "exact",
        0.95,
        "CLC README defines TV as an incorrect tense-of-verb error.",
    ),
    "AGV": _agreement_rule("AGV"),
    "MD": _rule(
        "determiner",
        "clc_md",
        "exact",
        0.95,
        "CLC README defines MD as a missing determiner error.",
    ),
    "RN": _rule(
        "lexical_choice",
        "clc_rn",
        "exact",
        0.9,
        "CLC README defines RN as a replace-noun error.",
    ),
    "FN": _rule(
        "word_form",
        "clc_fn",
        "exact",
        0.9,
        "CLC README defines FN as a wrong noun-form error.",
    ),
    "S": _rule("spelling", "clc_s", "exact", 0.9, "CLC code targets spelling."),
    "W": _rule("word_order", "clc_w", "exact", 0.9, "CLC code targets word order."),
    "CL": _rule(
        "lexical_choice",
        "clc_cl",
        "candidate",
        0.72,
        "CLC collocation-like label is lexical-choice evidence; keep pending review.",
        review_required=True,
    ),
    "CE": _rule(
        "noun_number",
        "clc_ce",
        "candidate",
        0.68,
        "CLC countability label is compatible with noun-number/countability errors.",
        review_required=True,
    ),
    "AS": _rule(
        "sentence_structure",
        "clc_as",
        "candidate",
        0.7,
        "CLC argument/sentence-structure label is broader than an atomic grammar skill.",
        review_required=True,
    ),
    "SX": _rule(
        "sentence_structure",
        "clc_sx",
        "candidate",
        0.64,
        "CLC sentence-level label is broader than a deterministic V1 grammar category.",
        review_required=True,
    ),
    "L": _rule(
        "lexical_choice",
        "clc_l",
        "candidate",
        0.62,
        "CLC lexical label is not safely reducible to a grammar skill.",
        review_required=True,
    ),
    "X": _rule(
        "other",
        "clc_x",
        "ambiguous",
        0.35,
        "CLC miscellaneous label is intentionally held for review.",
        review_required=True,
    ),
}

_EFCAMDAT_RULES: dict[str, NormalizationRule] = {
    "SP": _rule("spelling", "efcamdat_sp", "exact", 0.95, "EFCAMDAT SP marks spelling/orthographic errors."),
    "C": _rule(
        "spelling",
        "efcamdat_capitalization",
        "candidate",
        0.72,
        "EFCAMDAT C is treated as capitalization/orthographic evidence pending codebook review.",
        review_required=True,
    ),
    "WC": _rule("lexical_choice", "efcamdat_wc", "exact", 0.9, "EFCAMDAT WC marks word-choice errors."),
    "PU": _rule("punctuation", "efcamdat_pu", "exact", 0.95, "EFCAMDAT PU marks punctuation errors."),
    "AR": _rule("article", "efcamdat_ar", "exact", 0.88, "EFCAMDAT AR marks article-related errors."),
    "PR": _rule("preposition", "efcamdat_pr", "exact", 0.88, "EFCAMDAT PR marks preposition-related errors."),
    "VT": _rule("verb_tense", "efcamdat_vt", "exact", 0.9, "EFCAMDAT VT marks verb-tense errors."),
    "PL": _rule("noun_number", "efcamdat_pl", "exact", 0.88, "EFCAMDAT PL marks plural/number errors."),
    "WO": _rule("word_order", "efcamdat_wo", "exact", 0.88, "EFCAMDAT WO marks word-order errors."),
    "SI": _rule(
        "noun_number",
        "efcamdat_si",
        "candidate",
        0.62,
        "EFCAMDAT SI is treated as singular/number-related evidence pending codebook review.",
        review_required=True,
    ),
    "MW": _rule(
        "sentence_structure",
        "efcamdat_mw",
        "candidate",
        0.58,
        "EFCAMDAT MW marks a missing-word edit; target grammar category is broad.",
        review_required=True,
    ),
    "AG": _rule(
        "other",
        "efcamdat_ag",
        "ambiguous",
        0.45,
        "EFCAMDAT AG is a broad agreement label and is not forced into subject-verb agreement.",
        review_required=True,
    ),
    "D": _rule(
        "other",
        "efcamdat_deletion",
        "ambiguous",
        0.42,
        "EFCAMDAT D marks deletion/unnecessary material but not a deterministic grammar category.",
        review_required=True,
    ),
    "AS": _rule(
        "sentence_structure",
        "efcamdat_as",
        "candidate",
        0.5,
        "EFCAMDAT AS is sentence-structure-like but requires source-codebook review.",
        review_required=True,
    ),
    "RS": _rule(
        "sentence_structure",
        "efcamdat_rs",
        "candidate",
        0.5,
        "EFCAMDAT RS is sentence-structure-like but requires source-codebook review.",
        review_required=True,
    ),
    "IS": _rule("other", "efcamdat_is", "ambiguous", 0.35, "EFCAMDAT IS is not deterministic in V1.", review_required=True),
    "XC": _rule("other", "efcamdat_xc", "ambiguous", 0.35, "EFCAMDAT XC is not deterministic in V1.", review_required=True),
    "EX": _rule("other", "efcamdat_ex", "ambiguous", 0.35, "EFCAMDAT EX is not deterministic in V1.", review_required=True),
    "CO": _rule("other", "efcamdat_co", "ambiguous", 0.35, "EFCAMDAT CO is not deterministic in V1.", review_required=True),
    "NS": _rule("other", "efcamdat_ns", "ambiguous", 0.35, "EFCAMDAT NS is not deterministic in V1.", review_required=True),
    "PO": _rule("other", "efcamdat_po", "ambiguous", 0.35, "EFCAMDAT PO is not deterministic in V1.", review_required=True),
    "PS": _rule("other", "efcamdat_ps", "ambiguous", 0.35, "EFCAMDAT PS is not deterministic in V1.", review_required=True),
    "PH": _rule("other", "efcamdat_ph", "ambiguous", 0.35, "EFCAMDAT PH is not deterministic in V1.", review_required=True),
    "NSW": _rule("other", "efcamdat_nsw", "ambiguous", 0.35, "EFCAMDAT NSW is not deterministic in V1.", review_required=True),
    "HL": _rule("other", "efcamdat_hl", "ambiguous", 0.35, "EFCAMDAT HL is not deterministic in V1.", review_required=True),
    "Word Limit": _rule(
        "other",
        "efcamdat_word_limit",
        "exact",
        0.9,
        "EFCAMDAT Word Limit is a valid source annotation outside grammar categories.",
        review_required=True,
    ),
    "undefined": _unmapped("EFCAMDAT undefined label has no source-native semantics for V1."),
}
