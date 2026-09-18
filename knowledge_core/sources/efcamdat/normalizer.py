from __future__ import annotations

from pathlib import Path

from knowledge_core.sources.efcamdat.models import EFCAMDATWritingBlock
from knowledge_core.sources.efcamdat.parser import parse_writing_block


def normalize_writing_block(
    raw_block: str,
    *,
    source_path: Path,
    start_line_number: int = 1,
) -> EFCAMDATWritingBlock:
    """Normalize one EFCAMDAT writing block into common source/error schema."""
    return parse_writing_block(
        raw_block,
        source_path=source_path,
        start_line_number=start_line_number,
    )

