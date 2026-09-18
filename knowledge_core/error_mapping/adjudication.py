from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge_core.error_mapping.paths import (
    DECISIONS_FILE,
    DEFAULT_ERROR_INSTANCE_PATHS,
    DEFAULT_MAPPINGS_PATH,
    DEFAULT_REVIEW_DIR,
)


DEFAULT_CLC_SOURCE_RECORDS = Path("data/interim/clc_fce/source_records.jsonl")
DEFAULT_UD_ROOT = Path("data/raw/UD_English-EWT-master/UD_English-EWT-master")
DECISION_FIELDS = [
    "mapping_id",
    "reviewer_decision",
    "reviewer_note",
    "reviewed_by",
    "reviewed_at",
]
BE_FORMS = {"am", "is", "are", "was", "were", "be", "been", "being"}


def adjudicate_clc_agv_mappings(
    *,
    mappings_path: str | Path = DEFAULT_MAPPINGS_PATH,
    errors_path: str | Path = DEFAULT_ERROR_INSTANCE_PATHS["clc_fce"],
    source_records_path: str | Path = DEFAULT_CLC_SOURCE_RECORDS,
    ud_root: str | Path = DEFAULT_UD_ROOT,
    decisions_path: str | Path = DEFAULT_REVIEW_DIR / DECISIONS_FILE,
    reviewed_by: str = "codex_assisted_review_on_user_request",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    timestamp = reviewed_at or datetime.now(timezone.utc).isoformat()
    mappings = _load_jsonl(Path(mappings_path))
    mapping_by_error = {
        item["error_instance_id"]: item
        for item in mappings
        if item.get("source_key") == "clc_fce"
    }
    errors = {
        item["error_instance_id"]: item
        for item in _load_jsonl(Path(errors_path))
        if item["error_instance_id"] in mapping_by_error
    }
    source_ids = {item["source_record_id"] for item in errors.values()}
    source_records = {
        item["source_record_id"]: item
        for item in _load_jsonl(Path(source_records_path))
        if item["source_record_id"] in source_ids
    }
    raw_records = _load_needed_raw_records(source_records)
    third_person_pairs = _third_person_pairs(Path(ud_root))

    decisions = []
    for error_id, mapping in sorted(mapping_by_error.items(), key=lambda item: item[1]["mapping_id"]):
        error = errors[error_id]
        source_record = source_records[error["source_record_id"]]
        raw_record = raw_records[source_record["native_record_id"]]
        original, correction = _resolve_edit(raw_record, error)
        decision, note = classify_agreement_edit(
            original,
            correction,
            third_person_pairs,
        )
        decisions.append(
            {
                "mapping_id": mapping["mapping_id"],
                "reviewer_decision": decision,
                "reviewer_note": note,
                "reviewed_by": reviewed_by if decision in {"APPROVE", "REJECT"} else "",
                "reviewed_at": timestamp if decision in {"APPROVE", "REJECT"} else "",
            }
        )
    _write_csv(Path(decisions_path), decisions)
    counts = defaultdict(int)
    for item in decisions:
        counts[item["reviewer_decision"]] += 1
    return {
        "total": len(decisions),
        "approved": counts["APPROVE"],
        "rejected": counts["REJECT"],
        "needs_review": counts["NEEDS_REVIEW"],
        "raw_learner_text_emitted": False,
        "method": "clc_agv_ud_morphology_adjudication_v1",
        "decisions_path": str(decisions_path).replace("\\", "/"),
    }


def classify_agreement_edit(
    original: str,
    correction: str,
    third_person_pairs: set[tuple[str, str]],
) -> tuple[str, str]:
    original_tokens = _word_tokens(original)
    correction_tokens = _word_tokens(correction)
    if len(original_tokens) != len(correction_tokens) or not original_tokens:
        return (
            "NEEDS_REVIEW",
            "Edit structure is not a one-to-one token replacement; sentence-level review is required.",
        )
    changed = [
        (left, right)
        for left, right in zip(original_tokens, correction_tokens)
        if left != right
    ]
    if not changed:
        return "NEEDS_REVIEW", "No distinct morphological replacement could be established."
    kinds = [_pair_kind(left, right, third_person_pairs) for left, right in changed]
    if all(kind == "third_person_s" for kind in kinds):
        return (
            "APPROVE",
            "Source correction confirms a present-tense base/non-3SG to third-person singular form contrast for the same lexical verb.",
        )
    if all(kind == "be_agreement" for kind in kinds):
        return (
            "REJECT",
            "Source correction is agreement of the verb 'be', not the lexical present-simple third-person -s skill.",
        )
    return (
        "NEEDS_REVIEW",
        "AGV is confirmed, but the correction does not deterministically identify the canonical third-person -s morphology.",
    )


def _pair_kind(
    left: str,
    right: str,
    third_person_pairs: set[tuple[str, str]],
) -> str:
    if {left, right} <= BE_FORMS:
        return "be_agreement"
    if (left, right) in third_person_pairs or (right, left) in third_person_pairs:
        return "third_person_s"
    if right in _third_person_spellings(left) or left in _third_person_spellings(right):
        return "third_person_s"
    return "other"


def _third_person_spellings(base: str) -> set[str]:
    forms = {base + "s"}
    if base.endswith(("s", "sh", "ch", "x", "z", "o")):
        forms.add(base + "es")
    if len(base) > 1 and base.endswith("y") and base[-2] not in "aeiou":
        forms.add(base[:-1] + "ies")
    return forms


def _third_person_pairs(root: Path) -> set[tuple[str, str]]:
    pairs = {("has", "have"), ("does", "do")}
    for path in sorted(root.glob("en_ewt-ud-*.conllu")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    continue
                columns = line.rstrip("\n").split("\t")
                if len(columns) != 10 or not columns[0].isdigit():
                    continue
                features = set(columns[5].split("|"))
                if (
                    columns[3] in {"VERB", "AUX"}
                    and {"Person=3", "Number=Sing", "Tense=Pres", "VerbForm=Fin"}
                    <= features
                    and columns[2].lower() != "be"
                ):
                    pairs.add((columns[1].lower(), columns[2].lower()))
    return pairs


def _resolve_edit(raw_record: dict[str, Any], error: dict[str, Any]) -> tuple[str, str]:
    start = error["span"]["start_char"]
    end = error["span"]["end_char"]
    expected_hash = error["correction"]["correction_fingerprint"].split(":", 1)[1]
    corrections = []
    for group in raw_record.get("edits", []):
        for edit_start, edit_end, first, second in group[1]:
            if edit_start != start or edit_end != end:
                continue
            if _sha256(second or "") == expected_hash:
                corrections.append(second or "")
            elif _sha256(first or "") == expected_hash:
                corrections.append(first or "")
    if len(corrections) != 1:
        return raw_record["text"][start:end], ""
    return raw_record["text"][start:end], corrections[0]


def _load_needed_raw_records(source_records: dict[str, dict[str, Any]]) -> dict[str, dict]:
    needed = {item["native_record_id"] for item in source_records.values()}
    records = {}
    by_path = {Path(item["source_path"]) for item in source_records.values()}
    for path in sorted(by_path):
        split = path.name.split("(", 1)[0]
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line)
                native_id = (
                    f"{split}:session{payload['session']}:"
                    f"script{payload['id']}:q{payload['q']}"
                )
                if native_id in needed:
                    records[native_id] = payload
    missing = needed - set(records)
    if missing:
        raise ValueError(f"Missing {len(missing)} raw CLC FCE records required for review")
    return records


def _word_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?", value.lower())


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
