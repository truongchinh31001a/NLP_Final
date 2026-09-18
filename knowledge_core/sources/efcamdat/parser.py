from __future__ import annotations

import csv
import html
import re
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
from knowledge_core.sources.efcamdat.models import (
    EFCAMDATCSVSupportSummary,
    EFCAMDATWritingBlock,
)
from knowledge_core.sources.efcamdat.paths import DEFAULT_CSV_PATH, DEFAULT_XML_PATH, SOURCE_KEY


class EFCAMDATParseError(RuntimeError):
    """Raised when EFCAMDAT source files cannot be parsed."""


_WRITING_ATTR_RE = re.compile(
    r"<writing\s+id=\"(?P<id>[^\"]+)\"\s+level=\"(?P<level>[^\"]*)\"\s+unit=\"(?P<unit>[^\"]*)\"",
)
_LEARNER_RE = re.compile(
    r"<learner\s+id=\"(?P<id>[^\"]*)\"(?:\s+nationality=\"(?P<nationality>[^\"]*)\")?",
)
_TOPIC_RE = re.compile(r"<topic\s+id=\"(?P<id>[^\"]*)\"")
_GRADE_RE = re.compile(r"<grade>(?P<grade>.*?)</grade>", re.DOTALL)
_TEXT_RE = re.compile(r"<text>(?P<text>.*?)</text>", re.DOTALL)
_CHANGE_RE = re.compile(r"<change>(?P<change>.*?)</change>", re.DOTALL)
_TAG_RE = re.compile(r"<{tag}>(?P<value>.*?)</{tag}>", re.DOTALL)
_STRIP_TAGS_RE = re.compile(r"<[^>]+>")


def iter_writing_blocks(xml_path: str | Path = DEFAULT_XML_PATH) -> Iterator[EFCAMDATWritingBlock]:
    path = Path(xml_path)
    if not path.exists():
        raise EFCAMDATParseError(f"EFCAMDAT XML not found: {path}")
    block_lines: list[str] = []
    in_writing = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if "<writing " in line and not in_writing:
                in_writing = True
                block_lines = [line]
                continue
            if in_writing:
                block_lines.append(line)
                if "</writing>" in line:
                    raw_block = "".join(block_lines)
                    yield parse_writing_block(
                        raw_block,
                        source_path=path,
                        start_line_number=line_number - len(block_lines) + 1,
                    )
                    in_writing = False
                    block_lines = []
        if in_writing and block_lines:
            raw_block = "".join(block_lines)
            yield parse_writing_block(
                raw_block,
                source_path=path,
                start_line_number=line_number - len(block_lines) + 1,
                forced_note="unterminated_writing_block",
            )


def parse_writing_block(
    raw_block: str,
    *,
    source_path: Path,
    start_line_number: int = 1,
    forced_note: str | None = None,
) -> EFCAMDATWritingBlock:
    parser_notes = [forced_note] if forced_note else []
    try:
        element = ET.fromstring(raw_block)
    except ET.ParseError as exc:
        parser_notes.append(f"xml_parse_fallback:{exc.__class__.__name__}")
        return _parse_writing_block_regex(
            raw_block,
            source_path=source_path,
            start_line_number=start_line_number,
            parser_notes=tuple(parser_notes),
        )
    return _parse_writing_element(
        element,
        source_path=source_path,
        start_line_number=start_line_number,
        parser_notes=tuple(parser_notes),
    )


