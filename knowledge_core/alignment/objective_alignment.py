from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from knowledge_core.alignment.models import (
    ObjectiveAlignment,
    ObjectiveAlignmentConfig,
    ObjectiveRuleConfig,
)
from knowledge_core.sources.cefr.models import CEFRLearningObjectiveCandidate
from knowledge_core.sources.cefr.normalizer import normalize_whitespace


LEVEL_ORDER = {
    "Pre-A1": 0,
    "A1": 1,
    "A2": 2,
    "A2+": 3,
    "B1": 4,
    "B1+": 5,
    "B2": 6,
    "B2+": 7,
    "C1": 8,
    "C2": 9,
}


@dataclass(slots=True, frozen=True)
class SkillLevelContext:
    inferred_min_level: str | None
    inferred_primary_level: str | None


def align_objectives_for_skill(
    canonical_skill_id: str,
    objectives: Iterable[CEFRLearningObjectiveCandidate],
    config: ObjectiveAlignmentConfig,
    *,
    level_context: SkillLevelContext,
) -> list[ObjectiveAlignment]:
    rule = _rule_for_skill(canonical_skill_id, config)
    if rule is None:
        return []

    alignments: list[ObjectiveAlignment] = []
    for objective in objectives:
        if not _objective_level_allowed(
            objective.cefr_level,
            config,
            level_context=level_context,
        ):
            continue
        direct_terms = _matched_terms(objective.objective_text, rule.direct_terms)
        contextual_terms = _matched_terms(
            objective.objective_text,
            rule.contextual_terms,
        )
        if direct_terms:
            alignments.append(
                _alignment(
                    canonical_skill_id,
                    objective,
                    relevance="direct",
                    matched_terms=direct_terms,
                    config=config,
                    level_context=level_context,
                ),
            )
        elif contextual_terms:
            alignments.append(
                _alignment(
                    canonical_skill_id,
                    objective,
                    relevance="contextual",
                    matched_terms=contextual_terms,
                    config=config,
                    level_context=level_context,
                ),
            )

    return _limit_alignments(alignments, config.max_objectives_per_skill_per_mode)


def _alignment(
    canonical_skill_id: str,
    objective: CEFRLearningObjectiveCandidate,
    *,
    relevance: str,
    matched_terms: list[str],
    config: ObjectiveAlignmentConfig,
    level_context: SkillLevelContext,
) -> ObjectiveAlignment:
    confidence = _objective_confidence(
        objective.cefr_level,
        relevance=relevance,
        config=config,
        level_context=level_context,
    )
    reason = (
        f"CEFR objective matched {relevance} grammar-context term(s): "
        + ", ".join(matched_terms)
    )
    if level_context.inferred_primary_level:
        reason += f"; compared against EGP primary level {level_context.inferred_primary_level}."
    else:
        reason += "; no EGP-derived primary level was available."
    return ObjectiveAlignment(
        canonical_skill_id=canonical_skill_id,
        objective_id=objective.objective_id,
        source_record_id=objective.source_record_id,
        cefr_level=objective.cefr_level,
        relevance=relevance,  # type: ignore[arg-type]
        confidence=confidence,
        matched_terms=matched_terms,
        reason=reason,
    )


def _objective_confidence(
    objective_level: str,
    *,
    relevance: str,
    config: ObjectiveAlignmentConfig,
    level_context: SkillLevelContext,
) -> float:
    confidence = (
        config.direct_confidence
        if relevance == "direct"
        else config.contextual_confidence
    )
    primary_level = level_context.inferred_primary_level
    if primary_level:
        distance = _level_distance(objective_level, primary_level)
        if distance == 0:
            confidence += 0.08
        elif distance == 1:
            confidence += 0.04
    else:
        confidence -= 0.05
    ceiling = 0.86 if relevance == "direct" else 0.74
    return round(min(max(confidence, 0.0), ceiling), 4)


def _objective_level_allowed(
    objective_level: str,
    config: ObjectiveAlignmentConfig,
    *,
    level_context: SkillLevelContext,
) -> bool:
    primary_level = level_context.inferred_primary_level
    if primary_level is None:
        return True
    return (
        _level_distance(objective_level, primary_level)
        <= config.max_level_distance_for_aligned_skills
    )


def _level_distance(left: str, right: str) -> int:
    return abs(LEVEL_ORDER.get(left, 99) - LEVEL_ORDER.get(right, 99))


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    haystack = _normalize_match_text(text)
    matched: list[str] = []
    for term in terms:
        normalized_term = _normalize_match_text(term)
        if not normalized_term:
            continue
        if _contains_term(haystack, normalized_term):
            matched.append(term)
    return matched


def _contains_term(haystack: str, term: str) -> bool:
    if re.fullmatch(r"[a-z0-9]+", term):
        return f" {term} " in haystack
    return term in haystack


def _normalize_match_text(value: str) -> str:
    text = normalize_whitespace(value).casefold()
    text = text.replace("�", "'")
    text = re.sub(r"[^a-z0-9'+/-]+", " ", text)
    text = text.replace("/", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "


def _rule_for_skill(
    canonical_skill_id: str,
    config: ObjectiveAlignmentConfig,
) -> ObjectiveRuleConfig | None:
    for rule in config.rules:
        if rule.canonical_skill_id == canonical_skill_id:
            return rule
    return None


def _limit_alignments(
    alignments: list[ObjectiveAlignment],
    max_per_mode: int,
) -> list[ObjectiveAlignment]:
    direct = [
        alignment
        for alignment in alignments
        if alignment.relevance == "direct"
    ]
    contextual = [
        alignment
        for alignment in alignments
        if alignment.relevance == "contextual"
    ]
    return sorted(direct, key=_sort_key)[:max_per_mode] + sorted(
        contextual,
        key=_sort_key,
    )[:max_per_mode]


def _sort_key(alignment: ObjectiveAlignment) -> tuple[float, int, str]:
    return (
        -alignment.confidence,
        LEVEL_ORDER.get(alignment.cefr_level, 99),
        alignment.objective_id,
    )

