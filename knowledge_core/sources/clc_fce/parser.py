from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from knowledge_core.normalization.error_taxonomy.ids import (
    make_error_instance_id,
    make_source_record_id,
    stable_hash,
)
from knowledge_core.normalization.error_taxonomy.models import (
    ErrorCorrection,
    ErrorInstance,
    LearnerCorpusSourceRecord,
    SourceNativeErrorLabel,
    TextSpan,
)
from knowledge_core.normalization.error_taxonomy.policy import fingerprint_text
from knowledge_core.sources.clc_fce.models import (
    CLCFCEInputFiles,
    CLCFCEXMLAnswerSummary,
    CLCFCEXMLErrorNode,
    ParsedCLCFCECorpus,
)
from knowledge_core.sources.clc_fce.paths import DEFAULT_RAW_ROOT, SOURCE_KEY, SPLIT_FILE_PREFIXES


class CLCFCEParseError(RuntimeError):
    """Raised when CLC FCE source files cannot be parsed."""


def discover_input_files(root: str | Path = DEFAULT_RAW_ROOT) -> CLCFCEInputFiles:
    raw_root = Path(root)
    json_by_split: dict[str, Path] = {}
    xml_by_split: dict[str, Path] = {}
    for split, prefix in SPLIT_FILE_PREFIXES.items():
        json_matches = sorted(raw_root.glob(f"{prefix}*.json"))
        xml_matches = sorted(raw_root.glob(f"{prefix}*.xml"))
        if not json_matches:
            raise CLCFCEParseError(f"Missing CLC FCE JSON file for split: {split}")
        if not xml_matches:
            raise CLCFCEParseError(f"Missing CLC FCE XML file for split: {split}")
        json_by_split[split] = json_matches[0]
        xml_by_split[split] = xml_matches[0]
    return CLCFCEInputFiles(json_by_split=json_by_split, xml_by_split=xml_by_split)


def parse_clc_fce_corpus(root: str | Path = DEFAULT_RAW_ROOT) -> ParsedCLCFCECorpus:
    input_files = discover_input_files(root)
    xml_summaries = parse_xml_answer_summaries(input_files.xml_by_split)
    source_records: list[LearnerCorpusSourceRecord] = []
    error_instances: list[ErrorInstance] = []
    for split, path in input_files.json_by_split.items():
        for line_number, payload in iter_json_records(path):
            source_record = build_source_record(
                payload,
                split=split,
                source_path=path,
                line_number=line_number,
                xml_summary=xml_summaries.get(_native_record_id(split, payload)),
            )
            source_records.append(source_record)
            error_instances.extend(
                build_error_instances(
                    payload,
                    split=split,
                    source_record=source_record,
                    source_path=path,
                ),
            )
    return ParsedCLCFCECorpus(
        source_records=source_records,
        error_instances=error_instances,
        xml_answer_summaries=xml_summaries,
        input_files=input_files,
    )


def iter_json_records(path: str | Path) -> Iterator[tuple[int, dict[str, Any]]]:
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CLCFCEParseError(
                    f"Invalid JSON in {source_path} line {line_number}: {exc}",
                ) from exc
            if not isinstance(payload, dict):
                raise CLCFCEParseError(
                    f"Expected object in {source_path} line {line_number}",
                )
            yield line_number, payload


