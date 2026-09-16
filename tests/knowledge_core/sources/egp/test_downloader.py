from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import httpx

from knowledge_core.sources.egp.downloader import download_categories
from knowledge_core.sources.egp.http_downloader import HttpEGPDownloader
from knowledge_core.sources.egp.models import DownloadResult, EGPCategoryConfig, now_utc
from knowledge_core.sources.egp.paths import raw_file_path
from tests.egp_workbook_fixtures import xlsx_bytes


class EGPDownloaderTests(unittest.TestCase):
    def test_download_categories_skips_existing_files_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir)
            category = EGPCategoryConfig(
                id="present_simple",
                query="present simple",
                raw_path="Tenses/Present Simple/present_simple.xlsx",
            )
            destination = raw_file_path(raw_dir, category)
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"existing")
            downloader = FakeDownloader()

            results = download_categories(downloader, [category], raw_dir)

        self.assertEqual(results[0].status, "skipped")
        self.assertFalse(downloader.called)

    def test_download_categories_supports_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir) / "raw"
            category = EGPCategoryConfig(
                id="present_simple",
                query="present simple",
                raw_path="Tenses/Present Simple/present_simple.xlsx",
            )
            downloader = FakeDownloader()

            results = download_categories(
                downloader,
                [category],
                raw_dir,
                dry_run=True,
            )

            self.assertEqual(results[0].status, "dry_run")
            self.assertFalse(downloader.called)
            self.assertFalse(raw_dir.exists())

    def test_http_downloader_writes_xlsx_and_metadata(self) -> None:
        rows = [["Level", "Can-DoStatement"], ["A1", "Can use present simple."]]
        content = xlsx_bytes(rows)
        requested_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested_urls.append(str(request.url))
            return httpx.Response(
                200,
                content=content,
                headers={
                    "content-type": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        downloader = HttpEGPDownloader(
            export_url_template="https://example.test/export?query={query}&level={level}",
            client=client,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir)
            category = EGPCategoryConfig(
                id="present_simple",
                query="present simple",
                raw_path="Tenses/Present Simple/present_simple.xlsx",
            )
            results = download_categories(
                downloader,
                [category],
                raw_dir,
                force=True,
            )
            destination = raw_dir / "Tenses" / "Present Simple" / "present_simple.xlsx"
            metadata = Path(temp_dir) / "present_simple.metadata.json"

            self.assertEqual(results[0].status, "downloaded")
            self.assertTrue(destination.exists())
            self.assertEqual(destination.read_bytes(), content)
            self.assertTrue(destination.with_suffix(".metadata.json").exists())
            self.assertFalse(metadata.exists())

        self.assertEqual(
            requested_urls,
            ["https://example.test/export?query=present+simple&level=ALL"],
        )


class FakeDownloader:
    def __init__(self) -> None:
        self.called = False

    def download_category(
        self,
        category: EGPCategoryConfig,
        destination: Path,
    ) -> DownloadResult:
        self.called = True
        destination.write_bytes(b"downloaded")
        return DownloadResult(
            category_id=category.id,
            destination=destination,
            status="downloaded",
            method="FakeDownloader",
            retrieved_at=now_utc(),
            bytes_written=destination.stat().st_size,
        )


if __name__ == "__main__":
    unittest.main()
