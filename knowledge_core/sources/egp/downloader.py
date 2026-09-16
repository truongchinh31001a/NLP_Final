from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Protocol, Sequence

from knowledge_core.sources.egp.models import (
    DownloadResult,
    EGPCategoryConfig,
    now_utc,
)
from knowledge_core.sources.egp.paths import DEFAULT_RAW_GRAMMAR_DIR, raw_file_path


logger = logging.getLogger(__name__)


class EGPDownloadError(RuntimeError):
    """Raised when a category cannot be downloaded."""


class EGPDownloader(Protocol):
    def download_category(
        self,
        category: EGPCategoryConfig,
        destination: Path,
    ) -> DownloadResult:
        ...


def download_categories(
    downloader: EGPDownloader,
    categories: Sequence[EGPCategoryConfig],
    raw_dir: str | Path = DEFAULT_RAW_GRAMMAR_DIR,
    *,
    force: bool = False,
    dry_run: bool = False,
    delay_seconds: float = 0.0,
) -> list[DownloadResult]:
    raw_path = Path(raw_dir)
    results: list[DownloadResult] = []

    for category in categories:
        destination = raw_file_path(raw_path, category)
        if destination.exists() and not force:
            logger.info("Skipping existing EGP raw file: %s", destination)
            results.append(
                DownloadResult(
                    category_id=category.id,
                    destination=destination,
                    status="skipped",
                    method=downloader.__class__.__name__,
                    bytes_written=destination.stat().st_size,
                ),
            )
            continue

        if dry_run:
            results.append(
                DownloadResult(
                    category_id=category.id,
                    destination=destination,
                    status="dry_run",
                    method=downloader.__class__.__name__,
                ),
            )
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        result = downloader.download_category(category, destination)
        results.append(result)
        if result.status == "downloaded":
            write_download_metadata(result)

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return results


def write_download_metadata(result: DownloadResult) -> Path:
    metadata_path = result.destination.with_suffix(".metadata.json")
    payload = {
        "category_id": result.category_id,
        "source_url": result.source_url,
        "retrieved_at": result.retrieved_at.isoformat(),
        "method": result.method,
        "bytes_written": result.bytes_written,
    }
    metadata_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return metadata_path


def failed_download_result(
    *,
    category: EGPCategoryConfig,
    destination: Path,
    method: str,
    error: str,
    source_url: str | None = None,
) -> DownloadResult:
    return DownloadResult(
        category_id=category.id,
        destination=destination,
        status="failed",
        method=method,
        source_url=source_url,
        retrieved_at=now_utc(),
        error=error,
    )
