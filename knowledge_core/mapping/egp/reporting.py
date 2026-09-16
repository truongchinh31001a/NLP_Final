from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.mapping.egp.models import (
    EGPCanonicalMapping,
    MappingValidationResult,
)
from knowledge_core.sources.egp.models import (
    RawEGPRecord,
    SourceRecordExclusion,
    ValidationResult,
    now_utc,
)
from knowledge_core.sources.egp.paths import (
    DEFAULT_EGP_REPORTS_DIR,
    DEFAULT_EGP_REVIEW_DIR,
    DEFAULT_INTERIM_GRAMMAR_DIR,
)
from knowledge_core.sources.egp.reporting import EGPOutputError


MAPPINGS_JSONL_OUTPUT_NAME = "egp_mappings.jsonl"
MAPPINGS_PARQUET_OUTPUT_NAME = "egp_mappings.parquet"
REVIEW_QUEUE_NAME = "egp_mapping_review.csv"
MAPPING_REPORT_NAME = "mapping_report.json"


def write_mappings_jsonl(
    mappings: Sequence[EGPCanonicalMapping],
    destination: str | Path,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for mapping in mappings:
            handle.write(
                json.dumps(
                    mapping.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            handle.write("\n")
    return path


def write_mappings_parquet(
    mappings: Sequence[EGPCanonicalMapping],
    destination: str | Path,
) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise EGPOutputError("pyarrow is required to write EGP mappings") from exc

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("mapping_id", pa.string()),
            ("source_record_id", pa.string()),
            ("canonical_skill", pa.string()),
            ("secondary_candidates", pa.string()),
            ("status", pa.string()),
            ("confidence", pa.float64()),
            ("reason", pa.string()),
            ("matched_terms", pa.string()),
            ("review_status", pa.string()),
            ("reviewer_note", pa.string()),
        ],
    )
    rows = [_mapping_parquet_row(mapping) for mapping in mappings]
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path)
    return path


def write_mapping_outputs(
    mappings: Sequence[EGPCanonicalMapping],
    interim_dir: str | Path = DEFAULT_INTERIM_GRAMMAR_DIR,
) -> dict[str, Path]:
    output_dir = Path(interim_dir)
    return {
        "jsonl": write_mappings_jsonl(mappings, output_dir / MAPPINGS_JSONL_OUTPUT_NAME),
        "parquet": write_mappings_parquet(
            mappings,
            output_dir / MAPPINGS_PARQUET_OUTPUT_NAME,
        ),
    }


