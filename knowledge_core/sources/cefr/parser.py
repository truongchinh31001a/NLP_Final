from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from knowledge_core.sources.cefr.models import (
    CEFRConfig,
    CEFRDescriptorRecord,
    CEFRExtractionIssue,
    CEFRScaleConfig,
    SOURCE_NAME,
)
from knowledge_core.sources.cefr.normalizer import normalize_cefr_level, normalize_whitespace
from knowledge_core.sources.cefr.paths import DEFAULT_CEFR_PDF_PATH
from knowledge_core.sources.cefr.table_parser import (
    ParsedDescriptor,
    first_table_title,
    parse_descriptor_table_rows,
    title_key,
)


logger = logging.getLogger(__name__)


class CEFRParseError(ValueError):
    """Raised when the CEFR PDF cannot be parsed safely."""


@dataclass(slots=True)
class ParsedCEFRDataset:
    records: list[CEFRDescriptorRecord]
    issues: list[CEFRExtractionIssue] = field(default_factory=list)
    scale_hits: dict[str, list[int]] = field(default_factory=dict)
    pages_scanned: list[int] = field(default_factory=list)
    tables_seen: int = 0
    tables_matched: int = 0
    skipped_tables: list[dict[str, Any]] = field(default_factory=list)
    page_count: int = 0

    @property
    def no_descriptor_rows(self) -> list[CEFRDescriptorRecord]:
        return [record for record in self.records if not record.descriptor_available]

    @property
    def malformed_records(self) -> list[CEFRExtractionIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")


def parse_configured_pdf(
    config: CEFRConfig,
    pdf_path: str | Path | None = None,
    *,
    section: str | None = None,
    domain: str | None = None,
    level: str | None = None,
) -> ParsedCEFRDataset:
    source_file = Path(pdf_path or config.source.source_file or DEFAULT_CEFR_PDF_PATH)
    if not source_file.exists():
        raise CEFRParseError(f"CEFR PDF file does not exist: {source_file}")
    if source_file.stat().st_size == 0:
        raise CEFRParseError(f"CEFR PDF file is empty: {source_file}")

    try:
        import pdfplumber
    except ImportError as exc:
        raise CEFRParseError(
            "pdfplumber is required to parse the CEFR Companion Volume PDF",
        ) from exc

    selected_scales = config.select_scales(section=section, domain=domain)
    title_to_scale = {title_key(scale.name): scale for scale in selected_scales}
    selected_pages = _selected_pages(
        selected_scales,
        config=config,
        include_level_summaries=config.include_level_summaries(
            section=section,
            domain=domain,
        ),
    )
    normalized_level_filter = normalize_cefr_level(level) if level else None

    records: list[CEFRDescriptorRecord] = []
    issues: list[CEFRExtractionIssue] = []
    scale_hits: dict[str, set[int]] = defaultdict(set)
    skipped_tables: list[dict[str, Any]] = []
    pages_scanned: list[int] = []
    tables_seen = 0
    tables_matched = 0

    with pdfplumber.open(source_file) as pdf:
        page_count = len(pdf.pages)
        for page_number in selected_pages:
            if page_number < 1 or page_number > page_count:
                issues.append(
                    CEFRExtractionIssue(
                        severity="warning",
                        code="configured_page_out_of_range",
                        message=f"Configured page {page_number} is outside the PDF",
                        page_number=page_number,
                    ),
                )
                continue
            page = pdf.pages[page_number - 1]
            pages_scanned.append(page_number)
            tables = page.extract_tables() or []
            tables_seen += len(tables)
            for table_index, table in enumerate(tables, start=1):
                title = first_table_title(table)
                key = title_key(title)
                scale = title_to_scale.get(key)
                if scale is None:
                    skipped_tables.append(
                        {
                            "page_number": page_number,
                            "table_index": table_index,
                            "title": title,
                            "reason": "not_in_cefr_v1_scope",
                        },
                    )
                    continue
                if not _page_in_scale_range(page_number, scale):
                    skipped_tables.append(
                        {
                            "page_number": page_number,
                            "table_index": table_index,
                            "title": title,
                            "reason": "outside_configured_scale_page_range",
                            "scale_name": scale.id,
                        },
                    )
                    continue

                tables_matched += 1
                scale_hits[scale.id].add(page_number)
                parsed_descriptors, table_issues = parse_descriptor_table_rows(
                    table,
                    page_number=page_number,
                    scale_name=scale.id,
                    source_table=scale.name,
                )
                issues.extend(table_issues)
                for parsed in parsed_descriptors:
                    if (
                        normalized_level_filter
                        and parsed.cefr_level != normalized_level_filter
                    ):
                        continue
                    records.append(
                        build_descriptor_record(
                            parsed,
                            config=config,
                            scale=scale,
                            page_number=page_number,
                            table_index=table_index,
                            source_file=source_file,
                        ),
                    )

        if config.include_level_summaries(section=section, domain=domain):
            summary_records, summary_issues = _parse_appendix_level_summaries(
                pdf,
                config=config,
                source_file=source_file,
                level_filter=normalized_level_filter,
            )
            records.extend(summary_records)
            issues.extend(summary_issues)
            if summary_records:
                scale_hits["common_reference_levels"].update(
                    record.page_number
                    for record in summary_records
                    if record.page_number is not None
                )

    missing_scale_ids = sorted(
        scale.id for scale in selected_scales if scale.id not in scale_hits
    )
    for scale_id in missing_scale_ids:
        scale = next(scale for scale in selected_scales if scale.id == scale_id)
        issues.append(
            CEFRExtractionIssue(
                severity="error",
                code="configured_scale_not_found",
                message=f"Configured CEFR scale was not found in parsed tables: {scale.name}",
                scale_name=scale.id,
                source_table=scale.name,
            ),
        )

    return ParsedCEFRDataset(
        records=records,
        issues=issues,
        scale_hits={
            scale_id: sorted(page_numbers)
            for scale_id, page_numbers in sorted(scale_hits.items())
        },
        pages_scanned=sorted(set(pages_scanned)),
        tables_seen=tables_seen,
        tables_matched=tables_matched,
        skipped_tables=skipped_tables,
        page_count=page_count,
    )


def build_descriptor_record(
    parsed: ParsedDescriptor,
    *,
    config: CEFRConfig,
    scale: CEFRScaleConfig,
    page_number: int,
    table_index: int,
    source_file: Path,
) -> CEFRDescriptorRecord:
    raw_payload = {
        "pdf_page_number": page_number,
        "table_index": table_index,
        "row_index": parsed.row_index,
        "descriptor_index": parsed.descriptor_index,
        "raw_level_cell": parsed.raw_level_cell,
        "raw_descriptor_cell": parsed.raw_descriptor_cell,
        "raw_row": parsed.raw_row,
        "source_scale_name": scale.name,
    }
    descriptor_text = normalize_whitespace(parsed.descriptor_text)
    return CEFRDescriptorRecord(
        source=config.source.name,
        source_document=config.source.document,
        source_year=config.source.year,
        source_record_id=deterministic_source_record_id(
            source_document=config.source.document,
            page_number=page_number,
            scale_name=scale.id,
            cefr_level=parsed.cefr_level,
            descriptor_text=descriptor_text,
        ),
        chapter=scale.chapter,
        section=scale.section,
        domain=scale.domain or "",
        subdomain=scale.subdomain,
        scale_name=scale.id,
        descriptor_type=scale.descriptor_type or "communicative_activity",
        cefr_level=parsed.cefr_level,
        descriptor_text=descriptor_text,
        descriptor_available=parsed.descriptor_available,
        reference_level=parsed.reference_level,
        page_number=page_number,
        source_table=scale.name,
        is_pre_a1=parsed.cefr_level == "Pre-A1",
        source_file=str(source_file),
        raw_payload=raw_payload,
    )


def deterministic_source_record_id(
    *,
    source_document: str,
    page_number: int | None,
    scale_name: str,
    cefr_level: str,
    descriptor_text: str,
) -> str:
    parts = [
        source_document,
        str(page_number or ""),
        scale_name,
        cefr_level,
        normalize_whitespace(descriptor_text),
    ]
    raw_key = "\x1f".join(parts)
    return "cefr_" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _parse_appendix_level_summaries(
    pdf: Any,
    *,
    config: CEFRConfig,
    source_file: Path,
    level_filter: str | None,
) -> tuple[list[CEFRDescriptorRecord], list[CEFRExtractionIssue]]:
    appendix = config.appendix_by_id().get("appendix_1_salient_features")
    if appendix is None or not appendix.enabled:
        return [], []

    records: list[CEFRDescriptorRecord] = []
    issues: list[CEFRExtractionIssue] = []
    page_range = range(appendix.page_start, appendix.page_end + 1)
    user_category_by_level = config.chapter2.primary_levels
    for page_number in page_range:
        if page_number > len(pdf.pages):
            continue
        page = pdf.pages[page_number - 1]
        tables = page.extract_tables() or []
        for table_index, table in enumerate(tables, start=1):
            if not _looks_like_salient_features_table(table):
                continue
            current_user_category: str | None = None
            for row_index, row in enumerate(table, start=1):
                if len(row) < 3:
                    continue
                raw_category = normalize_whitespace(row[0])
                if raw_category:
                    current_user_category = _normalize_reversed_user_category(
                        raw_category,
                    )
                cefr_level = normalize_cefr_level(row[1])
                if cefr_level not in config.levels.include:
                    continue
                if level_filter and cefr_level != level_filter:
                    continue
                descriptor_text = normalize_whitespace(row[2])
                if not descriptor_text:
                    issues.append(
                        CEFRExtractionIssue(
                            severity="warning",
                            code="empty_level_summary_cell",
                            message="Appendix 1 level summary row has no text",
                            page_number=page_number,
                            scale_name="common_reference_levels",
                            source_table="Salient features of the CEFR levels",
                            row_index=row_index,
                            raw_payload={"raw_row": list(row)},
                        ),
                    )
                    continue
                broad_user_category = (
                    current_user_category
                    or user_category_by_level.get(cefr_level)
                    or "Unknown user"
                )
                raw_payload = {
                    "pdf_page_number": page_number,
                    "table_index": table_index,
                    "row_index": row_index,
                    "raw_user_category_cell": raw_category or None,
                    "broad_user_category": broad_user_category,
                    "chapter2_reference_section": config.chapter2.section,
                    "source_scale_name": "Common Reference Levels",
                }
                records.append(
                    CEFRDescriptorRecord(
                        source=config.source.name,
                        source_document=config.source.document,
                        source_year=config.source.year,
                        source_record_id=deterministic_source_record_id(
                            source_document=config.source.document,
                            page_number=page_number,
                            scale_name="common_reference_levels",
                            cefr_level=cefr_level,
                            descriptor_text=descriptor_text,
                        ),
                        chapter="Appendix 1",
                        section="Salient features of the CEFR levels",
                        domain="level_summary",
                        subdomain="common_reference_levels",
                        scale_name="common_reference_levels",
                        descriptor_type="level_summary",
                        cefr_level=cefr_level,
                        descriptor_text=descriptor_text,
                        descriptor_available=True,
                        reference_level=None,
                        page_number=page_number,
                        source_table="Salient features of the CEFR levels",
                        is_pre_a1=False,
                        source_file=str(source_file),
                        raw_payload=raw_payload,
                    ),
                )
    if not records:
        issues.append(
            CEFRExtractionIssue(
                severity="warning",
                code="appendix_1_level_summary_not_extracted",
                message="Appendix 1 level summary table was not extracted",
                scale_name="common_reference_levels",
                source_table="Salient features of the CEFR levels",
            ),
        )
    return records, issues


def _selected_pages(
    selected_scales: Sequence[CEFRScaleConfig],
    *,
    config: CEFRConfig,
    include_level_summaries: bool,
) -> list[int]:
    pages: set[int] = set()
    for scale in selected_scales:
        if scale.page_start is None or scale.page_end is None:
            continue
        pages.update(range(scale.page_start, scale.page_end + 1))
    if include_level_summaries:
        appendix = config.appendix_by_id().get("appendix_1_salient_features")
        if appendix is not None and appendix.enabled:
            pages.update(range(appendix.page_start, appendix.page_end + 1))
    return sorted(pages)


def _page_in_scale_range(page_number: int, scale: CEFRScaleConfig) -> bool:
    if scale.page_start is None or scale.page_end is None:
        return True
    return scale.page_start <= page_number <= scale.page_end


def _looks_like_salient_features_table(table: Sequence[Sequence[Any]]) -> bool:
    if len(table) < 6:
        return False
    levels = {normalize_cefr_level(row[1]) for row in table if len(row) > 1}
    return {"A1", "A2", "B1", "B2", "C1", "C2"}.issubset(levels)


def _normalize_reversed_user_category(value: str) -> str:
    text = value[::-1]
    normalized = " ".join(text.split())
    known = {"Basic user", "Independent user", "Proficient user"}
    if normalized in known:
        return normalized
    return value

