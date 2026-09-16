from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from knowledge_core.sources.cefr.models import CEFRConfig
from knowledge_core.sources.cefr.normalizer import normalize_table_title
from knowledge_core.sources.cefr.paths import DEFAULT_CEFR_PDF_PATH
from knowledge_core.sources.cefr.table_parser import first_table_title


class CEFRInspectionError(ValueError):
    """Raised when a CEFR source PDF cannot be inspected."""


def inspect_source_pdf(
    config: CEFRConfig,
    pdf_path: str | Path | None = None,
) -> dict[str, Any]:
    source_file = Path(pdf_path or config.source.source_file or DEFAULT_CEFR_PDF_PATH)
    if not source_file.exists():
        raise CEFRInspectionError(f"CEFR PDF file does not exist: {source_file}")

    try:
        import pdfplumber
    except ImportError as exc:
        raise CEFRInspectionError(
            "pdfplumber is required to inspect the CEFR Companion Volume PDF",
        ) from exc

    configured_scales = config.select_scales()
    title_to_scale = {
        normalize_table_title(scale.name): scale for scale in configured_scales
    }
    scale_pages: dict[str, set[int]] = defaultdict(set)
    table_titles_by_page: dict[int, list[str]] = defaultdict(list)
    tables_seen = 0

    with pdfplumber.open(source_file) as pdf:
        page_count = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            tables_seen += len(tables)
            for table in tables:
                title = first_table_title(table)
                if not title:
                    continue
                table_titles_by_page[page_number].append(title)
                scale = title_to_scale.get(normalize_table_title(title))
                if (
                    scale
                    and scale.page_start is not None
                    and scale.page_end is not None
                    and scale.page_start <= page_number <= scale.page_end
                ):
                    scale_pages[scale.id].add(page_number)

    missing_scales = [
        {"scale_id": scale.id, "source_table": scale.name}
        for scale in configured_scales
        if scale.id not in scale_pages
    ]
    return {
        "source": config.source.name,
        "source_document": config.source.document,
        "source_year": config.source.year,
        "source_file": str(source_file),
        "pdf": {
            "total_pages": page_count,
            "tables_seen": tables_seen,
        },
        "chapter2": {
            "section": config.chapter2.section,
            "page_start": config.chapter2.page_start,
            "page_end": config.chapter2.page_end,
            "primary_levels": config.chapter2.primary_levels,
            "documentation_only": config.chapter2.documentation_only,
        },
        "configured_scales": [
            {
                "scale_id": scale.id,
                "source_table": scale.name,
                "domain": scale.domain,
                "subdomain": scale.subdomain,
                "chapter": scale.chapter,
                "section": scale.section,
                "page_start": scale.page_start,
                "page_end": scale.page_end,
            }
            for scale in configured_scales
        ],
        "descriptor_scales_found": {
            scale_id: sorted(pages) for scale_id, pages in sorted(scale_pages.items())
        },
        "missing_scales": missing_scales,
        "appendices": [
            appendix.model_dump(mode="json") for appendix in config.appendices
        ],
        "table_titles_in_scope_pages": {
            str(page_number): titles
            for page_number, titles in sorted(table_titles_by_page.items())
            if _page_in_any_enabled_range(page_number, config)
        },
    }


def _page_in_any_enabled_range(page_number: int, config: CEFRConfig) -> bool:
    for section in config.sections.values():
        if section.enabled and section.page_start <= page_number <= section.page_end:
            return True
    for appendix in config.appendices:
        if appendix.enabled and appendix.page_start <= page_number <= appendix.page_end:
            return True
    return config.chapter2.page_start <= page_number <= config.chapter2.page_end