def write_review_queue(
    records: Sequence[RawEGPRecord],
    mappings: Sequence[EGPCanonicalMapping],
    review_dir: str | Path = DEFAULT_EGP_REVIEW_DIR,
) -> Path:
    path = Path(review_dir) / REVIEW_QUEUE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    records_by_id = {
        record.source_record_id: record
        for record in records
        if record.source_record_id
    }
    rows = []
    for mapping in mappings:
        if mapping.status == "exact" and mapping.confidence >= 0.9:
            continue
        record = records_by_id.get(mapping.source_record_id)
        if record is None:
            continue
        rows.append(_review_row(record, mapping))

    fieldnames = [
        "source_record_id",
        "source_file",
        "super_category",
        "sub_category",
        "cefr_level",
        "feature_type",
        "feature_name",
        "can_do_statement",
        "example",
        "proposed_skill",
        "secondary_candidates",
        "mapping_status",
        "confidence",
        "reason",
        "reviewer_decision",
        "reviewer_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def build_mapping_report(
    records: Sequence[RawEGPRecord],
    mappings: Sequence[EGPCanonicalMapping],
    *,
    raw_record_count: int | None = None,
    source_exclusions: Sequence[SourceRecordExclusion] = (),
    source_validation: ValidationResult | None = None,
    mapping_validation: MappingValidationResult | None = None,
    source_inspection_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapping_counts = Counter(mapping.status for mapping in mappings)
    review_counts = Counter(mapping.review_status for mapping in mappings)
    canonical_evidence = _canonical_evidence(mappings)
    skills_with_mapped_evidence = sorted(canonical_evidence.keys())
    zero_evidence_review = review_zero_evidence_skills(records)
    reviewed_evidence_skills = set(skills_with_mapped_evidence)
    reviewed_evidence_skills.update(
        item["canonical_skill"]
        for item in zero_evidence_review
        if item["review_result"] == "evidence_found"
    )
    skills_with_evidence = sorted(reviewed_evidence_skills)
    skills_with_zero_evidence = [
        skill
        for skill in CANONICAL_GRAMMAR_V1_SKILLS
        if skill not in reviewed_evidence_skills
    ]
    return {
        "run_at": now_utc().isoformat(),
        "source_files": {
            "total": len({record.source_file for record in records}),
            "paths": sorted({record.source_file for record in records}),
        },
        "source_records": {
            "raw_total": raw_record_count
            if raw_record_count is not None
            else len(records) + len(source_exclusions),
            "total": len(records),
            "excluded": len(source_exclusions),
            "cefr_distribution": _cefr_distribution(records),
            "category_distribution": dict(
                sorted(Counter(record.category_id for record in records).items()),
            ),
        },
        "source_exclusions": _source_exclusion_summary(source_exclusions),
        "zero_evidence_review": zero_evidence_review,
        "mapping_counts": {
            "exact": mapping_counts.get("exact", 0),
            "candidate": mapping_counts.get("candidate", 0),
            "ambiguous": mapping_counts.get("ambiguous", 0),
            "unmapped": mapping_counts.get("unmapped", 0),
        },
        "review_counts": {
            "pending": review_counts.get("pending", 0),
            "approved": review_counts.get("approved", 0),
            "rejected": review_counts.get("rejected", 0),
            "needs_review": review_counts.get("needs_review", 0),
        },
        "canonical_coverage": {
            "total_v1_skills": len(CANONICAL_GRAMMAR_V1_SKILLS),
            "skills_with_egp_evidence": len(skills_with_evidence),
            "skills_with_zero_egp_evidence": len(skills_with_zero_evidence),
            "coverage_ratio": (
                f"{len(skills_with_evidence)}/{len(CANONICAL_GRAMMAR_V1_SKILLS)}"
            ),
            "mapped_skills_with_egp_evidence": len(skills_with_mapped_evidence),
            "mapped_coverage_ratio": (
                f"{len(skills_with_mapped_evidence)}/"
                f"{len(CANONICAL_GRAMMAR_V1_SKILLS)}"
            ),
            "skills_with_zero_evidence": skills_with_zero_evidence,
            "skills_with_zero_mapped_evidence": [
                skill
                for skill in CANONICAL_GRAMMAR_V1_SKILLS
                if skill not in canonical_evidence
            ],
        },
        "categories_with_high_unmapped_rate": _high_unmapped_categories(records, mappings),
        "high_confidence_mappings": _mapping_samples(mappings, min_confidence=0.9),
        "ambiguous_mappings": _ambiguous_samples(mappings),
        "malformed_source_records": _source_error_samples(source_validation),
        "source_validation": _validation_summary(source_validation),
        "mapping_validation": _mapping_validation_summary(mapping_validation),
        "source_inspection": source_inspection_report["totals"]
        if source_inspection_report
        else None,
        "canonical_taxonomy_unchanged": True,
    }


def write_mapping_report(
    report: dict[str, Any],
    reports_dir: str | Path = DEFAULT_EGP_REPORTS_DIR,
) -> Path:
    path = Path(reports_dir) / MAPPING_REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def load_records_jsonl(path: str | Path) -> list[RawEGPRecord]:
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(RawEGPRecord.model_validate(json.loads(line)))
    return records


def load_mappings_jsonl(path: str | Path) -> list[EGPCanonicalMapping]:
    mappings = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                mappings.append(EGPCanonicalMapping.model_validate(json.loads(line)))
    return mappings


def _mapping_parquet_row(mapping: EGPCanonicalMapping) -> dict[str, Any]:
    payload = mapping.model_dump(mode="json")
    payload["secondary_candidates"] = json.dumps(
        payload["secondary_candidates"],
        ensure_ascii=False,
        sort_keys=True,
    )
    payload["matched_terms"] = json.dumps(
        payload["matched_terms"],
        ensure_ascii=False,
        sort_keys=True,
    )
    return payload


def review_zero_evidence_skills(
    records: Sequence[RawEGPRecord],
) -> list[dict[str, Any]]:
    review_specs = [
        (
            "grammar.present_simple.third_person_s",
            "likely_curated_skill",
            ("third person", "third-person", "3rd person", "-s", "-es"),
            "No downloaded present-simple EGP record explicitly targets third-person -s.",
        ),
        (
            "grammar.past_simple.finished_past",
            "likely_curated_skill",
            ("finished past", "past time", "specific past time"),
            "Past-simple EGP records are broader than the curated finished-past V1 atom.",
        ),
        (
            "grammar.past_continuous.interrupted_action",
            "likely_curated_skill",
            ("interrupted", "interruption"),
            "Downloaded past-continuous records cover background/progress but not interruption.",
        ),
        (
            "grammar.present_perfect.past_participle",
            "likely_curated_skill",
            ("have + '-ed'", "has + '-ed'", "haven't + '-ed'", "have you + '-ed'"),
            "EGP uses + '-ed' wording for present-perfect participle form.",
        ),
        (
            "grammar.future.will_spontaneous_decision",
            "no_evidence",
            ("spontaneous decision", "instant decision"),
            "No included future-will EGP record expresses spontaneous or instant decisions.",
        ),
        (
            "grammar.articles.first_vs_subsequent_mention",
            "likely_curated_skill",
            ("first mention", "subsequent mention"),
            "Downloaded article records do not explicitly encode first/subsequent mention.",
        ),
        (
            "grammar.conditionals.first_vs_second",
            "likely_curated_skill",
            ("first vs second", "contrast first and second"),
            "Conditional EGP records cover individual forms but not a contrast skill.",
        ),
    ]
    return [
        _zero_evidence_review_row(records, *spec)
        for spec in review_specs
    ]


def _zero_evidence_review_row(
    records: Sequence[RawEGPRecord],
    canonical_skill: str,
    fallback_status: str,
    terms: tuple[str, ...],
    fallback_reason: str,
) -> dict[str, Any]:
    matches = [
        record
        for record in records
        if any(_term_in_record(record, term) for term in terms)
    ]
    if matches:
        return {
            "canonical_skill": canonical_skill,
            "review_result": "evidence_found",
            "supporting_source_record_ids": [
                record.source_record_id
                for record in matches
                if record.source_record_id
            ],
            "matched_terms": list(terms),
            "reason": "Downloaded EGP wording appears to express this concept.",
        }
    return {
        "canonical_skill": canonical_skill,
        "review_result": fallback_status,
        "supporting_source_record_ids": [],
        "matched_terms": list(terms),
        "reason": fallback_reason,
    }


def _review_row(
    record: RawEGPRecord,
    mapping: EGPCanonicalMapping,
) -> dict[str, Any]:
    return {
        "source_record_id": record.source_record_id,
        "source_file": record.source_file,
        "super_category": record.super_category,
        "sub_category": record.sub_category,
        "cefr_level": record.cefr_level,
        "feature_type": record.feature_type,
        "feature_name": record.feature_name,
        "can_do_statement": record.can_do_statement,
        "example": record.example,
        "proposed_skill": mapping.canonical_skill,
        "secondary_candidates": ";".join(mapping.secondary_candidates),
        "mapping_status": mapping.status,
        "confidence": mapping.confidence,
        "reason": mapping.reason,
        "reviewer_decision": "",
        "reviewer_note": "",
    }


def _canonical_evidence(
    mappings: Sequence[EGPCanonicalMapping],
) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = defaultdict(list)
    for mapping in mappings:
        if mapping.canonical_skill:
            evidence[mapping.canonical_skill].append(mapping.source_record_id)
        for secondary in mapping.secondary_candidates:
            evidence[secondary].append(mapping.source_record_id)
    return evidence


def _source_exclusion_summary(
    exclusions: Sequence[SourceRecordExclusion],
) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    for exclusion in exclusions:
        category_counts[exclusion.category_id] += 1
        for reason in exclusion.reason_codes:
            reason_counts[reason] += 1
    return {
        "excluded_records": len(exclusions),
        "reason_counts": dict(sorted(reason_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "records": [
            exclusion.model_dump(mode="json")
            for exclusion in exclusions
        ],
    }


def _cefr_distribution(records: Sequence[RawEGPRecord]) -> dict[str, int]:
    return dict(sorted(Counter(record.cefr_level for record in records).items()))


def _term_in_record(record: RawEGPRecord, term: str) -> bool:
    haystack = " ".join(
        value
        for value in [
            record.category_id,
            record.super_category,
            record.sub_category,
            record.feature_type,
            record.feature_name,
            record.can_do_statement,
        ]
        if value
    ).casefold()
    return term.casefold() in haystack


def _high_unmapped_categories(
    records: Sequence[RawEGPRecord],
    mappings: Sequence[EGPCanonicalMapping],
) -> list[dict[str, Any]]:
    record_categories = {
        record.source_record_id: record.category_id
        for record in records
        if record.source_record_id
    }
    totals: Counter[str] = Counter()
    unmapped: Counter[str] = Counter()
    for mapping in mappings:
        category_id = record_categories.get(mapping.source_record_id)
        if not category_id:
            continue
        totals[category_id] += 1
        if mapping.status in {"ambiguous", "unmapped"}:
            unmapped[category_id] += 1
    rows = []
    for category_id, total in sorted(totals.items()):
        rate = unmapped[category_id] / total if total else 0.0
        if rate >= 0.5:
            rows.append(
                {
                    "category_id": category_id,
                    "records": total,
                    "ambiguous_or_unmapped": unmapped[category_id],
                    "rate": round(rate, 4),
                },
            )
    return rows


def _mapping_samples(
    mappings: Sequence[EGPCanonicalMapping],
    *,
    min_confidence: float,
) -> list[dict[str, Any]]:
    return [
        _mapping_sample(mapping)
        for mapping in mappings
        if mapping.confidence >= min_confidence and mapping.canonical_skill is not None
    ][:50]


def _ambiguous_samples(mappings: Sequence[EGPCanonicalMapping]) -> list[dict[str, Any]]:
    return [
        _mapping_sample(mapping)
        for mapping in mappings
        if mapping.status == "ambiguous"
    ][:50]


def _mapping_sample(mapping: EGPCanonicalMapping) -> dict[str, Any]:
    return {
        "source_record_id": mapping.source_record_id,
        "canonical_skill": mapping.canonical_skill,
        "secondary_candidates": mapping.secondary_candidates,
        "status": mapping.status,
        "confidence": mapping.confidence,
        "reason": mapping.reason,
        "matched_terms": mapping.matched_terms,
    }


def _source_error_samples(
    validation: ValidationResult | None,
) -> list[dict[str, Any]]:
    if validation is None:
        return []
    return [
        issue.model_dump(mode="json")
        for issue in validation.errors
    ][:50]


def _validation_summary(validation: ValidationResult | None) -> dict[str, int] | None:
    if validation is None:
        return None
    return {
        "records": validation.total_records,
        "errors": validation.error_count,
        "warnings": validation.warning_count,
    }


def _mapping_validation_summary(
    validation: MappingValidationResult | None,
) -> dict[str, int] | None:
    if validation is None:
        return None
    return {
        "records": validation.total_records,
        "mappings": validation.total_mappings,
        "errors": validation.error_count,
        "warnings": validation.warning_count,
    }
