from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_SCHEMA_VERSION = "knowledge_source_manifest_v1"
EXPECTED_SOURCE_KEYS = {
    "efcamdat",
    "clc_fce",
    "write_improve",
    "ud_english_ewt",
    "english_grammar_profile",
    "cefr_companion_volume_2020",
}


def build_source_manifest(
    *,
    inventory_path: str | Path = "data/reports/source_inventory/source_inventory.json",
    file_inventory_path: str | Path = "data/reports/source_inventory/file_inventory.jsonl",
    governance_path: str | Path = "data/reports/source_inventory/source_governance.json",
    output_path: str | Path = "data/curated/source_metadata/source_manifest.json",
    file_output_path: str | Path = "data/curated/source_metadata/source_file_manifest.jsonl",
) -> dict[str, Any]:
    inventory = _load_json(Path(inventory_path))
    governance = _load_json(Path(governance_path))
    files = _load_jsonl(Path(file_inventory_path))
    governance_by_source = {
        item["source_key"]: item for item in governance.get("sources", [])
    }

    manifest_files: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for source in inventory.get("sources", []):
        source_key = source["source_key"]
        root_path = PurePosixPath(str(source["root_path"]).replace("\\", "/"))
        source_files = []
        for item in files:
            relative_path = PurePosixPath(str(item["relative_path"]).replace("\\", "/"))
            if item.get("source_key") != source_key or not relative_path.is_relative_to(root_path):
                continue
            record = {
                "source_key": source_key,
                "relative_path": str(relative_path),
                "source_relative_path": item.get("source_relative_path"),
                "size_bytes": int(item["size_bytes"]),
                "extension": item.get("extension") or "",
                "checksum_algorithm": (
                    "sha256" if item.get("checksum_status") == "sha256" else None
                ),
                "checksum": item.get("checksum_sha256"),
                "checksum_status": item.get("checksum_status") or "unavailable",
            }
            record["manifest_record_hash"] = _stable_hash(record)
            source_files.append(record)
        source_files.sort(key=lambda item: item["relative_path"])
        manifest_files.extend(source_files)
        checksum_count = sum(item["checksum_status"] == "sha256" for item in source_files)
        missing_count = len(source_files) - checksum_count
        governance_entry = governance_by_source.get(source_key, {})
        version = _known_value(source.get("detected_version"), unknown={"unavailable", "unknown"})
        year = _known_value(source.get("publication_year"), unknown={"unavailable", "unknown"})
        source_manifest_hash = _stable_hash(
            [item["manifest_record_hash"] for item in source_files]
        )
        sources.append(
            {
                "source_key": source_key,
                "source_name": source.get("source_name"),
                "required_for_v1": bool(source.get("required_for_v1")),
                "source_roles": source.get("source_role", []),
                "root_path": str(root_path),
                "detected_version": version["value"],
                "version_status": version["status"],
                "publication_year": year["value"],
                "publication_year_status": year["status"],
                "license_status": governance_entry.get(
                    "license_status",
                    "needs_manual_review",
                ),
                "redistribution_notes": source.get("redistribution_notes", []),
                "official_source_urls": governance_entry.get("official_source_urls", []),
                "manifest_file_count": len(source_files),
                "manifest_size_bytes": sum(item["size_bytes"] for item in source_files),
                "sha256_file_count": checksum_count,
                "checksum_unavailable_count": missing_count,
                "checksum_coverage": round(checksum_count / len(source_files), 8)
                if source_files
                else 0.0,
                "source_manifest_hash": source_manifest_hash,
            }
        )

    sources.sort(key=lambda item: item["source_key"])
    _validate_manifest(sources, manifest_files, issues)
    errors = [item for item in issues if item["severity"] == "error"]
    warnings = [item for item in issues if item["severity"] == "warning"]
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inventory_generated_at": inventory.get("generated_at"),
        "source_count": len(sources),
        "file_count": len(manifest_files),
        "sources": sources,
        "validation": {
            "passed": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "issues": issues,
        },
        "limitations": [
            "Manifest records only locally evidenced versions, years, licenses, and checksums.",
            "Files marked checksum_unavailable are retained explicitly and are not re-hashed by this promotion step.",
            "A needs_manual_review license status is not a license conclusion.",
        ],
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_jsonl(Path(file_output_path), manifest_files)
    return manifest


def _validate_manifest(sources, files, issues) -> None:
    source_keys = {item["source_key"] for item in sources}
    if source_keys != EXPECTED_SOURCE_KEYS:
        issues.append(_issue("error", "source_set_mismatch", str(sorted(source_keys))))
    paths = [(item["source_key"], item["relative_path"]) for item in files]
    if len(paths) != len(set(paths)):
        issues.append(_issue("error", "duplicate_file", "Duplicate source file path"))
    for item in files:
        checksum = item.get("checksum")
        if item["checksum_status"] == "sha256" and (
            not isinstance(checksum, str)
            or len(checksum) != 64
            or any(char not in "0123456789abcdef" for char in checksum.lower())
        ):
            issues.append(_issue("error", "invalid_sha256", item["relative_path"]))
    for source in sources:
        actual = sum(item["source_key"] == source["source_key"] for item in files)
        if actual != source["manifest_file_count"]:
            issues.append(_issue("error", "file_count_mismatch", source["source_key"]))
        if source["checksum_unavailable_count"]:
            issues.append(
                _issue(
                    "warning",
                    "checksum_coverage_incomplete",
                    f"{source['source_key']}: {source['checksum_unavailable_count']} file(s)",
                )
            )
        if source["license_status"] == "needs_manual_review":
            issues.append(_issue("warning", "license_needs_manual_review", source["source_key"]))


def _known_value(value: Any, *, unknown: set[str]) -> dict[str, Any]:
    normalized = str(value).strip() if value is not None else ""
    if not normalized or normalized.lower() in unknown:
        return {"value": None, "status": "unavailable"}
    return {"value": normalized, "status": "locally_evidenced"}


def _stable_hash(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}
