from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from knowledge_core.sources.cefr.models import CEFRExtractionIssue, VALID_CEFR_LEVELS
from knowledge_core.sources.cefr.normalizer import (
    normalize_cefr_level,
    normalize_table_title,
    normalize_whitespace,
)


LEVEL_PATTERN = re.compile(r"^(Pre-A1|A1|A2|A2\+|B1|B1\+|B2|B2\+|C1|C2)$")
NO_DESCRIPTOR_PATTERN = re.compile(
    r"^No descriptors available(?:[;:]?\s*see\s+(Pre-A1|A1|A2|A2\+|B1|B1\+|B2|B2\+|C1|C2))?$",
    re.IGNORECASE,
)
DESCRIPTOR_START_PATTERN = re.compile(
    r"^(Can|Has|Uses|Shows|Maintains|Consistently|Communicates|Good|Lexical|"
    r"Writing|Layout|Spelling|No descriptors available)\b",
)
INLINE_DESCRIPTOR_SPLIT_PATTERN = re.compile(
    r"(?<=[.!?])\s+(?=(?:Can|Has|Uses|Shows|Maintains|Consistently|"
    r"Communicates|Good|Lexical|Writing|Layout|Spelling|"
    r"No descriptors available)\b)",
)


@dataclass(slots=True)
class ParsedDescriptor:
    cefr_level: str
    descriptor_text: str
    descriptor_available: bool
    reference_level: str | None
    row_index: int
    descriptor_index: int
    raw_level_cell: str | None
    raw_descriptor_cell: str | None
    raw_row: list[Any]


def first_table_title(table: Sequence[Sequence[Any]]) -> str:
    if not table:
        return ""
    first_row = table[0]
    for cell in first_row:
        title = normalize_whitespace(cell)
        if title:
            return title
    return ""


def parse_descriptor_table_rows(
    table: Sequence[Sequence[Any]],
    *,
    page_number: int,
    scale_name: str,
    source_table: str,
) -> tuple[list[ParsedDescriptor], list[CEFRExtractionIssue]]:
    descriptors: list[ParsedDescriptor] = []
    issues: list[CEFRExtractionIssue] = []
    current_level: str | None = None

    for row_index, row in enumerate(table[1:], start=1):
        if len(row) < 2:
            issues.append(
                CEFRExtractionIssue(
                    severity="warning",
                    code="short_table_row",
                    message="Descriptor table row has fewer than two cells",
                    page_number=page_number,
                    scale_name=scale_name,
                    source_table=source_table,
                    row_index=row_index,
                    raw_payload={"raw_row": list(row)},
                ),
            )
            continue

        raw_level_cell = normalize_whitespace(row[0])
        raw_descriptor_cell = str(row[1]) if row[1] is not None else ""
        descriptor_cell = normalize_whitespace(raw_descriptor_cell)
        if not raw_level_cell and not descriptor_cell:
            continue

        if raw_level_cell:
            current_level = normalize_cefr_level(raw_level_cell)
            if current_level not in VALID_CEFR_LEVELS:
                issues.append(
                    CEFRExtractionIssue(
                        severity="error",
                        code="invalid_cefr_level",
                        message=f"Invalid CEFR level cell: {raw_level_cell!r}",
                        page_number=page_number,
                        scale_name=scale_name,
                        source_table=source_table,
                        row_index=row_index,
                        raw_payload={"raw_row": list(row)},
                    ),
                )
                continue

        if current_level is None:
            issues.append(
                CEFRExtractionIssue(
                    severity="error",
                    code="descriptor_without_level",
                    message="Descriptor row has no level and no preceding level to inherit",
                    page_number=page_number,
                    scale_name=scale_name,
                    source_table=source_table,
                    row_index=row_index,
                    raw_payload={"raw_row": list(row)},
                ),
            )
            continue

        split_descriptors = split_descriptor_cell(raw_descriptor_cell)
        if not split_descriptors:
            issues.append(
                CEFRExtractionIssue(
                    severity="error",
                    code="empty_descriptor_cell",
                    message="Descriptor row has no descriptor text",
                    page_number=page_number,
                    scale_name=scale_name,
                    source_table=source_table,
                    row_index=row_index,
                    raw_payload={"raw_row": list(row)},
                ),
            )
            continue

        for descriptor_index, descriptor_text in enumerate(split_descriptors, start=1):
            descriptor_available, reference_level = descriptor_availability(
                descriptor_text,
            )
            descriptors.append(
                ParsedDescriptor(
                    cefr_level=current_level,
                    descriptor_text=descriptor_text,
                    descriptor_available=descriptor_available,
                    reference_level=reference_level,
                    row_index=row_index,
                    descriptor_index=descriptor_index,
                    raw_level_cell=raw_level_cell or None,
                    raw_descriptor_cell=raw_descriptor_cell or None,
                    raw_row=list(row),
                ),
            )

    return descriptors, issues


def split_descriptor_cell(value: Any) -> list[str]:
    statements: list[str] = []
    current = ""
    for raw_line in str(value or "").splitlines():
        line = normalize_whitespace(raw_line)
        if not line:
            continue
        starts_new = bool(DESCRIPTOR_START_PATTERN.match(line))
        if starts_new and current and _ends_sentence(current):
            statements.append(current)
            current = line
        else:
            current = f"{current} {line}".strip() if current else line
    if current:
        statements.append(current)

    split_statements: list[str] = []
    for statement in statements:
        split_statements.extend(
            part.strip()
            for part in INLINE_DESCRIPTOR_SPLIT_PATTERN.split(statement)
            if part.strip()
        )
    return split_statements


def descriptor_availability(descriptor_text: str) -> tuple[bool, str | None]:
    match = NO_DESCRIPTOR_PATTERN.match(descriptor_text.strip())
    if match is None:
        return True, None
    reference_level = normalize_cefr_level(match.group(1)) if match.group(1) else None
    return False, reference_level or None


def descriptor_is_table_like(descriptor_text: str, *, descriptor_available: bool) -> bool:
    if not descriptor_text.strip():
        return False
    if not descriptor_available:
        return True
    return bool(DESCRIPTOR_START_PATTERN.match(descriptor_text.strip()))


def title_key(value: Any) -> str:
    return normalize_table_title(value)


def _ends_sentence(value: str) -> bool:
    return bool(re.search(r"[.!?]$", value.strip()))