def inspect_csv_support(
    csv_path: str | Path = DEFAULT_CSV_PATH,
    *,
    chunk_size: int = 50_000,
    track_unique_writing_ids: bool = True,
) -> EFCAMDATCSVSupportSummary:
    path = Path(csv_path)
    if not path.exists():
        return EFCAMDATCSVSupportSummary(
            path=path,
            row_count=0,
            chunk_count=0,
            fieldnames=(),
            rows_with_text_change_markup=0,
            rows_with_support_field_change_markup=0,
            unique_writing_id_count=None,
        )
    row_count = 0
    chunk_count = 0
    rows_with_text_change_markup = 0
    rows_with_support_field_change_markup = 0
    writing_ids: set[str] | None = set() if track_unique_writing_ids else None
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        for row in reader:
            row_count += 1
            if (row_count - 1) % chunk_size == 0:
                chunk_count += 1
            if writing_ids is not None and row.get("writingID"):
                writing_ids.add(str(row["writingID"]))
            if "<change>" in (row.get("text") or ""):
                rows_with_text_change_markup += 1
            support_blob = "".join(row.get(field) or "" for field in ("original", "corrected", "POS"))
            if "<change>" in support_blob:
                rows_with_support_field_change_markup += 1
    return EFCAMDATCSVSupportSummary(
        path=path,
        row_count=row_count,
        chunk_count=chunk_count,
        fieldnames=fieldnames,
        rows_with_text_change_markup=rows_with_text_change_markup,
        rows_with_support_field_change_markup=rows_with_support_field_change_markup,
        unique_writing_id_count=len(writing_ids) if writing_ids is not None else None,
    )


def _parse_writing_element(
    element: ET.Element,
    *,
    source_path: Path,
    start_line_number: int,
    parser_notes: tuple[str, ...],
) -> EFCAMDATWritingBlock:
    writing_id = _required_attr(element, "id")
    level = element.attrib.get("level", "")
    unit = element.attrib.get("unit", "")
    learner = element.find("learner")
    topic = element.find("topic")
    grade = _clean_optional(element.findtext("grade"))
    text_element = element.find("text")
    text_value = "".join(text_element.itertext()) if text_element is not None else ""
    text_fingerprint, text_length = fingerprint_text(text_value)
    changes = list(text_element.iter("change")) if text_element is not None else []
    source_record = _build_source_record(
        writing_id=writing_id,
        level=level,
        unit=unit,
        learner_id=learner.attrib.get("id", "") if learner is not None else "",
        learner_nationality=learner.attrib.get("nationality", "") if learner is not None else "",
        topic_id=topic.attrib.get("id", "") if topic is not None else "",
        grade=grade,
        text_fingerprint=text_fingerprint,
        text_length=text_length,
        change_count=len(changes),
        source_path=source_path,
        start_line_number=start_line_number,
        parser_status="xml",
        parser_notes=parser_notes,
    )
    errors = tuple(
        _build_error_instance_from_element(
            change,
            writing_id=writing_id,
            source_record=source_record,
            source_path=source_path,
            change_index=index,
            parser_status="xml",
            parser_notes=parser_notes,
        )
        for index, change in enumerate(changes, start=1)
    )
    return EFCAMDATWritingBlock(
        source_record=source_record,
        error_instances=errors,
        parser_status="xml",
        parser_notes=parser_notes,
    )


def _parse_writing_block_regex(
    raw_block: str,
    *,
    source_path: Path,
    start_line_number: int,
    parser_notes: tuple[str, ...],
) -> EFCAMDATWritingBlock:
    attrs = _match_groupdict(_WRITING_ATTR_RE, raw_block)
    learner_attrs = _match_groupdict(_LEARNER_RE, raw_block)
    topic_attrs = _match_groupdict(_TOPIC_RE, raw_block)
    grade = _regex_text(_GRADE_RE, raw_block)
    text_markup = _regex_text(_TEXT_RE, raw_block)
    text_value = _strip_tags(text_markup)
    text_fingerprint, text_length = fingerprint_text(text_value)
    changes = [match.group("change") for match in _CHANGE_RE.finditer(text_markup)]
    source_record = _build_source_record(
        writing_id=attrs.get("id", f"unknown_line_{start_line_number}"),
        level=attrs.get("level", ""),
        unit=attrs.get("unit", ""),
        learner_id=learner_attrs.get("id", ""),
        learner_nationality=learner_attrs.get("nationality", ""),
        topic_id=topic_attrs.get("id", ""),
        grade=grade,
        text_fingerprint=text_fingerprint,
        text_length=text_length,
        change_count=len(changes),
        source_path=source_path,
        start_line_number=start_line_number,
        parser_status="regex_fallback",
        parser_notes=parser_notes,
    )
    errors = tuple(
        _build_error_instance_from_markup(
            change_markup,
            source_record=source_record,
            source_path=source_path,
            change_index=index,
            parser_notes=parser_notes,
        )
        for index, change_markup in enumerate(changes, start=1)
    )
    return EFCAMDATWritingBlock(
        source_record=source_record,
        error_instances=errors,
        parser_status="regex_fallback",
        parser_notes=parser_notes,
    )


