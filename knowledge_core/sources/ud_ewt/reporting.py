from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.sources.ud_ewt.models import (
    SkillStructuralEvidence,
    UDDependencyEdge,
    UDMorphFeature,
    UDSentenceRecord,
    UDTokenRecord,
    UDValidationResult,
)
from knowledge_core.sources.ud_ewt.paths import DEFAULT_INTERIM_DIR, DEFAULT_REPORTS_DIR, DEFAULT_REVIEW_DIR, SOURCE_KEY


class UDEWTOutputError(RuntimeError):
    """Raised when UD EWT outputs cannot be written."""


def write_ingestion_outputs(
    *,
    sentences: Sequence[UDSentenceRecord],
    tokens: Sequence[UDTokenRecord],
    dependencies: Sequence[UDDependencyEdge],
    morphology: Sequence[UDMorphFeature],
    evidence: Sequence[SkillStructuralEvidence],
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
) -> dict[str, Path]:
    output_dir = Path(interim_dir)
    review_output_dir = Path(review_dir)
    return {
        "sentences_jsonl": write_jsonl(sentences, output_dir / "sentences.jsonl"),
        "tokens_parquet": write_tokens_parquet(tokens, output_dir / "tokens.parquet"),
        "dependencies_parquet": write_dependencies_parquet(
            dependencies,
            output_dir / "dependencies.parquet",
        ),
        "morphology_parquet": write_morphology_parquet(
            morphology,
            output_dir / "morphology.parquet",
        ),
        "grammar_structural_evidence_jsonl": write_jsonl(
            evidence,
            output_dir / "grammar_structural_evidence.jsonl",
        ),
        "review_csv": write_structural_evidence_review_csv(
            evidence,
            review_output_dir / "ud_grammar_structural_evidence_review.csv",
        ),
    }


def write_reports(
    *,
    ingestion_report: dict[str, Any],
    structural_inventory_report: dict[str, Any],
    grammar_evidence_report: dict[str, Any],
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
) -> dict[str, Path]:
    output_dir = Path(reports_dir)
    return {
        "ingestion_report": write_json(
            ingestion_report,
            output_dir / "ingestion_report.json",
        ),
        "structural_inventory_report": write_json(
            structural_inventory_report,
            output_dir / "structural_inventory_report.json",
        ),
        "grammar_evidence_report": write_json(
            grammar_evidence_report,
            output_dir / "grammar_evidence_report.json",
        ),
    }


