from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from knowledge_core.source_inventory.inventory import (
    build_file_inventory,
    classify_raw_root,
    discover_sources,
    inspect_archive,
    inspect_conllu_files,
    inspect_sources,
    snapshot_files,
)


class SourceInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        create_fixture_workspace(self.workspace)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_source_discovery_maps_expected_roots_and_unknown_raw(self) -> None:
        discovery = discover_sources(self.workspace)

        self.assertEqual(discovery["sources"]["efcamdat"]["status"], "discovered")
        self.assertEqual(discovery["sources"]["clc_fce"]["status"], "discovered")
        self.assertEqual(discovery["sources"]["write_improve"]["status"], "discovered")
        self.assertEqual(discovery["sources"]["ud_english_ewt"]["status"], "discovered")
        self.assertEqual(discovery["unknown_raw_roots"], [])
        self.assertEqual(discovery["classified_raw_roots"][0]["source_key"], "excluded_raw_dataset")
        self.assertEqual(
            discovery["classified_raw_roots"][0]["status"],
            "unrelated_to_knowledge_core_v1",
        )
        self.assertEqual(classify_raw_root(Path("_fce-released-dataset-1.1")), "clc_fce")

    def test_file_inventory_counts_extensions_and_archives(self) -> None:
        discovery = discover_sources(self.workspace)
        rows = build_file_inventory(self.workspace, discovery, checksum_threshold=1024)
        extensions = {
            row["extension"]
            for row in rows
            if row["source_key"] == "write_improve"
        }

        self.assertIn(".tsv", extensions)
        self.assertIn(".m2", extensions)
        self.assertTrue(any(row["source_key"] == "excluded_raw_dataset" for row in rows))
        self.assertTrue(any(row["extension"] == ".zip" for row in rows))

    def test_archive_inspection_lists_members_without_extracting(self) -> None:
        archive_path = self.workspace / "data" / "raw" / "EFCAMDAT" / "sample.zip"
        inspection = inspect_archive(archive_path)

        self.assertEqual(inspection["archive_format"], "zip")
        self.assertEqual(inspection["member_count"], 1)
        self.assertEqual(inspection["representative_members"], ["inside.txt"])
        self.assertFalse((archive_path.parent / "inside.txt").exists())

    def test_conllu_inspection_detects_core_inventories(self) -> None:
        path = (
            self.workspace
            / "data"
            / "raw"
            / "UD_English-EWT-master"
            / "UD_English-EWT-master"
            / "en_ewt-ud-train.conllu"
        )
        result = inspect_conllu_files([path])

        self.assertEqual(result["sentence_counts"]["train"]["count"], 1)
        self.assertEqual(result["token_counts"]["train"]["count"], 1)
        self.assertIn("NOUN", result["upos_values"])
        self.assertIn("Number", result["feats_keys"])
        self.assertIn("SpaceAfter", result["misc_keys"])

    def test_full_inventory_serializes_reports_and_preserves_raw_files(self) -> None:
        before = snapshot_files(self.workspace / "data" / "raw")

        result = inspect_sources(self.workspace)

        after = snapshot_files(self.workspace / "data" / "raw")
        self.assertEqual(before, after)
        self.assertTrue(result["raw_data_unchanged"])
        report_dir = self.workspace / "data" / "reports" / "source_inventory"
        self.assertTrue((report_dir / "source_inventory.json").exists())
        self.assertTrue((report_dir / "file_inventory.jsonl").exists())
        self.assertTrue((report_dir / "schema_samples" / "ud_ewt_schema_sample.json").exists())

        inventory = json.loads((report_dir / "source_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory["sources"]), 6)
        required = {
            entry["source_key"]
            for entry in inventory["sources"]
            if entry["required_for_v1"]
        }
        optional = {
            entry["source_key"]
            for entry in inventory["sources"]
            if entry["optional_enrichment"]
        }
        self.assertEqual(
            required,
            {
                "efcamdat",
                "clc_fce",
                "english_grammar_profile",
                "cefr_companion_volume_2020",
            },
        )
        self.assertEqual(optional, {"write_improve", "ud_english_ewt"})
        self.assertTrue(inventory["validation"]["checks"]["all_raw_files_assigned_or_classified"])
        self.assertEqual(inventory["classified_raw_datasets"][0]["source_key"], "excluded_raw_dataset")

        efcamdat = json.loads((report_dir / "efcamdat_inspection.json").read_text(encoding="utf-8"))
        self.assertFalse(efcamdat["csv_has_standalone_error_labels"])
        self.assertEqual(efcamdat["csv_embedded_label_field"], "text")
        self.assertEqual(efcamdat["annotation_source_of_truth"]["source"], "xml_change_markup")

    def test_missing_source_handling_reports_blocked_readiness(self) -> None:
        missing_workspace = self.workspace / "missing"
        (missing_workspace / "data" / "raw").mkdir(parents=True)

        result = inspect_sources(missing_workspace)

        self.assertFalse(result["validation"]["passed"])
        issues = json.loads(
            (
                missing_workspace
                / "data"
                / "reports"
                / "source_inventory"
                / "inspection_issues.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertGreaterEqual(issues["validation"]["error_count"], 6)

    def test_unknown_directory_handling_keeps_manual_review_context(self) -> None:
        workspace = self.workspace
        raw = workspace / "data" / "raw" / "MysteryRaw"
        raw.mkdir(parents=True)
        raw.joinpath("sample.bin").write_bytes(b"mystery")

        result = inspect_sources(workspace)

        self.assertTrue(result["validation"]["passed"])
        issues = json.loads(
            (
                workspace
                / "data"
                / "reports"
                / "source_inventory"
                / "inspection_issues.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(issues["unknown_raw_roots"], ["data/raw/MysteryRaw"])
        self.assertEqual(issues["unknown_raw_file_count"], 1)
        self.assertEqual(issues["validation"]["warning_count"], 1)


def create_fixture_workspace(workspace: Path) -> None:
    create_efcamdat_fixture(workspace)
    create_clc_fixture(workspace)
    create_write_improve_fixture(workspace)
    create_ud_fixture(workspace)
    create_egp_fixture(workspace)
    create_cefr_fixture(workspace)
    dataset = workspace / "data" / "raw" / "Dataset" / "VNHSGE-E" / "JSON format" / "eval" / "English"
    dataset.mkdir(parents=True)
    (dataset / "MET_Eng_IE_2019.json").write_text(
        json.dumps(
            [
                {
                    "ID": "1",
                    "Question": "masked",
                    "Choice": [],
                    "Explanation": "masked",
                    "Image_Question": "",
                    "Image_Answer": "",
                },
            ],
        ),
        encoding="utf-8",
    )


def create_efcamdat_fixture(workspace: Path) -> None:
    root = workspace / "data" / "raw" / "EFCAMDAT"
    error_dir = root / "Cleaned_Error-coded_Subcorpus sample"
    clean_dir = root / "Cleaned_Subcorpus sample"
    error_dir.mkdir(parents=True)
    clean_dir.mkdir(parents=True)
    (root / "README.txt").write_text("fixture readme\n", encoding="utf-8")
    (root / "EFCamDat-User-Agreement-2023.pdf").write_bytes(b"%PDF-1.4\n")
    (root / "EFCAMDAT_Database.xml").write_text(
        """
        <selection id="s1">
          <meta><title>EFCAMDAT</title><version>fixture</version><date>2024</date></meta>
          <writings>
            <writing id="w1" level="1" unit="2">
              <learner id="l1" nationality="masked"/>
              <topic id="t1"/>
              <grade>1</grade>
              <text>
                <change><selection>token</selection><tag><symbol>AGV</symbol><correct>tokens</correct></tag></change>
              </text>
            </writing>
          </writings>
        </selection>
        """,
        encoding="utf-8",
    )
    (error_dir / "ef_POStagged_original_corrected.csv").write_text(
        ",writingID,level,unit,learnerID,nationality,topicID,topic,grade,text,lvno,prof,original,corrected,POS\n"
        "0,w1,1,2,l1,XX,t1,topic,1,masked,1,1,token,tokens,NN\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(root / "sample.zip", "w") as archive:
        archive.writestr("inside.txt", "inside")


def create_clc_fixture(workspace: Path) -> None:
    root = workspace / "data" / "raw" / "_fce-released-dataset-1.1"
    root.mkdir(parents=True)
    (root / "README").write_text(
        "Released for non-commercial research and educational purposes only.\n",
        encoding="utf-8",
    )
    record = {
        "id": "s1",
        "q": "1",
        "session": "2000",
        "l1": "masked",
        "age": "20",
        "combined-score": 30,
        "score": 15,
        "score-old-scale": "B",
        "text": "masked",
        "edits": [[0, 1, "masked", "M:DET"]],
    }
    (root / "train(oeistein.andersen@cambridge.org).json").write_text(
        json.dumps(record) + "\n",
        encoding="utf-8",
    )
    (root / "train(oeistein.andersen@cambridge.org).xml").write_text(
        '<scripts><script id="s1"><text><e type="M:DET"><i>x</i><c>y</c></e></text></script></scripts>',
        encoding="utf-8",
    )
    (root / "questions(oeistein.andersen@cambridge.org).json").write_text("{}\n", encoding="utf-8")
    (root / "questions(oeistein.andersen@cambridge.org).xml").write_text("<questions />", encoding="utf-8")


def create_write_improve_fixture(workspace: Path) -> None:
    root = workspace / "data" / "raw" / "write-and-improve-corpus-2024-v2"
    whole = root / "whole-corpus"
    m2_dir = root / "user-prompt-final-versions"
    whole.mkdir(parents=True)
    m2_dir.mkdir(parents=True)
    (root / "README").write_text("Write & Improve Corpus 2024 version 2\n", encoding="utf-8")
    (whole / "en-writeandimprove2024-corpus.tsv").write_text(
        "public_essay_id\tcreated_epoch\tcreated_timestamp\tpublic_prompt_id\tpublic_user_id\tuser_prompt\tessay_version_num\tis_first_version\tis_final_version\tlanguage\ttext\twi_suspecttokens\tautomarker_cefr_level\thumannotator_cefr_level\tsplit\n"
        "essay1\t1\t2024-01-01\tprompt1\tuser1\tuser1_prompt1\t1\tTRUE\tFALSE\tEnglish\tmasked\t\tB1\tB1\ttrain\n"
        "essay2\t2\t2024-01-02\tprompt1\tuser1\tuser1_prompt1\t2\tFALSE\tTRUE\tEnglish\tmasked\t\tB2\tB1\ttrain\n",
        encoding="utf-8",
    )
    (whole / "en-writeandimprove2024-prompts-info.tsv").write_text(
        "question_id\tpublic_prompt_id\tn.essay.sets\tn.essays\ttopic\tgenre\tmin_words\tmax_words\tprompt_level\tprompt\n"
        "q1\tprompt1\t1\t2\ttopic\tessay\t1\t10\tB1\tmasked\n",
        encoding="utf-8",
    )
    (m2_dir / "train.m2").write_text(
        "S masked sentence\nA 0 1|||M:DET|||the|||REQUIRED|||-NONE-|||0\n\n",
        encoding="utf-8",
    )


def create_ud_fixture(workspace: Path) -> None:
    root = workspace / "data" / "raw" / "UD_English-EWT-master" / "UD_English-EWT-master"
    root.mkdir(parents=True)
    (root / "README.md").write_text(
        "# Universal Dependencies English Web Treebank v2.18 -- 2026-05-15\n",
        encoding="utf-8",
    )
    (root / "LICENSE.txt").write_text("CC BY-SA 4.0\n", encoding="utf-8")
    content = (
        "# sent_id = fixture-1\n"
        "# text = masked\n"
        "1\tword\tword\tNOUN\tNN\tNumber=Sing\t0\troot\t0:root\tSpaceAfter=No\n\n"
    )
    for split in ("train", "dev", "test"):
        (root / f"en_ewt-ud-{split}.conllu").write_text(content, encoding="utf-8")


def create_egp_fixture(workspace: Path) -> None:
    (workspace / "data" / "external" / "english_profile" / "Grammar").mkdir(parents=True)
    (workspace / "data" / "external" / "english_profile" / "Grammar" / "sample.xlsx").write_bytes(b"xlsx")
    interim = workspace / "data" / "interim" / "english_profile" / "grammar"
    interim.mkdir(parents=True)
    interim.joinpath("egp_records.jsonl").write_text(
        json.dumps(
            {
                "source_record_id": "egp1",
                "cefr_level": "A2",
                "feature_type": "FORM",
                "super_category": "PRESENT",
            },
        )
        + "\n",
        encoding="utf-8",
    )
    reports = workspace / "data" / "reports" / "egp"
    reports.mkdir(parents=True)
    reports.joinpath("mapping_report.json").write_text(
        json.dumps({"mapping_counts": {"exact": 1}, "canonical_coverage": {"coverage_ratio": "1/1"}}),
        encoding="utf-8",
    )
    reports.joinpath("source_exclusion_report.json").write_text(
        json.dumps({"raw_records": 1, "included_v1_records": 1, "excluded_records": 0, "reason_counts": {}}),
        encoding="utf-8",
    )


def create_cefr_fixture(workspace: Path) -> None:
    external = workspace / "data" / "external" / "cefr"
    external.mkdir(parents=True)
    external.joinpath("CEFR Companion Volume_eng.pdf").write_bytes(b"%PDF-1.4\n")
    interim = workspace / "data" / "interim" / "cefr"
    interim.mkdir(parents=True)
    interim.joinpath("cefr_descriptors.jsonl").write_text(
        json.dumps({"source_record_id": "cefr1", "cefr_level": "B1"}) + "\n",
        encoding="utf-8",
    )
    interim.joinpath("cefr_learning_objective_candidates.jsonl").write_text(
        json.dumps({"objective_id": "obj1"}) + "\n",
        encoding="utf-8",
    )
    reports = workspace / "data" / "reports" / "cefr"
    reports.mkdir(parents=True)
    reports.joinpath("source_inspection_report.json").write_text(
        json.dumps(
            {
                "pdf": {"total_pages": 10, "tables_seen": 1},
                "configured_scales": [
                    {"scale_id": "grammatical_accuracy", "domain": "linguistic_competence"},
                ],
                "missing_scales": [],
            },
        ),
        encoding="utf-8",
    )
    reports.joinpath("extraction_report.json").write_text(
        json.dumps({"appendices": [], "extraction_issues": []}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