def _build_source_record(
    *,
    writing_id: str,
    level: str,
    unit: str,
    learner_id: str,
    learner_nationality: str,
    topic_id: str,
    grade: str | None,
    text_fingerprint: str,
    text_length: int,
    change_count: int,
    source_path: Path,
    start_line_number: int,
    parser_status: str,
    parser_notes: tuple[str, ...],
) -> LearnerCorpusSourceRecord:
    source_record_id = make_source_record_id(
        source_key=SOURCE_KEY,
        native_record_id=writing_id,
    )
    learner_pseudonym = (
        f"sha256:{stable_hash({'source': SOURCE_KEY, 'learner_id': learner_id}, length=64)}"
        if learner_id
        else None
    )
    document_pseudonym = f"sha256:{stable_hash({'source': SOURCE_KEY, 'writing_id': writing_id}, length=64)}"
    return LearnerCorpusSourceRecord(
        source_record_id=source_record_id,
        source_key=SOURCE_KEY,
        native_record_id=writing_id,
        record_unit="writing",
        learner_id_pseudonym=learner_pseudonym,
        document_id_pseudonym=document_pseudonym,
        task_id=topic_id or None,
        proficiency_label=f"level:{level};unit:{unit}",
        source_path=str(source_path).replace("\\", "/"),
        text_fingerprint=text_fingerprint,
        text_length=text_length,
        metadata={
            "level": level,
            "unit": unit,
            "topic_id": topic_id or None,
            "grade_present": grade is not None,
            "grade": grade,
            "learner_nationality": learner_nationality or None,
            "change_count": change_count,
            "parser_status": parser_status,
            "xml_start_line_number": start_line_number,
        },
        provenance={
            "parser": "efcamdat_ingestion_v1",
            "xml_source_file": str(source_path).replace("\\", "/"),
            "annotation_source_of_truth": "xml_change_markup",
            "parser_notes": list(parser_notes),
        },
    )


def _build_error_instance_from_element(
    change: ET.Element,
    *,
    writing_id: str,
    source_record: LearnerCorpusSourceRecord,
    source_path: Path,
    change_index: int,
    parser_status: str,
    parser_notes: tuple[str, ...],
) -> ErrorInstance:
    selection = change.find("selection")
    symbol = change.find(".//symbol")
    correct = change.find(".//correct")
    selection_text = "".join(selection.itertext()) if selection is not None else ""
    symbol_text = _clean_optional("".join(symbol.itertext()) if symbol is not None else "") or "UNKNOWN"
    correct_text = "".join(correct.itertext()) if correct is not None else ""
    return _build_error_instance(
        source_record=source_record,
        source_path=source_path,
        writing_id=writing_id,
        change_index=change_index,
        selection_text=selection_text,
        symbol_text=symbol_text,
        correct_text=correct_text,
        parser_status=parser_status,
        parser_notes=parser_notes,
    )


def _build_error_instance_from_markup(
    change_markup: str,
    *,
    source_record: LearnerCorpusSourceRecord,
    source_path: Path,
    change_index: int,
    parser_notes: tuple[str, ...],
) -> ErrorInstance:
    selection_text = _strip_tags(_tag_value(change_markup, "selection"))
    symbol_text = _clean_optional(_strip_tags(_tag_value(change_markup, "symbol"))) or "UNKNOWN"
    correct_text = _strip_tags(_tag_value(change_markup, "correct"))
    return _build_error_instance(
        source_record=source_record,
        source_path=source_path,
        writing_id=source_record.native_record_id,
        change_index=change_index,
        selection_text=selection_text,
        symbol_text=symbol_text,
        correct_text=correct_text,
        parser_status="regex_fallback",
        parser_notes=parser_notes,
    )