def build_ingestion_report(
    *,
    ud_version: str,
    files: dict[str, Path],
    sentences: Sequence[UDSentenceRecord],
    tokens: Sequence[UDTokenRecord],
    dependencies: Sequence[UDDependencyEdge],
    morphology: Sequence[UDMorphFeature],
    validation: UDValidationResult,
    output_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    sentence_counts = Counter(sentence.split for sentence in sentences)
    syntactic_tokens = [
        token
        for token in tokens
        if not token.is_multiword and not token.is_empty_node
    ]
    token_counts = Counter(token.split for token in syntactic_tokens)
    multiword_count = sum(1 for token in tokens if token.is_multiword)
    empty_count = sum(1 for token in tokens if token.is_empty_node)
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    return {
        "source_key": SOURCE_KEY,
        "ud_version": ud_version,
        "files_parsed": {
            split: str(path).replace("\\", "/") for split, path in files.items()
        },
        "sentence_counts": dict(sorted(sentence_counts.items())),
        "token_counts": dict(sorted(token_counts.items())),
        "total_sentences": len(sentences),
        "total_syntactic_tokens": len(syntactic_tokens),
        "total_token_rows_including_multiword_and_empty": len(tokens),
        "multiword_token_count": multiword_count,
        "empty_node_count": empty_count,
        "dependency_edge_count": len(dependencies),
        "enhanced_dependency_edge_count": sum(1 for edge in dependencies if edge.enhanced),
        "morphology_row_count": len(morphology),
        "validation": validation.model_dump(mode="json"),
        "taxonomy": {
            "atomic_skill_count": len(CANONICAL_GRAMMAR_V1_SKILLS),
            "taxonomy_hash": taxonomy.taxonomy_hash,
            "taxonomy_unchanged": validation.taxonomy_unchanged,
        },
        "no_cefr_inference_introduced": validation.no_cefr_inference_introduced,
        "output_paths": {
            key: str(path).replace("\\", "/")
            for key, path in (output_paths or {}).items()
        },
        "definition_of_done_satisfied": validation.error_count == 0,
    }


def build_grammar_evidence_report(
    evidence: Sequence[SkillStructuralEvidence],
    *,
    validation: UDValidationResult,
) -> dict[str, Any]:
    by_status = Counter(item.status for item in evidence)
    by_skill = Counter(item.canonical_skill_id for item in evidence)
    candidate_review = [
        item.evidence_id
        for item in evidence
        if item.status in {"candidate", "ambiguous"} or item.review_status != "approved"
    ]
    return {
        "source_key": SOURCE_KEY,
        "total_structural_evidence": len(evidence),
        "status_counts": dict(sorted(by_status.items())),
        "canonical_skills_with_structural_evidence": sorted(by_skill),
        "canonical_skill_count_with_structural_evidence": len(by_skill),
        "candidate_mappings_requiring_review": candidate_review,
        "candidate_mappings_requiring_review_count": len(candidate_review),
        "no_new_canonical_skills": validation.no_new_canonical_skills,
        "notes": [
            "UD EWT evidence is structural linguistic support only.",
            "No learner errors, misconceptions, CEFR levels, or mastery claims are inferred.",
        ],
    }


def write_jsonl(records: Sequence[Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return path


def write_json(payload: Any, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_tokens_parquet(records: Sequence[UDTokenRecord], destination: str | Path) -> Path:
    schema = _pa().schema(
        [
            ("token_ref", _pa().string()),
            ("sentence_id", _pa().string()),
            ("source_key", _pa().string()),
            ("split", _pa().string()),
            ("token_id", _pa().string()),
            ("form", _pa().string()),
            ("lemma", _pa().string()),
            ("upos", _pa().string()),
            ("xpos", _pa().string()),
            ("feats", _pa().string()),
            ("feats_text", _pa().string()),
            ("head", _pa().string()),
            ("deprel", _pa().string()),
            ("deps", _pa().string()),
            ("deps_text", _pa().string()),
            ("misc", _pa().string()),
            ("misc_text", _pa().string()),
            ("is_multiword", _pa().bool_()),
            ("is_empty_node", _pa().bool_()),
            ("source_line_number", _pa().int64()),
        ],
    )
    rows = []
    for record in records:
        row = record.model_dump(mode="json")
        row["feats"] = json.dumps(row["feats"], ensure_ascii=False, sort_keys=True)
        row["deps"] = json.dumps(row["deps"], ensure_ascii=False, sort_keys=True)
        row["misc"] = json.dumps(row["misc"], ensure_ascii=False, sort_keys=True)
        rows.append(row)
    return _write_parquet(rows, schema, destination)


def write_dependencies_parquet(
    records: Sequence[UDDependencyEdge],
    destination: str | Path,
) -> Path:
    schema = _pa().schema(
        [
            ("sentence_id", _pa().string()),
            ("split", _pa().string()),
            ("head_token_id", _pa().string()),
            ("dependent_token_id", _pa().string()),
            ("relation", _pa().string()),
            ("enhanced", _pa().bool_()),
            ("metadata", _pa().string()),
        ],
    )
    rows = []
    for record in records:
        row = record.model_dump(mode="json")
        row["metadata"] = json.dumps(row["metadata"], ensure_ascii=False, sort_keys=True)
        rows.append(row)
    return _write_parquet(rows, schema, destination)


def write_morphology_parquet(
    records: Sequence[UDMorphFeature],
    destination: str | Path,
) -> Path:
    schema = _pa().schema(
        [
            ("token_ref", _pa().string()),
            ("sentence_id", _pa().string()),
            ("split", _pa().string()),
            ("token_id", _pa().string()),
            ("feature_name", _pa().string()),
            ("feature_value", _pa().string()),
        ],
    )
    rows = [record.model_dump(mode="json") for record in records]
    return _write_parquet(rows, schema, destination)


def write_structural_evidence_review_csv(
    evidence: Sequence[SkillStructuralEvidence],
    destination: str | Path,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "evidence_id",
        "canonical_skill_id",
        "pattern_type",
        "status",
        "review_status",
        "confidence",
        "occurrence_count",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in evidence:
            writer.writerow({field: getattr(item, field) for field in fieldnames})
    return path


def _write_parquet(rows: list[dict[str, Any]], schema: Any, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = _pa().Table.from_pylist(rows, schema=schema)
    _pq().write_table(table, path)
    return path


def _pa() -> Any:
    try:
        import pyarrow as pa
    except ImportError as exc:
        raise UDEWTOutputError("pyarrow is required to write UD EWT Parquet output") from exc
    return pa


def _pq() -> Any:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise UDEWTOutputError("pyarrow is required to write UD EWT Parquet output") from exc
    return pq

