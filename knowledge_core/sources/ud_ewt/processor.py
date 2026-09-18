from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge_core.sources.ud_ewt.evidence import (
    build_grammar_structural_evidence,
    build_structural_inventory,
)
from knowledge_core.sources.ud_ewt.models import (
    SkillStructuralEvidence,
    UDDependencyEdge,
    UDMorphFeature,
    UDSentenceRecord,
    UDTokenRecord,
    UDValidationResult,
)
from knowledge_core.sources.ud_ewt.parser import parse_release_files, released_conllu_paths
from knowledge_core.sources.ud_ewt.paths import (
    DEFAULT_SOURCE_INVENTORY_REPORT,
    SOURCE_KEY,
)
from knowledge_core.sources.ud_ewt.reporting import (
    build_grammar_evidence_report,
    build_ingestion_report,
    write_ingestion_outputs,
    write_reports,
)
from knowledge_core.sources.ud_ewt.validator import validate_ud_ewt_ingestion


@dataclass(slots=True)
class UDEWTIngestionDataset:
    ud_version: str
    files: dict[str, Path]
    sentences: list[UDSentenceRecord]
    tokens: list[UDTokenRecord]
    dependencies: list[UDDependencyEdge]
    morphology: list[UDMorphFeature]
    structural_inventory: dict[str, Any]
    evidence: list[SkillStructuralEvidence]
    validation: UDValidationResult
    ingestion_report: dict[str, Any]
    structural_inventory_report: dict[str, Any]
    grammar_evidence_report: dict[str, Any]
    output_paths: dict[str, Path]
    report_paths: dict[str, Path]


def build_ud_ewt_dataset(
    *,
    root_dir: str | Path,
    source_inventory_report: str | Path = DEFAULT_SOURCE_INVENTORY_REPORT,
) -> UDEWTIngestionDataset:
    root = Path(root_dir)
    files = released_conllu_paths(root)
    inventory = _read_inventory(source_inventory_report)
    ud_version = inventory.get("detected_version") or "unavailable"

    sentences = list(parse_release_files(root))
    tokens = [token for sentence in sentences for token in sentence.tokens]
    dependencies = build_dependency_edges(sentences)
    morphology = build_morphology_features(tokens)
    structural_inventory = build_structural_inventory(sentences)
    evidence = build_grammar_structural_evidence(sentences, ud_version=ud_version)
    validation = validate_ud_ewt_ingestion(
        sentences=sentences,
        tokens=tokens,
        dependencies=dependencies,
        evidence=evidence,
        expected_sentence_counts=_expected_counts(inventory, "sentence_counts"),
        expected_token_counts=_expected_counts(inventory, "token_counts"),
        required_files=files,
    )
    ingestion_report = build_ingestion_report(
        ud_version=ud_version,
        files=files,
        sentences=sentences,
        tokens=tokens,
        dependencies=dependencies,
        morphology=morphology,
        validation=validation,
    )
    structural_inventory_report = {
        "source_key": SOURCE_KEY,
        "ud_version": ud_version,
        "inventory": structural_inventory,
        "sentence_count": len(sentences),
        "syntactic_token_count": sum(
            1 for token in tokens if not token.is_multiword and not token.is_empty_node
        ),
        "multiword_token_count": sum(1 for token in tokens if token.is_multiword),
        "empty_node_count": sum(1 for token in tokens if token.is_empty_node),
    }
    grammar_evidence_report = build_grammar_evidence_report(
        evidence,
        validation=validation,
    )
    return UDEWTIngestionDataset(
        ud_version=ud_version,
        files=files,
        sentences=sentences,
        tokens=tokens,
        dependencies=dependencies,
        morphology=morphology,
        structural_inventory=structural_inventory,
        evidence=evidence,
        validation=validation,
        ingestion_report=ingestion_report,
        structural_inventory_report=structural_inventory_report,
        grammar_evidence_report=grammar_evidence_report,
        output_paths={},
        report_paths={},
    )


def run_ud_ewt_ingestion(
    *,
    root_dir: str | Path,
    interim_dir: str | Path,
    review_dir: str | Path,
    reports_dir: str | Path,
    source_inventory_report: str | Path = DEFAULT_SOURCE_INVENTORY_REPORT,
    dry_run: bool = False,
) -> UDEWTIngestionDataset:
    dataset = build_ud_ewt_dataset(
        root_dir=root_dir,
        source_inventory_report=source_inventory_report,
    )
    output_paths: dict[str, Path] = {}
    report_paths: dict[str, Path] = {}
    if not dry_run:
        output_paths = write_ingestion_outputs(
            sentences=dataset.sentences,
            tokens=dataset.tokens,
            dependencies=dataset.dependencies,
            morphology=dataset.morphology,
            evidence=dataset.evidence,
            interim_dir=interim_dir,
            review_dir=review_dir,
        )
        ingestion_report = build_ingestion_report(
            ud_version=dataset.ud_version,
            files=dataset.files,
            sentences=dataset.sentences,
            tokens=dataset.tokens,
            dependencies=dataset.dependencies,
            morphology=dataset.morphology,
            validation=dataset.validation,
            output_paths=output_paths,
        )
        report_paths = write_reports(
            ingestion_report=ingestion_report,
            structural_inventory_report=dataset.structural_inventory_report,
            grammar_evidence_report=dataset.grammar_evidence_report,
            reports_dir=reports_dir,
        )
        dataset.ingestion_report = ingestion_report
    dataset.output_paths = output_paths
    dataset.report_paths = report_paths
    return dataset


def build_dependency_edges(sentences: list[UDSentenceRecord]) -> list[UDDependencyEdge]:
    edges: list[UDDependencyEdge] = []
    for sentence in sentences:
        for token in sentence.tokens:
            if token.is_multiword:
                continue
            if token.head and token.deprel:
                edges.append(
                    UDDependencyEdge(
                        sentence_id=sentence.sentence_id,
                        split=sentence.split,
                        head_token_id=token.head,
                        dependent_token_id=token.token_id,
                        relation=token.deprel,
                        enhanced=False,
                        metadata={"source": "HEAD/DEPREL"},
                    ),
                )
            for dep in token.deps:
                edges.append(
                    UDDependencyEdge(
                        sentence_id=sentence.sentence_id,
                        split=sentence.split,
                        head_token_id=dep["head"],
                        dependent_token_id=token.token_id,
                        relation=dep["relation"],
                        enhanced=True,
                        metadata={"source": "DEPS"},
                    ),
                )
    return edges


def build_morphology_features(tokens: list[UDTokenRecord]) -> list[UDMorphFeature]:
    rows: list[UDMorphFeature] = []
    for token in tokens:
        if token.is_multiword:
            continue
        for feature_name, values in token.feats.items():
            for feature_value in values:
                rows.append(
                    UDMorphFeature(
                        token_ref=token.token_ref,
                        sentence_id=token.sentence_id,
                        split=token.split,
                        token_id=token.token_id,
                        feature_name=feature_name,
                        feature_value=feature_value,
                    ),
                )
    return rows


def _read_inventory(path: str | Path) -> dict[str, Any]:
    inventory_path = Path(path)
    if not inventory_path.exists():
        return {}
    return json.loads(inventory_path.read_text(encoding="utf-8"))


def _expected_counts(inventory: dict[str, Any], key: str) -> dict[str, int]:
    counts = {}
    for split, payload in inventory.get(key, {}).items():
        if isinstance(payload, dict) and isinstance(payload.get("count"), int):
            counts[split] = payload["count"]
    return counts