def build_source_record(
    payload: dict[str, Any],
    *,
    split: str,
    source_path: Path,
    line_number: int,
    xml_summary: CLCFCEXMLAnswerSummary | None,
) -> LearnerCorpusSourceRecord:
    text = _text(payload.get("text"))
    text_fingerprint, text_length = fingerprint_text(text)
    native_record_id = _native_record_id(split, payload)
    script_id = _text(payload.get("id"))
    session = _text(payload.get("session"))
    question_id = _text(payload.get("q"))
    source_record_id = make_source_record_id(
        source_key=SOURCE_KEY,
        native_record_id=native_record_id,
        split=split,
    )
    return LearnerCorpusSourceRecord(
        source_record_id=source_record_id,
        source_key=SOURCE_KEY,
        native_record_id=native_record_id,
        record_unit="answer",
        split=split,
        learner_id_pseudonym=f"sha256:{stable_hash({'source': SOURCE_KEY, 'script_id': script_id}, length=64)}",
        document_id_pseudonym=f"sha256:{stable_hash({'source': SOURCE_KEY, 'script_id': script_id, 'session': session}, length=64)}",
        task_id=f"{session}:q{question_id}",
        proficiency_label="FCE_B2",
        source_path=str(source_path).replace("\\", "/"),
        text_fingerprint=text_fingerprint,
        text_length=text_length,
        metadata={
            "age": _optional_scalar(payload.get("age")),
            "l1": _optional_scalar(payload.get("l1")),
            "score": _optional_scalar(payload.get("score")),
            "combined_score": _optional_scalar(payload.get("combined-score")),
            "score_old_scale": _optional_scalar(payload.get("score-old-scale")),
            "new_scores_present": "new-scores" in payload,
            "json_line_number": line_number,
            "xml_error_count": xml_summary.error_count if xml_summary else 0,
            "xml_nested_error_count": xml_summary.nested_error_count if xml_summary else 0,
            "xml_max_error_depth": xml_summary.max_error_depth if xml_summary else 0,
        },
        provenance={
            "parser": "clc_fce_ingestion_v1",
            "json_source_file": str(source_path).replace("\\", "/"),
            "xml_source_file": xml_summary.source_path if xml_summary else None,
        },
    )


def build_error_instances(
    payload: dict[str, Any],
    *,
    split: str,
    source_record: LearnerCorpusSourceRecord,
    source_path: Path,
) -> list[ErrorInstance]:
    text_length = source_record.text_length or 0
    errors: list[ErrorInstance] = []
    for group_index, edit_tuple in enumerate(_iter_edit_tuples(payload.get("edits"))):
        edit_index, start, end, correction, label = edit_tuple
        correction_text = str(correction or "")
        correction = _build_correction(correction_text, start=start, end=end)
        native_error_id = (
            f"{source_record.native_record_id}:group{group_index}:edit{edit_index}"
        )
        span_payload = {
            "span_kind": "json_char_offsets",
            "start_char": start,
            "end_char": end,
        }
        label_payload = {"label_system": "clc_fce_error_code", "label": label}
        error_id = make_error_instance_id(
            source_key=SOURCE_KEY,
            source_record_id=source_record.source_record_id,
            native_error_id=native_error_id,
            span_payload=span_payload,
            label_payload=label_payload,
        )
        parser_notes = []
        if start > text_length or end > text_length:
            parser_notes.append("json_span_exceeds_text_length")
        if _is_compound_label(label):
            parser_notes.append("compound_or_nested_source_label_requires_review")
        errors.append(
            ErrorInstance(
                error_instance_id=error_id,
                source_record_id=source_record.source_record_id,
                source_key=SOURCE_KEY,
                native_error_id=native_error_id,
                source_native_label=SourceNativeErrorLabel(
                    label_system="clc_fce_error_code",
                    label=label,
                    label_path=_label_path(label),
                ),
                span=TextSpan(
                    span_kind="json_char_offsets",
                    source_field="text",
                    start_char=start,
                    end_char=end,
                    confidence=0.95,
                ),
                correction=correction,
                status="parsed",
                review_status=(
                    "needs_review"
                    if parser_notes or _is_compound_label(label)
                    else "pending"
                ),
                parser_notes=parser_notes,
                metadata={
                    "split": split,
                    "edit_group_index": group_index,
                    "edit_index": edit_index,
                    "correction_present": bool(correction_text),
                    "correction_length": len(correction_text),
                },
                provenance={
                    "parser": "clc_fce_ingestion_v1",
                    "json_source_file": str(source_path).replace("\\", "/"),
                },
            ),
        )
    return errors