def _build_error_instance(
    *,
    source_record: LearnerCorpusSourceRecord,
    source_path: Path,
    writing_id: str,
    change_index: int,
    selection_text: str,
    symbol_text: str,
    correct_text: str,
    parser_status: str,
    parser_notes: tuple[str, ...],
) -> ErrorInstance:
    selection_fingerprint, selection_length = fingerprint_text(selection_text)
    correction = _build_correction(selection_text, correct_text)
    native_error_id = f"{writing_id}:change{change_index}"
    span_payload = {
        "span_kind": "efcamdat_selection_text",
        "selection_fingerprint": selection_fingerprint,
        "selected_text_length": selection_length,
    }
    label_payload = {"label_system": "efcamdat_symbol", "label": symbol_text}
    error_id = make_error_instance_id(
        source_key=SOURCE_KEY,
        source_record_id=source_record.source_record_id,
        native_error_id=native_error_id,
        span_payload=span_payload,
        label_payload=label_payload,
    )
    notes = list(parser_notes)
    if symbol_text == "UNKNOWN":
        notes.append("missing_symbol_label")
    if parser_status == "regex_fallback":
        notes.append("parsed_from_regex_fallback")
    return ErrorInstance(
        error_instance_id=error_id,
        source_record_id=source_record.source_record_id,
        source_key=SOURCE_KEY,
        native_error_id=native_error_id,
        source_native_label=SourceNativeErrorLabel(
            label_system="efcamdat_symbol",
            label=symbol_text,
        ),
        span=TextSpan(
            span_kind="efcamdat_selection_text",
            source_field="text.change.selection",
            selection_fingerprint=selection_fingerprint,
            selected_text_length=selection_length,
            source_markup_path=f"/writing[@id='{writing_id}']/text/change[{change_index}]/selection",
            confidence=0.9 if parser_status == "regex_fallback" else 1.0,
        ),
        correction=correction,
        status="parsed",
        review_status="needs_review" if notes else "pending",
        parser_notes=notes,
        metadata={
            "change_index": change_index,
            "parser_status": parser_status,
            "label": symbol_text,
            "selection_length": selection_length,
            "correction_length": correction.correction_length,
        },
        provenance={
            "parser": "efcamdat_ingestion_v1",
            "xml_source_file": str(source_path).replace("\\", "/"),
            "annotation_source_of_truth": "xml_change_markup",
        },
    )


def _build_correction(selection_text: str, correct_text: str) -> ErrorCorrection:
    if correct_text:
        fingerprint, length = fingerprint_text(correct_text)
        correction_type = "insertion" if selection_text == "" else "replacement"
        return ErrorCorrection(
            correction_type=correction_type,
            correction_fingerprint=fingerprint,
            correction_length=length,
        )
    return ErrorCorrection(correction_type="deletion")


def _required_attr(element: ET.Element, attr: str) -> str:
    value = element.attrib.get(attr)
    if value is None or value == "":
        raise EFCAMDATParseError(f"Missing required writing attribute: {attr}")
    return value


def _tag_value(markup: str, tag: str) -> str:
    pattern = re.compile(_TAG_RE.pattern.format(tag=re.escape(tag)), re.DOTALL)
    match = pattern.search(markup)
    return html.unescape(match.group("value")) if match else ""


def _regex_text(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return html.unescape(match.group(next(iter(match.groupdict()))))


def _match_groupdict(pattern: re.Pattern[str], text: str) -> dict[str, str]:
    match = pattern.search(text)
    if not match:
        return {}
    return {key: html.unescape(value or "") for key, value in match.groupdict().items()}


def _strip_tags(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(_STRIP_TAGS_RE.sub("", value))


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
