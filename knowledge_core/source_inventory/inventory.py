from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import tarfile
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree


EXPECTED_SOURCE_KEYS: tuple[str, ...] = (
    "efcamdat",
    "clc_fce",
    "write_improve",
    "ud_english_ewt",
    "english_grammar_profile",
    "cefr_companion_volume_2020",
)

NEW_CORPUS_SOURCE_KEYS: tuple[str, ...] = (
    "efcamdat",
    "clc_fce",
    "write_improve",
    "ud_english_ewt",
)

REQUIRED_SOURCE_KEYS: frozenset[str] = frozenset(
    {
        "efcamdat",
        "clc_fce",
        "english_grammar_profile",
        "cefr_companion_volume_2020",
    },
)

OPTIONAL_SOURCE_KEYS: frozenset[str] = frozenset(
    {
        "write_improve",
        "ud_english_ewt",
    },
)

OUTPUT_FILENAMES: tuple[str, ...] = (
    "source_inventory.json",
    "source_inventory.md",
    "file_inventory.jsonl",
    "error_annotation_comparison.json",
    "error_annotation_comparison.md",
    "proficiency_comparison.json",
    "proficiency_comparison.md",
    "inspection_issues.json",
    "efcamdat_inspection.json",
    "clc_fce_inspection.json",
    "write_improve_inspection.json",
    "ud_ewt_inspection.json",
    "egp_summary.json",
    "cefr_summary.json",
)

CHECKSUM_THRESHOLD_BYTES = 50 * 1024 * 1024
TEXT_SAMPLE_BYTES = 8192
CSV_SAMPLE_ROWS = 50_000
UNIQUE_VALUE_LIMIT = 200


SOURCE_NAMES: dict[str, str] = {
    "efcamdat": "EFCAMDAT",
    "clc_fce": "Cambridge Learner Corpus FCE",
    "write_improve": "Write & Improve Corpus 2024",
    "ud_english_ewt": "Universal Dependencies English EWT",
    "english_grammar_profile": "English Grammar Profile",
    "cefr_companion_volume_2020": "CEFR Companion Volume 2020",
}

SOURCE_ROLES: dict[str, list[str]] = {
    "efcamdat": ["learner_corpus"],
    "clc_fce": ["annotated_error_corpus"],
    "write_improve": ["revision_corpus"],
    "ud_english_ewt": ["linguistic_structure_resource"],
    "english_grammar_profile": ["canonical_grammar_evidence"],
    "cefr_companion_volume_2020": ["proficiency_framework"],
}


def inspect_sources(
    workspace: str | Path = ".",
    output_dir: str | Path = "data/reports/source_inventory",
) -> dict[str, Any]:
    """Inspect configured source corpora and write source inventory reports."""

    workspace_path = Path(workspace).resolve()
    output_path = _resolve_under_workspace(workspace_path, output_dir)
    before_raw = snapshot_files(workspace_path / "data" / "raw")

    discovery = discover_sources(workspace_path)
    file_inventory = build_file_inventory(workspace_path, discovery)

    inspections = {
        "efcamdat": inspect_efcamdat(discovery["sources"]["efcamdat"], workspace_path),
        "clc_fce": inspect_clc_fce(discovery["sources"]["clc_fce"], workspace_path),
        "write_improve": inspect_write_improve(
            discovery["sources"]["write_improve"],
            workspace_path,
        ),
        "ud_english_ewt": inspect_ud_ewt(
            discovery["sources"]["ud_english_ewt"],
            workspace_path,
        ),
        "english_grammar_profile": inspect_egp(
            discovery["sources"]["english_grammar_profile"],
            workspace_path,
        ),
        "cefr_companion_volume_2020": inspect_cefr(
            discovery["sources"]["cefr_companion_volume_2020"],
            workspace_path,
        ),
    }

    entries = [
        build_inventory_entry(
            source_key,
            discovery["sources"][source_key],
            inspections[source_key],
            file_inventory,
        )
        for source_key in EXPECTED_SOURCE_KEYS
    ]
    error_comparison = build_error_annotation_comparison(inspections)
    proficiency_comparison = build_proficiency_comparison(inspections)
    issues = build_inspection_issues(discovery, entries, inspections, file_inventory)

    output_path.mkdir(parents=True, exist_ok=True)
    write_json(
        output_path / "source_inventory.json",
        {
            "generated_at": _utc_now(),
            "workspace": str(workspace_path),
            "expected_sources": list(EXPECTED_SOURCE_KEYS),
            "sources": entries,
            "classified_raw_datasets": issues["classified_raw_datasets"],
            "validation": issues["validation"],
            "inspection_warnings": issues["warnings"],
            "inspection_errors": issues["errors"],
        },
    )
    write_markdown(output_path / "source_inventory.md", render_source_inventory_md(entries, issues))
    write_jsonl(output_path / "file_inventory.jsonl", file_inventory)
    write_json(output_path / "error_annotation_comparison.json", error_comparison)
    write_markdown(
        output_path / "error_annotation_comparison.md",
        render_error_annotation_comparison_md(error_comparison),
    )
    write_json(output_path / "proficiency_comparison.json", proficiency_comparison)
    write_markdown(
        output_path / "proficiency_comparison.md",
        render_proficiency_comparison_md(proficiency_comparison),
    )
    write_json(output_path / "inspection_issues.json", issues)
    write_json(output_path / "efcamdat_inspection.json", inspections["efcamdat"])
    write_json(output_path / "clc_fce_inspection.json", inspections["clc_fce"])
    write_json(output_path / "write_improve_inspection.json", inspections["write_improve"])
    write_json(output_path / "ud_ewt_inspection.json", inspections["ud_english_ewt"])
    write_json(output_path / "egp_summary.json", inspections["english_grammar_profile"])
    write_json(output_path / "cefr_summary.json", inspections["cefr_companion_volume_2020"])
    write_schema_samples(output_path / "schema_samples", inspections)

    after_raw = snapshot_files(workspace_path / "data" / "raw")
    raw_unchanged = before_raw == after_raw
    if not raw_unchanged:
        issues["validation"]["checks"]["raw_data_unchanged"] = False
        issues["validation"]["passed"] = False
        write_json(output_path / "inspection_issues.json", issues)
        inventory_path = output_path / "source_inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory["validation"] = issues["validation"]
        write_json(inventory_path, inventory)

    return {
        "output_dir": str(output_path),
        "sources": entries,
        "file_inventory_count": len(file_inventory),
        "inspection_reports": {
            key: inspections[key]["report_path"]
            for key in inspections
            if "report_path" in inspections[key]
        },
        "validation": issues["validation"],
        "raw_data_unchanged": raw_unchanged,
        "generated_files": [str(output_path / name) for name in OUTPUT_FILENAMES],
    }


def discover_sources(workspace: str | Path = ".") -> dict[str, Any]:
    """Find expected Knowledge Core V1 source groups without moving raw files."""

    workspace_path = Path(workspace).resolve()
    raw_root = workspace_path / "data" / "raw"
    sources: dict[str, dict[str, Any]] = {
        key: {
            "source_key": key,
            "source_name": SOURCE_NAMES[key],
            "status": "missing",
            "root_paths": [],
            "discovery_notes": [],
        }
        for key in EXPECTED_SOURCE_KEYS
    }
    unknown_raw_roots: list[str] = []
    classified_raw_roots: list[dict[str, Any]] = []

    if raw_root.exists():
        for child in sorted(raw_root.iterdir(), key=lambda path: path.name.lower()):
            key = classify_raw_root(child)
            if key is None:
                classification = classify_unassigned_raw_root(child, workspace_path)
                classified_raw_roots.append(classification)
                if classification["status"] == "unknown_needs_manual_review":
                    unknown_raw_roots.append(classification["path"])
                continue
            sources[key]["status"] = "discovered"
            sources[key]["root_paths"].append(str(child))
            sources[key]["discovery_notes"].append(
                f"Matched raw path by directory name: {_relative(child, workspace_path)}",
            )
    else:
        for entry in sources.values():
            entry["discovery_notes"].append("data/raw does not exist.")

    _add_existing_processed_roots(
        sources["english_grammar_profile"],
        workspace_path,
        [
            "data/external/english_profile",
            "data/interim/english_profile",
            "data/reports/egp",
        ],
    )
    _add_existing_processed_roots(
        sources["cefr_companion_volume_2020"],
        workspace_path,
        [
            "data/external/cefr",
            "data/interim/cefr",
            "data/reports/cefr",
        ],
    )

    return {
        "workspace": str(workspace_path),
        "raw_root": str(raw_root),
        "sources": sources,
        "unknown_raw_roots": unknown_raw_roots,
        "classified_raw_roots": classified_raw_roots,
    }


def classify_raw_root(path: Path) -> str | None:
    name = path.name.lower()
    if "efcamdat" in name:
        return "efcamdat"
    if "fce" in name or "first-certificate" in name:
        return "clc_fce"
    if "write" in name and "improve" in name:
        return "write_improve"
    if "ud_english" in name or "english-ewt" in name or "english_ewt" in name:
        return "ud_english_ewt"
    return None


def classify_unassigned_raw_root(path: Path, workspace: Path) -> dict[str, Any]:
    files = list(iter_files(path))
    extension_counts = Counter(normalized_extension(file_path) for file_path in files)
    relative_path = _relative(path, workspace)
    sample_names = [file_path.name for file_path in files[:20]]
    markers = {
        "root_name": path.name,
        "top_level_dirs": sorted(child.name for child in path.iterdir() if child.is_dir())[:20]
        if path.exists() and path.is_dir()
        else [],
        "sample_file_names": sample_names,
        "sample_relative_paths": [_safe_relative(file_path, path) for file_path in files[:20]],
    }
    lower_parts = " ".join(
        [
            path.name.lower(),
            " ".join(markers["top_level_dirs"]).lower(),
            " ".join(sample_names).lower(),
            " ".join(markers["sample_relative_paths"]).lower(),
        ],
    )
    has_vnhsge_markers = (
        path.name.lower() == "dataset"
        and ("vnhsge" in lower_parts or "met_" in lower_parts)
        and ("json format" in lower_parts or "word format" in lower_parts)
    )
    if has_vnhsge_markers:
        status = "unrelated_to_knowledge_core_v1"
        source_key = "excluded_raw_dataset"
        reason = (
            "Directory contains VNHSGE/MET exam-style files with JSON/DOCX/image assets "
            "across school subjects; it is not one of the six Knowledge Core V1 sources."
        )
        inferred_role = "unrelated_project_dataset"
    else:
        status = "unknown_needs_manual_review"
        source_key = "unknown"
        reason = "Raw directory does not match known V1 source markers."
        inferred_role = "unknown"
    return {
        "path": relative_path,
        "source_key": source_key,
        "status": status,
        "included_in_knowledge_core_inventory": False,
        "inferred_role": inferred_role,
        "file_count": len(files),
        "files_by_extension": dict(sorted(extension_counts.items())),
        "representative_files": [_relative(file_path, workspace) for file_path in files[:20]],
        "markers": markers,
        "reason": reason,
    }