def parse_xml_answer_summaries(
    xml_by_split: dict[str, Path],
) -> dict[str, CLCFCEXMLAnswerSummary]:
    summaries: dict[str, CLCFCEXMLAnswerSummary] = {}
    for split, path in xml_by_split.items():
        tree = ET.parse(path)
        root = tree.getroot()
        for script in root.findall("script"):
            script_id = _text(script.attrib.get("id"))
            session = _text(script.attrib.get("session"))
            for answer in script.findall("answer"):
                question_id = _text(answer.attrib.get("q"))
                native_record_id = _native_record_id_from_parts(
                    split=split,
                    session=session,
                    script_id=script_id,
                    question_id=question_id,
                )
                text_node = answer.find("text")
                error_nodes: tuple[CLCFCEXMLErrorNode, ...] = ()
                if text_node is not None:
                    error_nodes = tuple(_collect_xml_error_nodes(text_node))
                summaries[native_record_id] = CLCFCEXMLAnswerSummary(
                    native_record_id=native_record_id,
                    split=split,
                    script_id=script_id,
                    session=session,
                    question_id=question_id,
                    source_path=str(path).replace("\\", "/"),
                    error_nodes=error_nodes,
                )
    return summaries


def _collect_xml_error_nodes(
    element: ET.Element,
    *,
    depth: int = 0,
    path: str = "text",
) -> Iterator[CLCFCEXMLErrorNode]:
    tag_counts: dict[str, int] = {}
    for child in list(element):
        tag_counts[child.tag] = tag_counts.get(child.tag, 0) + 1
        child_path = f"{path}/{child.tag}[{tag_counts[child.tag]}]"
        if child.tag == "e":
            incorrect = child.find("i")
            correction = child.find("c")
            incorrect_text = "".join(incorrect.itertext()) if incorrect is not None else ""
            correction_text = "".join(correction.itertext()) if correction is not None else ""
            incorrect_fp, incorrect_len = _fingerprint_optional(incorrect_text)
            correction_fp, correction_len = _fingerprint_optional(correction_text)
            nested = [descendant for descendant in child.iter("e") if descendant is not child]
            yield CLCFCEXMLErrorNode(
                label=_text(child.attrib.get("type")),
                path=child_path,
                depth=depth + 1,
                incorrect_fingerprint=incorrect_fp,
                incorrect_length=incorrect_len,
                correction_fingerprint=correction_fp,
                correction_length=correction_len,
                child_error_count=len(nested),
            )
        yield from _collect_xml_error_nodes(child, depth=depth + (1 if child.tag == "e" else 0), path=child_path)


def _iter_edit_tuples(edits: Any) -> Iterator[tuple[int, int, int, str, str]]:
    if not isinstance(edits, list):
        return
    tuple_counter = 0
    for group in edits:
        if not isinstance(group, list) or len(group) != 2:
            continue
        _group_id, edit_items = group
        if not isinstance(edit_items, list):
            continue
        for item in edit_items:
            if not isinstance(item, list) or len(item) < 4:
                continue
            start, end, correction, label = item[:4]
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            yield tuple_counter, start, end, str(correction or ""), str(label or "")
            tuple_counter += 1


def _build_correction(correction: str, *, start: int, end: int) -> ErrorCorrection:
    if correction:
        fingerprint, length = fingerprint_text(correction)
        correction_type = "insertion" if start == end else "replacement"
        return ErrorCorrection(
            correction_type=correction_type,
            correction_fingerprint=fingerprint,
            correction_length=length,
        )
    return ErrorCorrection(correction_type="deletion")


def _native_record_id(split: str, payload: dict[str, Any]) -> str:
    return _native_record_id_from_parts(
        split=split,
        session=_text(payload.get("session")),
        script_id=_text(payload.get("id")),
        question_id=_text(payload.get("q")),
    )


def _native_record_id_from_parts(
    *,
    split: str,
    session: str,
    script_id: str,
    question_id: str,
) -> str:
    return f"{split}:session{session}:script{script_id}:q{question_id}"


def _fingerprint_optional(value: str) -> tuple[str | None, int | None]:
    if value == "":
        return None, None
    fingerprint, length = fingerprint_text(value)
    return fingerprint, length


def _is_compound_label(label: str) -> bool:
    return "(" in label or ")" in label


def _label_path(label: str) -> str | None:
    if not _is_compound_label(label):
        return None
    return label.replace("(", "/").replace(")", "")


def _text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text


def _optional_scalar(value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    return text or None

