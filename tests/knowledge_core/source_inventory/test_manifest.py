from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.source_inventory.manifest import build_source_manifest


class SourceManifestTests(unittest.TestCase):
    def test_promotes_only_source_root_files_and_preserves_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = []
            governance_sources = []
            file_rows = []
            for index, key in enumerate(sorted({
                "efcamdat", "clc_fce", "write_improve", "ud_english_ewt",
                "english_grammar_profile", "cefr_companion_volume_2020",
            })):
                source_root = f"data/raw/{key}"
                sources.append({
                    "source_key": key, "source_name": key, "required_for_v1": index < 4,
                    "source_role": ["fixture"], "root_path": source_root,
                    "detected_version": "unknown" if index == 0 else "v1",
                    "publication_year": "unknown", "redistribution_notes": [],
                })
                governance_sources.append({
                    "source_key": key, "license_status": "needs_manual_review",
                    "official_source_urls": [],
                })
                file_rows.append({
                    "source_key": key, "relative_path": f"{source_root}/source.txt",
                    "source_relative_path": "source.txt", "size_bytes": 10,
                    "extension": ".txt", "checksum_status": "sha256",
                    "checksum_sha256": str(index) * 64,
                })
                file_rows.append({
                    "source_key": key, "relative_path": f"data/interim/{key}/derived.jsonl",
                    "source_relative_path": "derived.jsonl", "size_bytes": 20,
                    "extension": ".jsonl", "checksum_status": "sha256",
                    "checksum_sha256": "f" * 64,
                })
            inventory = root / "inventory.json"
            files = root / "files.jsonl"
            governance = root / "governance.json"
            output = root / "manifest.json"
            file_output = root / "manifest_files.jsonl"
            inventory.write_text(json.dumps({"generated_at": "fixture", "sources": sources}), encoding="utf-8")
            governance.write_text(json.dumps({"sources": governance_sources}), encoding="utf-8")
            files.write_text("".join(json.dumps(item) + "\n" for item in file_rows), encoding="utf-8")

            result = build_source_manifest(
                inventory_path=inventory,
                file_inventory_path=files,
                governance_path=governance,
                output_path=output,
                file_output_path=file_output,
            )

            self.assertTrue(result["validation"]["passed"])
            self.assertEqual(result["source_count"], 6)
            self.assertEqual(result["file_count"], 6)
            self.assertIsNone(result["sources"][0]["detected_version"])
            self.assertEqual(result["sources"][0]["version_status"], "unavailable")
            self.assertEqual(len(file_output.read_text(encoding="utf-8").splitlines()), 6)

    def test_invalid_checksum_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / "inventory.json"
            files = root / "files.jsonl"
            governance = root / "governance.json"
            source_keys = sorted({
                "efcamdat", "clc_fce", "write_improve", "ud_english_ewt",
                "english_grammar_profile", "cefr_companion_volume_2020",
            })
            inventory.write_text(json.dumps({"sources": [{
                "source_key": key, "root_path": f"raw/{key}", "detected_version": "v1",
                "publication_year": "2020", "required_for_v1": True,
            } for key in source_keys]}), encoding="utf-8")
            governance.write_text(json.dumps({"sources": []}), encoding="utf-8")
            files.write_text("".join(json.dumps({
                "source_key": key, "relative_path": f"raw/{key}/file",
                "source_relative_path": "file", "size_bytes": 1, "extension": "",
                "checksum_status": "sha256", "checksum_sha256": "bad",
            }) + "\n" for key in source_keys), encoding="utf-8")

            result = build_source_manifest(
                inventory_path=inventory, file_inventory_path=files,
                governance_path=governance, output_path=root / "out.json",
                file_output_path=root / "out.jsonl",
            )
            self.assertFalse(result["validation"]["passed"])
            self.assertEqual(result["validation"]["error_count"], 6)


if __name__ == "__main__":
    unittest.main()
