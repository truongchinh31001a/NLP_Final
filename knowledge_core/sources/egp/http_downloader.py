from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

import httpx

from knowledge_core.sources.egp.downloader import failed_download_result
from knowledge_core.sources.egp.models import DownloadResult, EGPCategoryConfig, now_utc


class HttpEGPDownloader:
    """Direct HTTP downloader for an explicitly configured EGP export endpoint.

    The current EGP Online page generates XLSX files in the browser from Bubble
    app JSON. Use this class only when a stable export URL template has been
    confirmed for the running site or provided by a licensed data workflow.
    """

    def __init__(
        self,
        *,
        export_url_template: str | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.export_url_template = export_url_template or os.getenv(
            "EGP_EXPORT_URL_TEMPLATE",
        )
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": "adaptive-ai-english-tutor-egp-ingestion/1.0"},
        )

    def download_category(
        self,
        category: EGPCategoryConfig,
        destination: Path,
    ) -> DownloadResult:
        if not self.export_url_template:
            return failed_download_result(
                category=category,
                destination=destination,
                method=self.__class__.__name__,
                error=(
                    "No stable EGP export endpoint is configured. Set "
                    "EGP_EXPORT_URL_TEMPLATE or use BrowserEGPDownloader."
                ),
            )

        url = self._render_url(category)
        try:
            response = self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return failed_download_result(
                category=category,
                destination=destination,
                method=self.__class__.__name__,
                error=f"HTTP EGP download failed: {exc}",
                source_url=url,
            )

        content = response.content
        if not content:
            return failed_download_result(
                category=category,
                destination=destination,
                method=self.__class__.__name__,
                error="HTTP EGP download returned an empty body",
                source_url=url,
            )
        if not _looks_like_xlsx(content):
            return failed_download_result(
                category=category,
                destination=destination,
                method=self.__class__.__name__,
                error=(
                    "HTTP EGP download did not look like an XLSX file; "
                    "the endpoint may have returned HTML or JSON"
                ),
                source_url=url,
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return DownloadResult(
            category_id=category.id,
            destination=destination,
            status="downloaded",
            method=self.__class__.__name__,
            source_url=url,
            retrieved_at=now_utc(),
            bytes_written=len(content),
        )

    def _render_url(self, category: EGPCategoryConfig) -> str:
        return self.export_url_template.format(
            category_id=category.id,
            query=quote_plus(category.query),
            query_raw=category.query,
            level="ALL",
            expected_super_category=quote_plus(category.expected_super_category or ""),
            expected_sub_category=quote_plus(category.expected_sub_category or ""),
        )


def _looks_like_xlsx(content: bytes) -> bool:
    return content.startswith(b"PK")
