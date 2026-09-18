from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET, CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.sources.ud_ewt.models import (
    SkillStructuralEvidence,
    UDDependencyEdge,
    UDSentenceRecord,
    UDTokenRecord,
    UDValidationIssue,
    UDValidationResult,
)


EXPECTED_SPLITS = {"train", "dev", "test"}


def validate_ud_ewt_ingestion(
    *,
    sentences: Sequence[UDSentenceRecord],
    tokens: Sequence[UDTokenRecord],
    dependencies: Sequence[UDDependencyEdge],
    evidence: Sequence[SkillStructuralEvidence],
    expected_sentence_counts: dict[str, int],
    expected_token_counts: dict[str, int],
    required_files: dict[str, Path],
) -> UDValidationResult:
    issues: list[UDValidationIssue] = []
    sentence_counts = Counter(sentence.split for sentence in sentences)
    syntactic_tokens = [
        token
        for token in tokens
        if not token.is_multiword and not token.is_empty_node
    ]
    token_counts = Counter(token.split for token in syntactic_tokens)
    parsed_splits = sorted(sentence_counts)

    for split in sorted(EXPECTED_SPLITS):
        if split not in required_files or not required_files[split].exists():
            issues.append(
                UDValidationIssue(
                    severity="error",
                    code="missing_released_file",
                    message=f"Released UD EWT {split} file is missing",
                    split=split,
                ),
            )
        if split not in sentence_counts:
            issues.append(
                UDValidationIssue(
                    severity="error",
                    code="missing_split",
                    message=f"UD EWT split was not parsed: {split}",
                    split=split,
                ),
            )

    for split, expected in expected_sentence_counts.items():
        actual = sentence_counts.get(split, 0)
        if actual != expected:
            issues.append(
                UDValidationIssue(
                    severity="error",
                    code="sentence_count_mismatch",
                    message=f"Expected {expected} {split} sentences; parsed {actual}",
                    split=split,
                ),
            )

    for split, expected in expected_token_counts.items():
        actual = token_counts.get(split, 0)
        if actual != expected:
            issues.append(
                UDValidationIssue(
                    severity="error",
                    code="token_count_mismatch",
                    message=f"Expected {expected} {split} syntactic tokens; parsed {actual}",
                    split=split,
                ),
            )

    token_ids_by_sentence: dict[str, set[str]] = defaultdict(set)
    for token in tokens:
        if not token.is_multiword:
            token_ids_by_sentence[token.sentence_id].add(token.token_id)
        if token.feats_text and not token.feats:
            issues.append(
                UDValidationIssue(
                    severity="error",
                    code="unparsed_feats",
                    message="Token has FEATS text but parsed FEATS is empty",
                    split=token.split,
                    sentence_id=token.sentence_id,
                    token_id=token.token_id,
                ),
            )

    for edge in dependencies:
        ids = token_ids_by_sentence.get(edge.sentence_id, set())
        if edge.dependent_token_id not in ids:
            issues.append(
                UDValidationIssue(
                    severity="error",
                    code="invalid_dependency_dependent",
                    message="Dependency dependent token does not resolve",
                    split=edge.split,
                    sentence_id=edge.sentence_id,
                    token_id=edge.dependent_token_id,
                ),
            )
        if edge.head_token_id != "0" and edge.head_token_id not in ids:
            issues.append(
                UDValidationIssue(
                    severity="error",
                    code="invalid_dependency_head",
                    message="Dependency head token does not resolve",
                    split=edge.split,
                    sentence_id=edge.sentence_id,
                    token_id=edge.head_token_id,
                ),
            )

    invalid_evidence_skills = sorted(
        {
            item.canonical_skill_id
            for item in evidence
            if item.canonical_skill_id not in CANONICAL_GRAMMAR_V1_SKILL_SET
        },
    )
    for skill_id in invalid_evidence_skills:
        issues.append(
            UDValidationIssue(
                severity="error",
                code="invalid_canonical_skill_reference",
                message=f"Structural evidence references unknown canonical skill: {skill_id}",
            ),
        )

    return UDValidationResult(
        issues=issues,
        parsed_splits=parsed_splits,
        sentence_counts=dict(sorted(sentence_counts.items())),
        token_counts=dict(sorted(token_counts.items())),
        expected_sentence_counts=dict(sorted(expected_sentence_counts.items())),
        expected_token_counts=dict(sorted(expected_token_counts.items())),
        taxonomy_unchanged=len(CANONICAL_GRAMMAR_V1_SKILLS) == 43,
        no_new_canonical_skills=not invalid_evidence_skills,
        no_cefr_inference_introduced=True,
    )

