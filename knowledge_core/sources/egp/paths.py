from __future__ import annotations

from pathlib import Path, PurePosixPath

from knowledge_core.sources.egp.models import EGPCategoryConfig


DEFAULT_RAW_GRAMMAR_DIR = Path("data/external/english_profile/Grammar")
DEFAULT_INTERIM_GRAMMAR_DIR = Path("data/interim/english_profile/grammar")
DEFAULT_EGP_REPORTS_DIR = Path("data/reports/egp")
DEFAULT_EGP_REVIEW_DIR = Path("data/curated/review")


def raw_file_path(raw_dir: str | Path, category: EGPCategoryConfig) -> Path:
    raw_path = Path(raw_dir)
    if category.raw_path:
        relative = PurePosixPath(category.raw_path)
        return raw_path.joinpath(*relative.parts)
    return raw_path / f"{category.id}.xlsx"