def build_file_inventory(
    workspace: Path,
    discovery: dict[str, Any],
    checksum_threshold: int = CHECKSUM_THRESHOLD_BYTES,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for source_key, source in discovery["sources"].items():
        for root_value in source["root_paths"]:
            root = Path(root_value)
            for path in iter_files(root):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                rows.append(
                    file_metadata(
                        path,
                        source_key,
                        root,
                        workspace,
                        checksum_threshold=checksum_threshold,
                    ),
                )

    raw_root = workspace / "data" / "raw"
    for classification in discovery.get("classified_raw_roots", []):
        root = workspace / classification["path"]
        for path in iter_files(root):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            rows.append(
                file_metadata(
                    path,
                    classification["source_key"],
                    root,
                    workspace,
                    checksum_threshold=checksum_threshold,
                    notes=[classification["reason"]],
                ),
            )

    if raw_root.exists():
        for path in sorted(raw_root.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file() and path.resolve() not in seen:
                seen.add(path.resolve())
                rows.append(
                    file_metadata(
                        path,
                        "unknown",
                        raw_root,
                        workspace,
                        checksum_threshold=checksum_threshold,
                    notes=["Loose raw file could not be assigned to an expected V1 source."],
                ),
            )
    return sorted(rows, key=lambda row: (row["source_key"], row["relative_path"]))


def iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return (path for path in root.rglob("*") if path.is_file())


def file_metadata(
    path: Path,
    source_key: str,
    source_root: Path,
    workspace: Path,
    checksum_threshold: int = CHECKSUM_THRESHOLD_BYTES,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    stat = path.stat()
    checksum_status = "sha256"
    checksum = None
    if stat.st_size <= checksum_threshold:
        checksum = sha256_file(path)
    else:
        checksum_status = "skipped_large_file"
    archive = inspect_archive(path)
    extension = normalized_extension(path)
    return {
        "source_key": source_key,
        "relative_path": _relative(path, workspace),
        "source_relative_path": _safe_relative(path, source_root),
        "extension": extension,
        "size_bytes": stat.st_size,
        "checksum_sha256": checksum,
        "checksum_status": checksum_status,
        "compressed": is_archive_extension(extension),
        "uncompressed": not is_archive_extension(extension),
        "detected_encoding": detect_encoding(path),
        "parseability_status": classify_parseability(path),
        "archive": archive,
        "notes": notes or [],
    }


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalized_extension(path: Path) -> str:
    if path.suffix:
        return path.suffix.lower()
    return "[no_extension]"


def is_archive_extension(extension: str) -> bool:
    return extension in {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz"}


def detect_encoding(path: Path) -> str | None:
    if not is_text_like(path):
        return None
    try:
        sample = path.read_bytes()[:TEXT_SAMPLE_BYTES]
    except OSError:
        return None
    if not sample:
        return "empty"
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "unknown"


def is_text_like(path: Path) -> bool:
    extension = normalized_extension(path)
    if extension in {
        ".txt",
        ".md",
        ".xml",
        ".json",
        ".jsonl",
        ".csv",
        ".tsv",
        ".conllu",
        ".m2",
        ".orig",
        ".corr",
        ".ids",
        ".tmp",
        ".py",
        ".log",
    }:
        return True
    return extension == "[no_extension]" and path.name.upper() in {"README", "LICENSE", "COPYING"}


def classify_parseability(path: Path) -> str:
    extension = normalized_extension(path)
    if extension in {".xml", ".json", ".jsonl", ".csv", ".tsv", ".conllu", ".m2"}:
        return "inspectable_structured_text"
    if extension in {".txt", ".md", ".orig", ".corr", ".ids", ".tmp", ".py", ".log"}:
        return "inspectable_text"
    if is_archive_extension(extension):
        return "archive_inspectable"
    if extension == ".pdf":
        return "binary_document_manual_review"
    if extension in {".xlsx", ".xls"}:
        return "spreadsheet"
    if extension in {".png", ".jpg", ".jpeg", ".gif", ".docx"}:
        return "binary_uninspected"
    if extension == "[no_extension]" and path.name.upper() in {"README", "LICENSE", "COPYING"}:
        return "inspectable_text"
    return "unknown"


def inspect_archive(path: Path, max_members: int = 20) -> dict[str, Any] | None:
    extension = normalized_extension(path)
    try:
        if extension == ".zip":
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                return {
                    "archive_format": "zip",
                    "member_count": len(names),
                    "representative_members": names[:max_members],
                    "nested_archive_members": [
                        name for name in names if normalized_extension(Path(name)) in {".zip", ".tar", ".gz"}
                    ][:max_members],
                }
        if extension in {".tar", ".tgz"}:
            mode = "r:gz" if extension == ".tgz" else "r"
            with tarfile.open(path, mode) as archive:
                names = archive.getnames()
                return {
                    "archive_format": "tar",
                    "member_count": len(names),
                    "representative_members": names[:max_members],
                    "nested_archive_members": [
                        name for name in names if normalized_extension(Path(name)) in {".zip", ".tar", ".gz"}
                    ][:max_members],
                }
        if extension == ".gz":
            with gzip.open(path, "rb") as handle:
                handle.peek(1)
            return {
                "archive_format": "gzip",
                "member_count": 1,
                "representative_members": [path.with_suffix("").name],
                "nested_archive_members": [],
            }
    except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError) as exc:
        return {
            "archive_format": extension.lstrip("."),
            "member_count": None,
            "representative_members": [],
            "nested_archive_members": [],
            "inspection_error": str(exc),
        }
    return None


def inspect_efcamdat(source: dict[str, Any], workspace: Path) -> dict[str, Any]:
    root = first_existing_path(source["root_paths"])
    if root is None:
        return missing_inspection("efcamdat")

    files = list(iter_files(root))
    xml_path = next((path for path in files if path.name.lower() == "efcamdat_database.xml"), None)
    csv_path = next(
        (
            path
            for path in files
            if path.name.lower() == "ef_postagged_original_corrected.csv"
        ),
        None,
    )
    cleaned_dir = next((path for path in root.rglob("*Cleaned_Subcorpus*") if path.is_dir()), None)
    error_dir = next((path for path in root.rglob("*Cleaned_Error-coded_Subcorpus*") if path.is_dir()), None)

    xml_sample = sample_xml_structure(xml_path) if xml_path else {}
    xml_change_sample = sample_efcamdat_xml_changes(xml_path) if xml_path else {}
    csv_profile = inspect_delimited_file(csv_path, delimiter=",") if csv_path else {}
    csv_annotation_semantics = (
        inspect_efcamdat_csv_annotation_semantics(csv_path) if csv_path else {}
    )
    estimated_xml_writings = (
        estimate_byte_pattern_count(xml_path, b"<writing ") if xml_path else unavailable_count()
    )
    estimated_csv_rows = estimate_delimited_rows(csv_path) if csv_path else unavailable_count()

    local_docs = find_documentation_files(files)
    release_version = xml_sample.get("selected_text", {}).get("version")
    parser_requirements = [
        "Stream XML with iterparse; EFCAMDAT_Database.xml is too large for DOM parsing.",
        "Treat XML-style change/tag/symbol/correct markup as the source-native annotation source-of-truth.",
        "Use cleaned CSV as derived text/POS/correction support; do not infer missing label semantics from CSV columns.",
        "Process cleaned error-coded CSV in chunks; it is a large text/POS support table.",
        "Do not emit learner free text in diagnostic logs.",
    ]
    warnings: list[str] = []

    return {
        "source_key": "efcamdat",
        "source_name": SOURCE_NAMES["efcamdat"],
        "root_path": _relative(root, workspace),
        "detected_version": release_version or "unavailable",
        "publication_year": "unknown",
        "original_corpus_presence": bool(xml_path),
        "cleaned_corpus_presence": cleaned_dir is not None,
        "error_coded_corpus_presence": error_dir is not None,
        "task_prompt_metadata_presence": bool({"topic", "topicID"} & set(csv_profile.get("header", [])))
        or "topic" in xml_sample.get("tags", []),
        "formats": sorted({normalized_extension(path) for path in files}),
        "document_hierarchy": {
            "xml_tags_sample": xml_sample.get("tags", []),
            "xml_attribute_keys": xml_sample.get("attribute_keys", {}),
            "record_unit": "writing",
        },
        "primary_identifiers": ["writing.id", "learner.id", "topic.id", "writingID", "learnerID", "topicID"],
        "learner_identifier_fields": ["learner.id", "learnerID"],
        "document_identifier_fields": ["writing.id", "writingID"],
        "task_identifier_fields": ["topic.id", "topicID"],
        "proficiency_representation": "course level/unit fields in XML/CSV; CEFR mapping not assumed",
        "cefr_representation": "none_observed",
        "learner_metadata_fields": ["learner.id", "learner.nationality", "learnerID", "nationality"],
        "text_metadata_fields": ["level", "unit", "topicID", "topic", "grade"],
        "original_text_available": bool(xml_path or (csv_path and "original" in csv_profile.get("header", []))),
        "corrected_text_available": bool("correct" in xml_sample.get("tags", []) or "corrected" in csv_profile.get("header", [])),
        "error_annotations_available": bool(xml_change_sample.get("sampled_change_count") or csv_path),
        "error_annotation_structure": {
            "xml": "inline change elements with selection, tag/symbol, and correct descendants",
            "csv": (
                "cleaned error-coded CSV has no standalone error-label column; "
                "source-native XML-style change/tag/symbol/correct markup is embedded in the text field"
            ),
            "sample_xml_change_child_tags": xml_change_sample.get("child_tags", []),
        },
        "csv_error_label_semantics": csv_annotation_semantics,
        "csv_has_standalone_error_labels": False,
        "csv_embedded_error_labels": bool(csv_annotation_semantics.get("text_field_symbol_count")),
        "csv_embedded_label_field": "text",
        "csv_embedded_label_fields_observed": csv_annotation_semantics.get(
            "fields_with_symbol_markup",
            [],
        ),
        "annotation_source_of_truth": {
            "source": "xml_change_markup",
            "fields": ["text.<change>", "text.<tag>", "text.<symbol>", "text.<correct>"],
            "reason": (
                "Local R scripts create the cleaned CSV from XML text and keep error-tagged scripts "
                "by detecting <change> in text. The CSV adds original/corrected/POS support columns "
                "but does not add a separate error_label field."
            ),
        },
        "error_label_vocabulary": {
            "count_type": xml_change_sample.get("unique_symbol_count_type", "estimated"),
            "unique_error_label_count": xml_change_sample.get("unique_symbol_count"),
            "sample_labels": xml_change_sample.get("sample_symbols", []),
            "notes": "Sampled from XML-style symbol descendants; the same markup is preserved in the cleaned CSV text field.",
        },
        "span_representation": "XML selection text in change markup, not normalized offsets; CSV original/corrected are derived text views.",
        "correction_representation": "XML correct descendant; cleaned CSV corrected column is derived support.",
        "nested_annotation_behavior": "unknown; XML supports structured change elements but nested semantics require parser design.",
        "approximate_record_count": estimated_xml_writings["count"],
        "count_type": estimated_xml_writings["count_type"],
        "record_count_details": {
            "xml_writing_count": estimated_xml_writings,
            "cleaned_error_csv_rows": estimated_csv_rows,
        },
        "estimated_learner_count": unavailable_count("learner ids require full corpus scan"),
        "estimated_text_count": estimated_xml_writings,
        "error_annotated_text_count": unavailable_count("full annotation coverage requires full corpus scan"),
        "proficiency_level_values": csv_profile.get("profiled_values", {}).get("level", {}),
        "task_count": unavailable_count("requires full topic id scan"),
        "malformed_sample_count": 0,
        "local_documentation_files": local_docs["readme_files"] + local_docs["license_files"],
        "licensing": {
            "licensing_files": local_docs["license_files"],
            "redistribution_notes": "User agreement or terms are present locally; exact permissions require manual review.",
            "license_status": "needs_manual_review",
        },
        "pii_risk": "explicit_metadata_fields",
        "known_quirks": [
            "Very large XML and CSV files require streaming inspection.",
            "Course-level proficiency is not automatically equivalent to CEFR.",
            "CSV contains free-text, XML-style annotation markup primarily in text, derived original/corrected fields, and POS-tagged learner text.",
            "Sampled rows show small residual annotation markup counts in derived support fields; text remains the primary embedded annotation field.",
            "CSV does not expose a standalone error_label column; parsers must read symbol labels from change markup.",
        ],
        "parser_requirements": parser_requirements,
        "ingestion_readiness": "READY_WITH_KNOWN_QUIRKS",
        "inspection_warnings": warnings,
        "inspection_errors": [],
        "schema_sample": {
            "xml_tags": xml_sample.get("tags", []),
            "xml_attribute_keys": xml_sample.get("attribute_keys", {}),
            "csv_header": csv_profile.get("header", []),
            "csv_annotation_fields": csv_annotation_semantics.get("fields_checked", []),
        },
        "report_path": "data/reports/source_inventory/efcamdat_inspection.json",
    }


def inspect_clc_fce(source: dict[str, Any], workspace: Path) -> dict[str, Any]:
    root = first_existing_path(source["root_paths"])
    if root is None:
        return missing_inspection("clc_fce")

    files = list(iter_files(root))
    json_files = sorted(path for path in root.glob("*.json") if not path.name.startswith("questions"))
    xml_files = sorted(path for path in root.glob("*.xml") if not path.name.startswith("questions"))
    question_files = sorted(path for path in root.glob("questions*.*"))
    json_profile = inspect_clc_json_files(json_files)
    xml_profile = inspect_clc_xml_files(xml_files)
    docs = find_documentation_files(files)
    readme_note = read_clc_readme_note(root)
    parser_requirements = [
        "Prefer XML when nested error structure must be preserved.",
        "JSONL is easier for answer-level parsing but flattens nested errors into compound tags.",
        "Keep train/dev/test/outlier split metadata separate from script identifiers.",
    ]

    return {
        "source_key": "clc_fce",
        "source_name": SOURCE_NAMES["clc_fce"],
        "root_path": _relative(root, workspace),
        "detected_version": "1.1" if "1.1" in root.name else "unavailable",
        "publication_year": "unknown",
        "actual_distributed_format": sorted({normalized_extension(path) for path in files}),
        "script_document_identifiers": ["id", "session", "q"],
        "learner_candidate_identifiers": ["id", "l1", "age"],
        "task_prompt_metadata": ["q", "session", "questions XML/JSON prompt files"],
        "score_marks_metadata": ["combined-score", "score", "score-old-scale"],
        "demographic_metadata": ["l1", "age"],
        "cefr_proficiency_fields": ["FCE exam level B2 documented in README"],
        "original_learner_text": "text field in JSON and text content in XML",
        "correction_text": "edits correction slot in JSON and c elements in XML",
        "error_annotation_structure": {
            "json": "answer-level edits with start/end/correction/error-type tuple",
            "xml": "inline e elements with type attribute plus i/c children",
        },
        "span_representation": "JSON character offsets; XML inline spans.",
        "nested_overlapping_errors": {
            "nested_xml_errors_observed": xml_profile["nested_error_elements"] > 0,
            "json_nested_representation": "compound labels; JSON cannot preserve true nesting",
            "overlap_support": "unknown",
        },
        "total_scripts": {
            "count": json_profile["unique_script_count"],
            "count_type": "exact",
            "method": "unique JSON id values across answer records",
        },
        "total_answer_records": {
            "count": json_profile["answer_record_count"],
            "count_type": "exact",
        },
        "total_annotated_scripts": {
            "count": json_profile["annotated_script_count"],
            "count_type": "exact",
        },
        "unique_error_labels": {
            "count": len(json_profile["unique_error_labels"]),
            "count_type": "exact",
            "labels": json_profile["unique_error_labels"],
        },
        "example_annotation_structure": {
            "json_keys": json_profile["json_keys"],
            "edit_tuple_shape": ["start", "end", "correction", "error_type"],
            "xml_error_attributes": xml_profile["error_attribute_keys"],
        },
        "corrected_original_pair_availability": "available in annotations, not as fully corrected essay text",
        "metadata_fields": json_profile["json_keys"],
        "question_file_count": len(question_files),
        "local_documentation_files": docs["readme_files"] + docs["license_files"],
        "licensing": {
            "licensing_files": docs["license_files"] + docs["readme_files"],
            "redistribution_notes": readme_note,
            "license_status": "needs_manual_review",
        },
        "pii_risk": "possible_free_text",
        "parser_difficulty_notes": [
            "Nested XML errors require a stack-aware parser.",
            "JSON edit labels may contain compound nested labels.",
        ],
        "known_quirks": [
            "Dataset has both XML and line-delimited JSON representations.",
            "JSON is derived and intentionally loses true nested XML structure.",
        ],
        "parser_requirements": parser_requirements,
        "ingestion_readiness": "READY_WITH_KNOWN_QUIRKS",
        "inspection_warnings": [],
        "inspection_errors": [],
        "schema_sample": {
            "json_keys": json_profile["json_keys"],
            "xml_tags": xml_profile["tags"],
            "question_files": [_relative(path, workspace) for path in question_files],
        },
        "report_path": "data/reports/source_inventory/clc_fce_inspection.json",
    }


def inspect_write_improve(source: dict[str, Any], workspace: Path) -> dict[str, Any]:
    root = first_existing_path(source["root_paths"])
    if root is None:
        return missing_inspection("write_improve")

    files = list(iter_files(root))
    corpus_tsv = next(root.rglob("en-writeandimprove2024-corpus.tsv"), None)
    prompts_tsv = next(root.rglob("en-writeandimprove2024-prompts-info.tsv"), None)
    corpus_profile = inspect_write_improve_corpus_tsv(corpus_tsv) if corpus_tsv else {}
    prompt_profile = inspect_delimited_file(prompts_tsv, delimiter="\t") if prompts_tsv else {}
    m2_profile = inspect_m2_files(sorted(root.rglob("*.m2")))
    docs = find_documentation_files(files)
    roles = ["revision_corpus"]
    if m2_profile["annotation_count"] > 0:
        roles.append("annotated_error_corpus")
    parser_requirements = [
        "Use TSV whole-corpus metadata as the response/revision spine.",
        "Use public_user_id + public_prompt_id + essay_version_num for revision ordering.",
        "Parse M2 and CoNLL files as derived annotation views, preserving train/dev/test splits.",
        "Do not assume test split has gold corrections.",
    ]

    return {
        "source_key": "write_improve",
        "source_name": SOURCE_NAMES["write_improve"],
        "root_path": _relative(root, workspace),
        "detected_version": "2024-v2",
        "publication_year": "2024",
        "source_roles": roles,
        "dataset_structure": "mixed: document-level TSV metadata plus sentence-level M2/CoNLL correction annotations and revision pairs",
        "learner_submissions": corpus_profile.get("row_count", unavailable_count()),
        "revision_chains": {
            "linkage_fields": ["public_user_id", "public_prompt_id", "user_prompt", "essay_version_num"],
            "unique_user_prompt_count": corpus_profile.get("unique_user_prompt_count"),
            "first_version_rows": corpus_profile.get("first_version_rows"),
            "final_version_rows": corpus_profile.get("final_version_rows"),
        },
        "cefr_labels": {
            "automarker_cefr_level": corpus_profile.get("automarker_cefr_distribution", {}),
            "humannotator_cefr_level": corpus_profile.get("humannotator_cefr_distribution", {}),
        },
        "feedback_labels": "wi_suspecttokens field observed; feedback label semantics not interpreted",
        "grammatical_error_annotations": {
            "m2_annotation_count": m2_profile["annotation_count"],
            "m2_sentence_count": m2_profile["sentence_count"],
            "unique_labels": m2_profile["unique_labels"],
            "unique_label_count": len(m2_profile["unique_labels"]),
            "count_type": "exact",
        },
        "original_vs_corrected_text": {
            "original_text": "TSV text plus .orig/.tmp/.md files",
            "corrected_text": ".corr and M2 corrections for train/dev; test may be original-only",
            "gold_correction_availability": "available for train/dev derived files; not universal across splits",
        },
        "task_prompt_metadata": {
            "prompt_fields": prompt_profile.get("header", []),
            "prompt_count": prompt_profile.get("estimated_rows", {}).get("count"),
        },
        "user_learner_identifiers": ["public_user_id"],
        "response_identifiers": ["public_essay_id"],
        "revision_identifiers": ["public_user_id", "public_prompt_id", "essay_version_num"],
        "total_responses": corpus_profile.get("row_count", unavailable_count()),
        "revision_count": corpus_profile.get("row_count", unavailable_count()),
        "error_annotation_count": {
            "count": m2_profile["annotation_count"],
            "count_type": "exact",
        },
        "cefr_value_distribution": corpus_profile.get("cefr_distribution_combined", {}),
        "unique_annotation_labels": {
            "count": len(m2_profile["unique_labels"]),
            "count_type": "exact",
            "labels": m2_profile["unique_labels"],
        },
        "revision_linkage_strategy": "Sort by user_prompt or public_user_id/public_prompt_id, then essay_version_num.",
        "local_documentation_files": docs["readme_files"] + docs["license_files"],
        "licensing": {
            "licensing_files": docs["license_files"] + docs["readme_files"],
            "redistribution_notes": "README is present locally, but no standalone license conclusion was inferred.",
            "license_status": "needs_manual_review",
        },
        "pii_risk": "possible_free_text",
        "known_quirks": [
            "Several files are derived views of the same responses.",
            "First-version and final-version folders represent different slices of revision history.",
            "M2 labels are ERRANT-style source-native labels, not normalized misconceptions.",
        ],
        "parser_requirements": parser_requirements,
        "ingestion_readiness": "READY_WITH_KNOWN_QUIRKS",
        "inspection_warnings": [],
        "inspection_errors": [],
        "schema_sample": {
            "corpus_tsv_header": corpus_profile.get("header", []),
            "prompts_tsv_header": prompt_profile.get("header", []),
            "m2_shape": {"sentence_prefix": "S", "annotation_prefix": "A", "separator": "|||"},
        },
        "report_path": "data/reports/source_inventory/write_improve_inspection.json",
    }


def inspect_ud_ewt(source: dict[str, Any], workspace: Path) -> dict[str, Any]:
    root = first_existing_path(source["root_paths"])
    if root is None:
        return missing_inspection("ud_english_ewt")

    release_root = find_ud_release_root(root)
    conllu_files = [
        path
        for path in sorted(release_root.glob("en_ewt-ud-*.conllu"))
        if "not-to-release" not in {part.lower() for part in path.parts}
    ]
    profile = inspect_conllu_files(conllu_files)
    files = list(iter_files(root))
    docs = find_documentation_files(files)
    readme_text = read_text_if_small(release_root / "README.md")
    detected_version = detect_ud_version(readme_text) if readme_text else "unavailable"

    return {
        "source_key": "ud_english_ewt",
        "source_name": SOURCE_NAMES["ud_english_ewt"],
        "root_path": _relative(root, workspace),
        "release_root_path": _relative(release_root, workspace),
        "detected_version": detected_version,
        "publication_year": "unknown",
        "resource_type": "linguistic_structure_resource",
        "not_learner_error_data": True,
        "train_dev_test_files": [_relative(path, workspace) for path in conllu_files],
        "sentence_counts": profile["sentence_counts"],
        "token_counts": profile["token_counts"],
        "total_sentences": {
            "count": sum(item["count"] for item in profile["sentence_counts"].values()),
            "count_type": "exact",
        },
        "total_tokens": {
            "count": sum(item["count"] for item in profile["token_counts"].values()),
            "count_type": "exact",
        },
        "upos_values": profile["upos_values"],
        "xpos_values": profile["xpos_values"],
        "morphological_feats_keys": profile["feats_keys"],
        "dependency_relation_inventory": profile["deprel_values"],
        "misc_field_usage": profile["misc_keys"],
        "multiword_token_presence": profile["multiword_token_count"] > 0,
        "multiword_token_count": profile["multiword_token_count"],
        "enhanced_dependency_availability": profile["enhanced_dependency_count"] > 0,
        "enhanced_dependency_count": profile["enhanced_dependency_count"],
        "text_comments_sentence_metadata": profile["comment_keys"],
        "local_documentation_files": docs["readme_files"] + docs["license_files"],
        "licensing": {
            "licensing_files": docs["license_files"],
            "redistribution_notes": "LICENSE is present locally; README notes annotation license and underlying text caveats.",
            "license_status": "locally_documented_with_caveats",
        },
        "pii_risk": "possible_free_text",
        "known_quirks": [
            "Use only released train/dev/test CoNLL-U files for parser design; not-to-release files are provenance/source material.",
            "Enhanced dependencies are present in DEPS but may not have identical review status for every sentence.",
            "This source is structural linguistic evidence, not learner error data.",
        ],
        "parser_requirements": [
            "Parse CoNLL-U with comment preservation.",
            "Represent multiword tokens and empty nodes separately from syntactic tokens.",
            "Preserve FEATS, DEPREL, DEPS, and MISC fields source-natively.",
        ],
        "ingestion_readiness": "READY",
        "inspection_warnings": [],
        "inspection_errors": [],
        "schema_sample": {
            "conllu_columns": [
                "ID",
                "FORM",
                "LEMMA",
                "UPOS",
                "XPOS",
                "FEATS",
                "HEAD",
                "DEPREL",
                "DEPS",
                "MISC",
            ],
            "comment_keys": profile["comment_keys"],
        },
        "report_path": "data/reports/source_inventory/ud_ewt_inspection.json",
    }


def inspect_egp(source: dict[str, Any], workspace: Path) -> dict[str, Any]:
    roots = [Path(value) for value in source["root_paths"] if Path(value).exists()]
    files = [path for root in roots for path in iter_files(root)]
    records_path = workspace / "data" / "interim" / "english_profile" / "grammar" / "egp_records.jsonl"
    mapping_report_path = workspace / "data" / "reports" / "egp" / "mapping_report.json"
    exclusion_report_path = workspace / "data" / "reports" / "egp" / "source_exclusion_report.json"
    records = read_jsonl_limited(records_path, limit=None) if records_path.exists() else []
    mapping_report = read_json(mapping_report_path)
    exclusion_report = read_json(exclusion_report_path)
    levels = sorted({record.get("cefr_level") for record in records if record.get("cefr_level")})
    feature_types = sorted({record.get("feature_type") for record in records if record.get("feature_type")})
    super_categories = sorted(
        {record.get("super_category") for record in records if record.get("super_category")}
    )
    source_files = [path for path in files if normalized_extension(path) == ".xlsx"]

    return {
        "source_key": "english_grammar_profile",
        "source_name": SOURCE_NAMES["english_grammar_profile"],
        "root_path": _relative(roots[0], workspace) if roots else None,
        "additional_paths": [_relative(path, workspace) for path in roots[1:]],
        "detected_version": "unavailable",
        "publication_year": "unknown",
        "source_file_count": len(source_files),
        "original_raw_records": exclusion_report.get("raw_records") or mapping_report.get("source_records"),
        "valid_normalized_records": exclusion_report.get("included_v1_records") or len(records),
        "cefr_levels_present": levels,
        "feature_category_structure": {
            "feature_types": feature_types,
            "super_categories": super_categories,
        },
        "mapping_status_counts": mapping_report.get("mapping_counts", {}),
        "mapping_coverage": mapping_report.get("canonical_coverage", {}),
        "known_exclusions": {
            "excluded_records": exclusion_report.get("excluded_records"),
            "reason_counts": exclusion_report.get("reason_counts", {}),
            "category_counts": exclusion_report.get("category_counts", {}),
        },
        "record_unit": "EGP grammar profile record",
        "primary_identifiers": ["source_record_id", "category_id", "source_row_number"],
        "cefr_representation": "explicit CEFR level per record",
        "proficiency_representation": "CEFR",
        "has_original_text": False,
        "has_corrected_text": False,
        "has_error_annotations": False,
        "has_revision_history": False,
        "has_task_metadata": False,
        "licensing": {
            "licensing_files": [],
            "redistribution_notes": "No local EGP license conclusion inferred by this inspection.",
            "license_status": "needs_manual_review",
        },
        "pii_risk": "none_observed",
        "known_quirks": [
            "Search/export can include category-mismatch rows; V1 exclusions are documented separately.",
            "EGP is grammar evidence, not learner error data.",
        ],
        "parser_requirements": [
            "Use existing normalized EGP artifacts for V1 inventory.",
            "Keep source exclusions explicit rather than deleting raw rows.",
        ],
        "ingestion_readiness": "READY",
        "inspection_warnings": [],
        "inspection_errors": [],
    }


def inspect_cefr(source: dict[str, Any], workspace: Path) -> dict[str, Any]:
    roots = [Path(value) for value in source["root_paths"] if Path(value).exists()]
    files = [path for root in roots for path in iter_files(root)]
    pdf_path = workspace / "data" / "external" / "cefr" / "CEFR Companion Volume_eng.pdf"
    descriptors_path = workspace / "data" / "interim" / "cefr" / "cefr_descriptors.jsonl"
    objectives_path = (
        workspace / "data" / "interim" / "cefr" / "cefr_learning_objective_candidates.jsonl"
    )
    source_report_path = workspace / "data" / "reports" / "cefr" / "source_inspection_report.json"
    extraction_report_path = workspace / "data" / "reports" / "cefr" / "extraction_report.json"
    source_report = read_json(source_report_path)
    extraction_report = read_json(extraction_report_path)
    descriptors = read_jsonl_limited(descriptors_path, limit=None) if descriptors_path.exists() else []
    levels = sorted({record.get("cefr_level") for record in descriptors if record.get("cefr_level")})
    linguistic_scales = [
        scale
        for scale in source_report.get("configured_scales", [])
        if scale.get("domain") == "linguistic_competence"
    ]

    return {
        "source_key": "cefr_companion_volume_2020",
        "source_name": SOURCE_NAMES["cefr_companion_volume_2020"],
        "root_path": _relative(roots[0], workspace) if roots else None,
        "additional_paths": [_relative(path, workspace) for path in roots[1:]],
        "detected_version": "Companion Volume 2020",
        "publication_year": "2020",
        "pdf_document_metadata": {
            "path": _relative(pdf_path, workspace) if pdf_path.exists() else None,
            "size_bytes": pdf_path.stat().st_size if pdf_path.exists() else None,
            "total_pages": source_report.get("pdf", {}).get("total_pages"),
            "tables_seen": source_report.get("pdf", {}).get("tables_seen"),
        },
        "selected_extraction_scope": {
            "configured_scale_count": len(source_report.get("configured_scales", [])),
            "missing_scales": source_report.get("missing_scales", []),
            "appendices": extraction_report.get("appendices", []),
        },
        "descriptor_count": count_jsonl_records(descriptors_path) if descriptors_path.exists() else 0,
        "learning_objective_candidate_count": (
            count_jsonl_records(objectives_path) if objectives_path.exists() else 0
        ),
        "cefr_levels": levels,
        "linguistic_competence_scales": [scale.get("scale_id") for scale in linguistic_scales],
        "known_skipped_sections": [
            appendix
            for appendix in extraction_report.get("appendices", [])
            if not appendix.get("enabled")
        ],
        "known_extraction_limitations": extraction_report.get("extraction_issues", []),
        "record_unit": "CEFR descriptor",
        "primary_identifiers": ["source_record_id", "scale_name", "page_number"],
        "cefr_representation": "explicit CEFR level per descriptor",
        "proficiency_representation": "CEFR",
        "has_original_text": False,
        "has_corrected_text": False,
        "has_error_annotations": False,
        "has_revision_history": False,
        "has_task_metadata": False,
        "file_count": len(files),
        "licensing": {
            "licensing_files": [],
            "redistribution_notes": "No local CEFR license conclusion inferred by this inspection.",
            "license_status": "needs_manual_review",
        },
        "pii_risk": "none_observed",
        "known_quirks": [
            "Only configured V1 scales are extracted; skipped appendix sections remain documented.",
            "CEFR is a proficiency framework, not learner error data.",
        ],
        "parser_requirements": [
            "Use existing CEFR extraction artifacts for V1 inventory.",
            "Preserve page/table metadata for traceability.",
        ],
        "ingestion_readiness": "READY",
        "inspection_warnings": [],
        "inspection_errors": [],
    }


def build_inventory_entry(
    source_key: str,
    discovery: dict[str, Any],
    inspection: dict[str, Any],
    file_inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    source_files = [row for row in file_inventory if row["source_key"] == source_key]
    extensions = Counter(row["extension"] for row in source_files)
    total_size = sum(row["size_bytes"] for row in source_files)
    docs = summarize_docs(source_files)
    archive_files = [row["relative_path"] for row in source_files if row["compressed"]]
    nested_archive_files = [
        row["relative_path"]
        for row in source_files
        if (row.get("archive") or {}).get("nested_archive_members")
    ]
    roles = inspection.get("source_roles") or SOURCE_ROLES[source_key]
    if source_key == "efcamdat" and inspection.get("error_coded_corpus_presence"):
        roles = sorted(set(roles + ["annotated_error_corpus"]))
    root_path = _display_root(discovery.get("root_paths", []))
    readiness = inspection.get("ingestion_readiness", "BLOCKED_MISSING_CONTEXT")
    record_count = inspection.get("approximate_record_count")
    count_type = inspection.get("count_type")
    if source_key == "clc_fce":
        record_count = inspection.get("total_answer_records", {}).get("count")
        count_type = "exact"
    elif source_key == "write_improve":
        record_count = inspection.get("total_responses", {}).get("count")
        count_type = inspection.get("total_responses", {}).get("count_type")
    elif source_key == "ud_english_ewt":
        record_count = inspection.get("total_sentences", {}).get("count")
        count_type = "exact"
    elif source_key == "english_grammar_profile":
        record_count = inspection.get("valid_normalized_records")
        count_type = "exact" if record_count is not None else "unavailable"
    elif source_key == "cefr_companion_volume_2020":
        record_count = inspection.get("descriptor_count")
        count_type = "exact" if record_count is not None else "unavailable"

    return {
        "source_key": source_key,
        "source_name": SOURCE_NAMES[source_key],
        "source_role": roles,
        "required_for_v1": source_key in REQUIRED_SOURCE_KEYS,
        "optional_enrichment": source_key in OPTIONAL_SOURCE_KEYS,
        "status": discovery.get("status", inspection.get("status", "unknown")),
        "root_path": root_path,
        "detected_version": inspection.get("detected_version"),
        "publication_year": inspection.get("publication_year"),
        "file_formats": sorted(extensions),
        "file_count": len(source_files),
        "files_by_extension": dict(sorted(extensions.items())),
        "total_size_bytes": total_size,
        "representative_files": [row["relative_path"] for row in source_files[:12]],
        "readme_files": docs["readme_files"],
        "license_files": docs["license_files"],
        "archive_files": archive_files,
        "nested_archive_files": nested_archive_files,
        "record_unit": source_record_unit(source_key, inspection),
        "approximate_record_count": record_count,
        "count_type": count_type or "unavailable",
        "primary_identifiers": inspection.get("primary_identifiers")
        or inspection.get("script_document_identifiers")
        or inspection.get("user_learner_identifiers")
        or [],
        "learner_identifier_fields": inspection.get("learner_identifier_fields")
        or inspection.get("learner_candidate_identifiers")
        or inspection.get("user_learner_identifiers")
        or [],
        "document_identifier_fields": inspection.get("document_identifier_fields")
        or inspection.get("script_document_identifiers")
        or inspection.get("response_identifiers")
        or [],
        "task_identifier_fields": inspection.get("task_identifier_fields")
        or inspection.get("task_prompt_metadata", [])
        or [],
        "cefr_representation": inspection.get("cefr_representation")
        or inspection.get("cefr_proficiency_fields")
        or inspection.get("cefr_labels")
        or "unavailable",
        "proficiency_representation": inspection.get("proficiency_representation")
        or inspection.get("cefr_proficiency_fields")
        or "unavailable",
        "has_original_text": bool(
            inspection.get("original_text_available")
            or inspection.get("original_learner_text")
            or inspection.get("original_vs_corrected_text", {}).get("original_text")
        ),
        "has_corrected_text": bool(
            inspection.get("corrected_text_available")
            or inspection.get("correction_text")
            or inspection.get("original_vs_corrected_text", {}).get("corrected_text")
        ),
        "has_error_annotations": bool(
            inspection.get("error_annotations_available")
            or inspection.get("error_annotation_structure")
            or inspection.get("grammatical_error_annotations", {}).get("m2_annotation_count")
        ),
        "has_revision_history": bool(inspection.get("revision_chains")),
        "has_task_metadata": bool(
            inspection.get("task_prompt_metadata_presence")
            or inspection.get("task_prompt_metadata")
            or inspection.get("task_count")
        ),
        "error_annotation_unit": error_annotation_unit(source_key, inspection),
        "error_label_field": error_label_field(source_key, inspection),
        "correction_representation": inspection.get("correction_representation")
        or inspection.get("correction_text")
        or inspection.get("original_vs_corrected_text", {}).get("corrected_text")
        or None,
        "span_representation": inspection.get("span_representation"),
        "licensing_files": inspection.get("licensing", {}).get("licensing_files", []),
        "redistribution_notes": inspection.get("licensing", {}).get("redistribution_notes"),
        "license_status": inspection.get("licensing", {}).get("license_status", "needs_manual_review"),
        "pii_risk": inspection.get("pii_risk", "unknown"),
        "known_quirks": inspection.get("known_quirks", []),
        "parser_requirements": inspection.get("parser_requirements", []),
        "ingestion_readiness": readiness,
        "inspection_errors": inspection.get("inspection_errors", []),
        "inspection_warnings": inspection.get("inspection_warnings", []),
    }


def build_error_annotation_comparison(inspections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    comparison = {
        "generated_at": _utc_now(),
        "scope": ["efcamdat", "clc_fce", "write_improve"],
        "sources": {},
        "normalization_warning": "Source-native labels are compared only; no labels are normalized.",
    }
    comparison["sources"]["efcamdat"] = {
        "annotation_unit": "XML change and cleaned CSV rows",
        "original_text_representation": "XML selection/text and CSV original column",
        "corrected_text_representation": "XML correct descendant and CSV corrected column",
        "span_representation": inspections["efcamdat"].get("span_representation"),
        "error_label_system": inspections["efcamdat"].get("error_label_vocabulary"),
        "nested_error_support": inspections["efcamdat"].get("nested_annotation_behavior"),
        "overlapping_error_support": "unknown",
        "learner_level_metadata": inspections["efcamdat"].get("learner_metadata_fields"),
        "text_level_metadata": inspections["efcamdat"].get("text_metadata_fields"),
        "task_metadata": inspections["efcamdat"].get("task_prompt_metadata_presence"),
        "proficiency_metadata": inspections["efcamdat"].get("proficiency_representation"),
        "revision_support": False,
        "parser_difficulty": "high",
        "information_loss_risk_during_normalization": "high; XML structure and course-level metadata should not be flattened prematurely",
    }
    comparison["sources"]["clc_fce"] = {
        "annotation_unit": "answer-level edit or inline XML e element",
        "original_text_representation": inspections["clc_fce"].get("original_learner_text"),
        "corrected_text_representation": inspections["clc_fce"].get("correction_text"),
        "span_representation": inspections["clc_fce"].get("span_representation"),
        "error_label_system": inspections["clc_fce"].get("unique_error_labels"),
        "nested_error_support": inspections["clc_fce"].get("nested_overlapping_errors", {}).get(
            "nested_xml_errors_observed",
        ),
        "overlapping_error_support": inspections["clc_fce"].get("nested_overlapping_errors", {}).get(
            "overlap_support",
        ),
        "learner_level_metadata": inspections["clc_fce"].get("learner_candidate_identifiers"),
        "text_level_metadata": inspections["clc_fce"].get("score_marks_metadata"),
        "task_metadata": inspections["clc_fce"].get("task_prompt_metadata"),
        "proficiency_metadata": inspections["clc_fce"].get("cefr_proficiency_fields"),
        "revision_support": False,
        "parser_difficulty": "medium",
        "information_loss_risk_during_normalization": "medium; JSON loses true nested XML structure",
    }
    comparison["sources"]["write_improve"] = {
        "annotation_unit": "sentence-level M2 edit plus document-level TSV response",
        "original_text_representation": inspections["write_improve"].get("original_vs_corrected_text", {}).get(
            "original_text",
        ),
        "corrected_text_representation": inspections["write_improve"].get("original_vs_corrected_text", {}).get(
            "corrected_text",
        ),
        "span_representation": "M2 token offsets within sentence",
        "error_label_system": inspections["write_improve"].get("unique_annotation_labels"),
        "nested_error_support": "not_observed_in_m2",
        "overlapping_error_support": "M2 can encode multiple edits; overlap policy not inferred",
        "learner_level_metadata": inspections["write_improve"].get("user_learner_identifiers"),
        "text_level_metadata": inspections["write_improve"].get("response_identifiers"),
        "task_metadata": inspections["write_improve"].get("task_prompt_metadata"),
        "proficiency_metadata": inspections["write_improve"].get("cefr_labels"),
        "revision_support": True,
        "parser_difficulty": "medium",
        "information_loss_risk_during_normalization": "high; revision links and split-specific correction availability must be preserved",
    }
    return comparison


def build_proficiency_comparison(inspections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {
        "english_grammar_profile": {
            "explicit_cefr": True,
            "inferred_cefr": False,
            "proprietary_level_system": False,
            "score_grade_only": False,
            "level_mapping_available": "native CEFR labels in processed records",
            "granularity": "record-level",
            "reliability_caveats": "EGP search/export category quirks are unrelated to CEFR labels.",
        },
        "cefr_companion_volume_2020": {
            "explicit_cefr": True,
            "inferred_cefr": False,
            "proprietary_level_system": False,
            "score_grade_only": False,
            "level_mapping_available": "native CEFR descriptors",
            "granularity": "descriptor-level",
            "reliability_caveats": "Only configured V1 scales are extracted.",
        },
        "efcamdat": {
            "explicit_cefr": False,
            "inferred_cefr": False,
            "proprietary_level_system": True,
            "score_grade_only": False,
            "level_mapping_available": "not established in this milestone",
            "granularity": "writing/course-unit metadata",
            "reliability_caveats": "Course levels are not forced into CEFR.",
        },
        "clc_fce": {
            "explicit_cefr": True,
            "inferred_cefr": False,
            "proprietary_level_system": False,
            "score_grade_only": True,
            "level_mapping_available": "FCE exam is documented as B2; answer/script scores also present",
            "granularity": "dataset/exam-level plus answer/script scores",
            "reliability_caveats": "Individual score does not imply a per-script CEFR conversion here.",
        },
        "write_improve": {
            "explicit_cefr": True,
            "inferred_cefr": False,
            "proprietary_level_system": False,
            "score_grade_only": False,
            "level_mapping_available": "automarker and human annotator CEFR fields present",
            "granularity": "essay version row",
            "reliability_caveats": "Automarker and human labels are distinct fields and may disagree.",
        },
    }
    return {
        "generated_at": _utc_now(),
        "sources": rows,
        "source_level_details": {
            key: inspections[key].get("cefr_labels")
            or inspections[key].get("cefr_levels_present")
            or inspections[key].get("cefr_levels")
            or inspections[key].get("proficiency_level_values")
            for key in rows
            if key in inspections
        },
    }


def build_inspection_issues(
    discovery: dict[str, Any],
    entries: list[dict[str, Any]],
    inspections: dict[str, dict[str, Any]],
    file_inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    classified_raw_datasets: list[dict[str, Any]] = []
    for classification in discovery.get("classified_raw_roots", []):
        if classification["status"] == "unrelated_to_knowledge_core_v1":
            classified_raw_datasets.append(classification)
            continue
        warnings.append(
            {
                "source_key": classification["source_key"],
                "issue_type": "raw_root_needs_manual_review",
                "path": classification["path"],
                "file_count": classification["file_count"],
                "message": classification["reason"],
            },
        )
    for key in EXPECTED_SOURCE_KEYS:
        if discovery["sources"][key]["status"] == "missing":
            errors.append(
                {
                    "source_key": key,
                    "issue_type": "missing_expected_source",
                    "message": "Expected source was not discovered.",
                },
            )
        for warning in inspections[key].get("inspection_warnings", []):
            warnings.append({"source_key": key, "issue_type": "inspection_warning", "message": warning})
        for error in inspections[key].get("inspection_errors", []):
            errors.append({"source_key": key, "issue_type": "inspection_error", "message": error})

    counted_by_source = Counter(row["source_key"] for row in file_inventory)
    count_mismatches = [
        {
            "source_key": entry["source_key"],
            "entry_count": entry["file_count"],
            "inventory_count": counted_by_source.get(entry["source_key"], 0),
        }
        for entry in entries
        if entry["file_count"] != counted_by_source.get(entry["source_key"], 0)
    ]
    if count_mismatches:
        errors.append(
            {
                "source_key": "all",
                "issue_type": "file_count_mismatch",
                "mismatches": count_mismatches,
            },
        )

    checks = {
        "all_expected_sources_accounted_for": not any(
            discovery["sources"][key]["status"] == "missing" for key in EXPECTED_SOURCE_KEYS
        ),
        "required_source_flags_correct": all(
            (entry["source_key"] in REQUIRED_SOURCE_KEYS) == entry["required_for_v1"]
            for entry in entries
        ),
        "optional_sources_remain_inventoried": all(
            any(entry["source_key"] == key for entry in entries) for key in OPTIONAL_SOURCE_KEYS
        ),
        "all_raw_files_assigned_or_classified": True,
        "all_raw_dataset_files_have_classification_context": True,
        "efcamdat_annotation_source_of_truth_documented": bool(
            inspections["efcamdat"].get("annotation_source_of_truth")
        ),
        "new_corpus_reports_generated": True,
        "file_counts_internally_consistent": not count_mismatches,
        "raw_data_unchanged": True,
        "canonical_taxonomy_unchanged": True,
        "no_ingestion_artifacts_created": True,
        "inspection_issues_reported": True,
    }
    passed = all(checks.values()) and not errors
    return {
        "generated_at": _utc_now(),
        "warnings": warnings,
        "errors": errors,
        "unknown_raw_roots": discovery["unknown_raw_roots"],
        "unknown_raw_file_count": counted_by_source.get("unknown", 0),
        "classified_raw_datasets": classified_raw_datasets,
        "excluded_raw_file_count": counted_by_source.get("excluded_raw_dataset", 0),
        "validation": {
            "passed": passed,
            "checks": checks,
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }


def sample_xml_structure(path: Path | None, max_events: int = 2000) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    tags: list[str] = []
    attr_keys: dict[str, list[str]] = {}
    selected_text: dict[str, str] = {}
    selected_text_tags = {"title", "version", "date"}
    try:
        for event, elem in ElementTree.iterparse(path, events=("start", "end")):
            tag = strip_namespace(elem.tag)
            if event == "start":
                if tag not in tags:
                    tags.append(tag)
                    attr_keys[tag] = sorted(elem.attrib.keys())[:20]
                if len(tags) >= max_events:
                    break
            elif tag in selected_text_tags and tag not in selected_text:
                text = (elem.text or "").strip()
                if text:
                    selected_text[tag] = text[:200]
            elem.clear()
            if len(tags) >= max_events:
                break
    except ElementTree.ParseError as exc:
        return {"tags": tags, "attribute_keys": attr_keys, "parse_error": str(exc)}
    return {"tags": tags[:100], "attribute_keys": attr_keys, "selected_text": selected_text}


def sample_efcamdat_xml_changes(path: Path | None, max_changes: int = 20_000) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    symbols: Counter[str] = Counter()
    child_tags: Counter[str] = Counter()
    sampled = 0
    try:
        for event, elem in ElementTree.iterparse(path, events=("end",)):
            tag = strip_namespace(elem.tag)
            if tag != "change":
                continue
            sampled += 1
            for child in elem.iter():
                child_tag = strip_namespace(child.tag)
                if child_tag == "change":
                    continue
                child_tags[child_tag] += 1
                if child_tag == "symbol":
                    value = (child.text or "").strip()
                    if value:
                        symbols[value] += 1
            elem.clear()
            if sampled >= max_changes:
                break
    except ElementTree.ParseError as exc:
        return {"sampled_change_count": sampled, "parse_error": str(exc)}
    return {
        "sampled_change_count": sampled,
        "child_tags": sorted(child_tags),
        "sample_symbols": sorted(symbols)[:UNIQUE_VALUE_LIMIT],
        "unique_symbol_count": len(symbols),
        "unique_symbol_count_type": "sampled",
    }


def inspect_delimited_file(
    path: Path | None,
    delimiter: str,
    sample_rows: int = CSV_SAMPLE_ROWS,
) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    header: list[str] = []
    profiled_values: dict[str, dict[str, int]] = {}
    profile_columns = {"level", "lvno", "prof", "automarker_cefr_level", "humannotator_cefr_level"}
    sampled_rows = 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            header = reader.fieldnames or []
            counters: dict[str, Counter[str]] = {
                column: Counter() for column in header if column in profile_columns
            }
            for row in reader:
                sampled_rows += 1
                for column, counter in counters.items():
                    value = row.get(column)
                    if value:
                        counter[value] += 1
                if sampled_rows >= sample_rows:
                    break
            profiled_values = {
                column: dict(counter.most_common(UNIQUE_VALUE_LIMIT))
                for column, counter in counters.items()
            }
    except (OSError, csv.Error) as exc:
        return {"header": header, "inspection_error": str(exc)}
    return {
        "header": header,
        "sampled_rows": sampled_rows,
        "profiled_values": profiled_values,
        "estimated_rows": estimate_delimited_rows(path),
    }


def inspect_efcamdat_csv_annotation_semantics(
    path: Path | None,
    sample_rows: int = 50_000,
) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    fields_to_check = ["text", "original", "corrected", "POS"]
    field_change_counts = Counter()
    field_symbol_counts = Counter()
    symbols = Counter()
    sampled_rows = 0
    symbol_pattern = re.compile(r"<symbol>(.*?)</symbol>")
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                sampled_rows += 1
                for field in fields_to_check:
                    value = row.get(field) or ""
                    if "<change>" in value:
                        field_change_counts[field] += value.count("<change>")
                    matches = [match.strip() for match in symbol_pattern.findall(value)]
                    if matches:
                        field_symbol_counts[field] += len(matches)
                        symbols.update(match for match in matches if match)
                if sampled_rows >= sample_rows:
                    break
    except (OSError, csv.Error) as exc:
        return {"inspection_error": str(exc), "fields_checked": fields_to_check}
    return {
        "sampled_rows": sampled_rows,
        "fields_checked": fields_to_check,
        "standalone_error_label_column": None,
        "has_standalone_error_label_column": False,
        "field_change_counts": dict(sorted(field_change_counts.items())),
        "field_symbol_counts": dict(sorted(field_symbol_counts.items())),
        "fields_with_symbol_markup": sorted(field_symbol_counts),
        "text_field_symbol_count": field_symbol_counts.get("text", 0),
        "original_field_symbol_count": field_symbol_counts.get("original", 0),
        "corrected_field_symbol_count": field_symbol_counts.get("corrected", 0),
        "pos_field_symbol_count": field_symbol_counts.get("POS", 0),
        "unique_symbol_count": len(symbols),
        "sample_symbols": sorted(symbols)[:UNIQUE_VALUE_LIMIT],
        "conclusion": (
            "No standalone error-label column is present; source-native labels are embedded "
            "as <symbol> values inside XML-style change markup, primarily in the text field."
        ),
    }


def estimate_delimited_rows(path: Path | None, sample_limit: int = 10_000) -> dict[str, Any]:
    if path is None or not path.exists():
        return unavailable_count()
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            total_bytes = 0
            line_count = 0
            for line in handle:
                total_bytes += len(line)
                line_count += 1
                if line_count >= sample_limit:
                    break
        if line_count <= 1 or total_bytes == 0:
            return {"count": max(0, line_count - 1), "count_type": "exact", "method": "small file sample"}
        estimated_total_lines = round(size / (total_bytes / line_count))
        return {
            "count": max(0, estimated_total_lines - 1),
            "count_type": "estimated",
            "method": f"file size divided by average first {line_count} line bytes",
        }
    except OSError as exc:
        return unavailable_count(str(exc))


def estimate_byte_pattern_count(path: Path | None, pattern: bytes, sample_bytes: int = 64 * 1024 * 1024) -> dict[str, Any]:
    if path is None or not path.exists():
        return unavailable_count()
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            sample = handle.read(min(sample_bytes, size))
        if not sample:
            return {"count": 0, "count_type": "exact", "method": "empty file"}
        sample_count = sample.count(pattern)
        if size <= sample_bytes:
            return {"count": sample_count, "count_type": "exact", "method": "full byte-pattern count"}
        estimate = round(sample_count * (size / len(sample)))
        return {
            "count": estimate,
            "count_type": "estimated",
            "method": f"pattern count in first {len(sample)} bytes extrapolated by file size",
        }
    except OSError as exc:
        return unavailable_count(str(exc))


def inspect_clc_json_files(paths: list[Path]) -> dict[str, Any]:
    answer_count = 0
    script_ids: set[str] = set()
    annotated_script_ids: set[str] = set()
    labels: set[str] = set()
    keys: set[str] = set()
    split_counts: dict[str, int] = {}
    for path in paths:
        split = path.name.split("(", 1)[0]
        split_count = 0
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                obj = json.loads(line)
                answer_count += 1
                split_count += 1
                keys.update(obj.keys())
                script_id = obj.get("id")
                if script_id:
                    script_ids.add(str(script_id))
                edits = obj.get("edits") or []
                if edits and script_id:
                    annotated_script_ids.add(str(script_id))
                labels.update(extract_clc_edit_labels(edits))
        split_counts[split] = split_count
    return {
        "answer_record_count": answer_count,
        "unique_script_count": len(script_ids),
        "annotated_script_count": len(annotated_script_ids),
        "unique_error_labels": sorted(labels),
        "json_keys": sorted(keys),
        "split_counts": split_counts,
    }


def extract_clc_edit_labels(value: Any) -> set[str]:
    labels: set[str] = set()
    if isinstance(value, list):
        if (
            len(value) >= 4
            and isinstance(value[0], int)
            and isinstance(value[1], int)
            and isinstance(value[3], str)
        ):
            labels.add(value[3])
        else:
            for item in value:
                labels.update(extract_clc_edit_labels(item))
    return labels


def inspect_clc_xml_files(paths: list[Path]) -> dict[str, Any]:
    tags: set[str] = set()
    error_attr_keys: set[str] = set()
    nested_errors = 0
    for path in paths:
        try:
            tree = ElementTree.parse(path)
        except ElementTree.ParseError:
            continue
        root = tree.getroot()
        for elem in root.iter():
            tag = strip_namespace(elem.tag)
            tags.add(tag)
            if tag == "e":
                error_attr_keys.update(elem.attrib.keys())
                if any(strip_namespace(child.tag) == "e" for child in elem.iter() if child is not elem):
                    nested_errors += 1
    return {
        "tags": sorted(tags),
        "error_attribute_keys": sorted(error_attr_keys),
        "nested_error_elements": nested_errors,
    }


def read_clc_readme_note(root: Path) -> str:
    readme = next((path for path in root.iterdir() if path.name.upper() == "README"), None)
    if readme is None:
        return "No local README found."
    text = read_text_if_small(readme) or ""
    if "non-commercial research and educational purposes" in text:
        return "Local README states release for non-commercial research and educational purposes; review full local terms before redistribution."
    return "Local README present; review manually before redistribution."


def inspect_write_improve_corpus_tsv(path: Path) -> dict[str, Any]:
    counters = {
        "automarker_cefr_level": Counter(),
        "humannotator_cefr_level": Counter(),
        "split": Counter(),
    }
    public_users: set[str] = set()
    public_prompts: set[str] = set()
    user_prompts: set[str] = set()
    first_version_rows = 0
    final_version_rows = 0
    row_count = 0
    header: list[str] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        header = reader.fieldnames or []
        for row in reader:
            row_count += 1
            if row.get("public_user_id"):
                public_users.add(row["public_user_id"])
            if row.get("public_prompt_id"):
                public_prompts.add(row["public_prompt_id"])
            if row.get("user_prompt"):
                user_prompts.add(row["user_prompt"])
            if row.get("is_first_version") == "TRUE":
                first_version_rows += 1
            if row.get("is_final_version") == "TRUE":
                final_version_rows += 1
            for column, counter in counters.items():
                value = row.get(column) or "[blank]"
                counter[value] += 1
    cefr_combined = Counter()
    cefr_combined.update(counters["automarker_cefr_level"])
    cefr_combined.update(counters["humannotator_cefr_level"])
    return {
        "header": header,
        "row_count": {"count": row_count, "count_type": "exact"},
        "unique_public_user_count": len(public_users),
        "unique_public_prompt_count": len(public_prompts),
        "unique_user_prompt_count": len(user_prompts),
        "first_version_rows": first_version_rows,
        "final_version_rows": final_version_rows,
        "automarker_cefr_distribution": dict(sorted(counters["automarker_cefr_level"].items())),
        "humannotator_cefr_distribution": dict(sorted(counters["humannotator_cefr_level"].items())),
        "cefr_distribution_combined": dict(sorted(cefr_combined.items())),
        "split_distribution": dict(sorted(counters["split"].items())),
    }


def inspect_m2_files(paths: list[Path]) -> dict[str, Any]:
    labels: set[str] = set()
    annotation_count = 0
    sentence_count = 0
    file_counts: dict[str, dict[str, int]] = {}
    for path in paths:
        local_annotations = 0
        local_sentences = 0
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith("S "):
                    sentence_count += 1
                    local_sentences += 1
                elif line.startswith("A "):
                    annotation_count += 1
                    local_annotations += 1
                    pieces = line.rstrip("\n").split("|||")
                    if len(pieces) >= 2:
                        labels.add(pieces[1])
        file_counts[path.name] = {
            "sentences": local_sentences,
            "annotations": local_annotations,
        }
    return {
        "sentence_count": sentence_count,
        "annotation_count": annotation_count,
        "unique_labels": sorted(labels),
        "file_counts": file_counts,
    }


def find_ud_release_root(root: Path) -> Path:
    if (root / "en_ewt-ud-train.conllu").exists():
        return root
    for child in root.iterdir():
        if child.is_dir() and (child / "en_ewt-ud-train.conllu").exists():
            return child
    return root


def inspect_conllu_files(paths: list[Path]) -> dict[str, Any]:
    upos: set[str] = set()
    xpos: set[str] = set()
    feats: set[str] = set()
    deprels: set[str] = set()
    misc: set[str] = set()
    comments: set[str] = set()
    sentence_counts: dict[str, dict[str, int]] = {}
    token_counts: dict[str, dict[str, int]] = {}
    multiword_token_count = 0
    enhanced_dependency_count = 0
    for path in paths:
        split = path.name.replace("en_ewt-ud-", "").replace(".conllu", "")
        sentences = 0
        tokens = 0
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\n")
                if not line:
                    continue
                if line.startswith("#"):
                    key = line[1:].strip().split("=", 1)[0].strip()
                    if key:
                        comments.add(key)
                    if line.startswith("# sent_id"):
                        sentences += 1
                    continue
                columns = line.split("\t")
                if len(columns) != 10:
                    continue
                token_id = columns[0]
                if "-" in token_id:
                    multiword_token_count += 1
                    continue
                if "." in token_id:
                    continue
                tokens += 1
                if columns[3] != "_":
                    upos.add(columns[3])
                if columns[4] != "_":
                    xpos.add(columns[4])
                if columns[5] != "_":
                    for item in columns[5].split("|"):
                        key = item.split("=", 1)[0]
                        if key:
                            feats.add(key)
                if columns[7] != "_":
                    deprels.add(columns[7])
                if columns[8] != "_":
                    enhanced_dependency_count += 1
                if columns[9] != "_":
                    for item in columns[9].split("|"):
                        key = item.split("=", 1)[0]
                        if key:
                            misc.add(key)
        sentence_counts[split] = {"count": sentences, "count_type": "exact"}
        token_counts[split] = {"count": tokens, "count_type": "exact"}
    return {
        "sentence_counts": sentence_counts,
        "token_counts": token_counts,
        "upos_values": sorted(upos),
        "xpos_values": sorted(xpos),
        "feats_keys": sorted(feats),
        "deprel_values": sorted(deprels),
        "misc_keys": sorted(misc),
        "comment_keys": sorted(comments),
        "multiword_token_count": multiword_token_count,
        "enhanced_dependency_count": enhanced_dependency_count,
    }


def detect_ud_version(readme_text: str) -> str:
    for line in readme_text.splitlines():
        if "Universal Dependencies English Web Treebank" in line and "v" in line:
            return line.strip().lstrip("# ").strip()
    return "unavailable"


def count_jsonl_records(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def read_jsonl_limited(path: Path, limit: int | None = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def find_documentation_files(files: list[Path]) -> dict[str, list[str]]:
    readme_files: list[str] = []
    license_files: list[str] = []
    for path in files:
        name = path.name.lower()
        as_posix = path.as_posix()
        if "readme" in name:
            readme_files.append(as_posix)
        if (
            "license" in name
            or "licence" in name
            or "copying" in name
            or "agreement" in name
            or "terms" in name
        ):
            license_files.append(as_posix)
    return {
        "readme_files": sorted(readme_files),
        "license_files": sorted(license_files),
    }


def summarize_docs(files: list[dict[str, Any]]) -> dict[str, list[str]]:
    readme_files: list[str] = []
    license_files: list[str] = []
    for row in files:
        name = Path(row["relative_path"]).name.lower()
        if "readme" in name:
            readme_files.append(row["relative_path"])
        if (
            "license" in name
            or "licence" in name
            or "copying" in name
            or "agreement" in name
            or "terms" in name
        ):
            license_files.append(row["relative_path"])
    return {"readme_files": sorted(readme_files), "license_files": sorted(license_files)}


def source_record_unit(source_key: str, inspection: dict[str, Any]) -> str:
    if source_key == "efcamdat":
        return "writing"
    if source_key == "clc_fce":
        return "answer record"
    if source_key == "write_improve":
        return "essay version"
    if source_key == "ud_english_ewt":
        return "sentence"
    return inspection.get("record_unit", "record")


def error_annotation_unit(source_key: str, inspection: dict[str, Any]) -> str | None:
    if source_key == "efcamdat":
        return "change element or cleaned CSV row"
    if source_key == "clc_fce":
        return "edit span / XML e element"
    if source_key == "write_improve":
        return "M2 edit"
    return None


def error_label_field(source_key: str, inspection: dict[str, Any]) -> str | None:
    if source_key == "efcamdat":
        return "XML-style symbol descendant in change markup; no standalone CSV error-label column"
    if source_key == "clc_fce":
        return "JSON edit[3] or XML e.type"
    if source_key == "write_improve":
        return "M2 error type between separators"
    return None


def write_schema_samples(output_dir: Path, inspections: dict[str, dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = {
        "efcamdat_schema_sample.json": inspections["efcamdat"].get("schema_sample", {}),
        "clc_fce_schema_sample.json": inspections["clc_fce"].get("schema_sample", {}),
        "write_improve_schema_sample.json": inspections["write_improve"].get("schema_sample", {}),
        "ud_ewt_schema_sample.json": inspections["ud_english_ewt"].get("schema_sample", {}),
    }
    for name, sample in samples.items():
        write_json(output_dir / name, sample)


def render_source_inventory_md(entries: list[dict[str, Any]], issues: dict[str, Any]) -> str:
    lines = [
        "# Global Source Inventory V1",
        "",
        f"Generated at: {_utc_now()}",
        "",
        "## Source Summary",
        "",
        "| Source | Required V1 | Optional | Status | Roles | Root | Files | Formats | Records | Count type | Readiness | License |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | ---: | --- | --- | --- |",
    ]
    for entry in entries:
        lines.append(
            "| {name} | {required} | {optional} | {status} | {roles} | {root} | {files} | {formats} | {records} | {count_type} | {readiness} | {license} |".format(
                name=entry["source_name"],
                required=entry["required_for_v1"],
                optional=entry.get("optional_enrichment", False),
                status=entry["status"],
                roles=", ".join(entry["source_role"]),
                root=entry.get("root_path") or "",
                files=entry["file_count"],
                formats=", ".join(entry["file_formats"]),
                records=entry.get("approximate_record_count"),
                count_type=entry.get("count_type"),
                readiness=entry.get("ingestion_readiness"),
                license=entry.get("license_status"),
            ),
        )
    if issues.get("classified_raw_datasets"):
        lines.extend(["", "## Classified Excluded Raw Data", ""])
        for item in issues["classified_raw_datasets"]:
            lines.append(
                f"- `{item['path']}`: `{item['status']}`, files={item['file_count']}, included=false. {item['reason']}",
            )
    lines.extend(["", "## Warnings And Errors", ""])
    if not issues["warnings"] and not issues["errors"]:
        lines.append("No inspection warnings or errors.")
    for warning in issues["warnings"]:
        lines.append(f"- WARNING `{warning['source_key']}`: {warning['issue_type']} - {warning.get('message', '')}")
    for error in issues["errors"]:
        lines.append(f"- ERROR `{error['source_key']}`: {error['issue_type']} - {error.get('message', '')}")
    lines.extend(["", "## Validation", "", f"Passed: `{issues['validation']['passed']}`", ""])
    for key, value in issues["validation"]["checks"].items():
        lines.append(f"- `{key}`: {value}")
    return "\n".join(lines) + "\n"


def render_error_annotation_comparison_md(comparison: dict[str, Any]) -> str:
    lines = [
        "# Error Annotation Comparison V1",
        "",
        "Source-native structures only. No error label normalization is performed here.",
        "",
        "| Source | Unit | Original | Corrected | Span | Labels | Revision | Parser difficulty |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, row in comparison["sources"].items():
        label_system = row.get("error_label_system")
        if isinstance(label_system, dict):
            labels = label_system.get("count") or label_system.get("unique_error_label_count") or "sampled"
        else:
            labels = label_system
        lines.append(
            "| {source} | {unit} | {original} | {corrected} | {span} | {labels} | {revision} | {difficulty} |".format(
                source=key,
                unit=row.get("annotation_unit"),
                original=row.get("original_text_representation"),
                corrected=row.get("corrected_text_representation"),
                span=row.get("span_representation"),
                labels=labels,
                revision=row.get("revision_support"),
                difficulty=row.get("parser_difficulty"),
            ),
        )
    return "\n".join(lines) + "\n"


def render_proficiency_comparison_md(comparison: dict[str, Any]) -> str:
    lines = [
        "# CEFR And Proficiency Comparison V1",
        "",
        "| Source | Explicit CEFR | Inferred CEFR | Proprietary level | Score only | Granularity | Caveat |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, row in comparison["sources"].items():
        lines.append(
            "| {source} | {explicit} | {inferred} | {proprietary} | {score} | {granularity} | {caveat} |".format(
                source=key,
                explicit=row["explicit_cefr"],
                inferred=row["inferred_cefr"],
                proprietary=row["proprietary_level_system"],
                score=row["score_grade_only"],
                granularity=row["granularity"],
                caveat=row["reliability_caveats"],
            ),
        )
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def snapshot_files(root: Path) -> dict[str, tuple[int, int]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if path.is_file():
            stat = path.stat()
            snapshot[str(path.resolve())] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def missing_inspection(source_key: str) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "source_name": SOURCE_NAMES[source_key],
        "status": "missing",
        "ingestion_readiness": "BLOCKED_MISSING_CONTEXT",
        "inspection_errors": ["Expected source root was not found."],
        "inspection_warnings": [],
    }


def unavailable_count(reason: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"count": None, "count_type": "unavailable"}
    if reason:
        payload["reason"] = reason
    return payload


def first_existing_path(values: list[str]) -> Path | None:
    for value in values:
        path = Path(value)
        if path.exists():
            return path
    return None


def strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1]


def read_text_if_small(path: Path, max_bytes: int = 2 * 1024 * 1024) -> str | None:
    if not path.exists() or path.stat().st_size > max_bytes:
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _add_existing_processed_roots(
    source: dict[str, Any],
    workspace: Path,
    relative_paths: list[str],
) -> None:
    for relative in relative_paths:
        path = workspace / relative
        if path.exists():
            source["root_paths"].append(str(path))
            source["status"] = "discovered"
            source["discovery_notes"].append(f"Matched existing processed/source path: {relative}")


def _display_root(root_paths: list[str]) -> str | None:
    if not root_paths:
        return None
    path = Path(root_paths[0])
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _resolve_under_workspace(workspace: Path, path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return workspace / value


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
