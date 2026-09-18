from __future__ import annotations

from pathlib import Path


DEFAULT_INPUT_PATHS = {
    "clc_fce": Path("data/interim/clc_fce/error_instances.jsonl"),
    "efcamdat": Path("data/interim/efcamdat/error_instances.jsonl"),
}

DEFAULT_INTERIM_DIR = Path("data/interim/corpus_errors")
DEFAULT_REPORTS_DIR = Path("data/reports/corpus_errors")
DEFAULT_REVIEW_DIR = Path("data/curated/review")

NORMALIZED_ERRORS_JSONL = "normalized_error_instances.jsonl"
ERROR_SKILL_MAPPINGS_JSONL = "error_skill_mappings.jsonl"
REVIEW_CSV = "error_skill_mapping_review.csv"
REPORT_JSON = "error_normalization_report.json"
