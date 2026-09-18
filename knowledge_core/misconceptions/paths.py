from __future__ import annotations

from pathlib import Path


DEFAULT_NORMALIZED_ERRORS_PATH = Path(
    "data/interim/corpus_errors/normalized_error_instances.jsonl",
)
DEFAULT_ERROR_SKILL_MAPPINGS_PATH = Path(
    "data/interim/corpus_errors/error_skill_mappings.jsonl",
)
DEFAULT_ERROR_NORMALIZATION_REPORT = Path(
    "data/reports/corpus_errors/error_normalization_report.json",
)
DEFAULT_SOURCE_RECORD_PATHS = {
    "clc_fce": Path("data/interim/clc_fce/source_records.jsonl"),
    "efcamdat": Path("data/interim/efcamdat/source_records.jsonl"),
}

DEFAULT_INTERIM_DIR = Path("data/interim/misconceptions")
DEFAULT_CURATED_DIR = Path("data/curated/misconceptions")
DEFAULT_REVIEW_DIR = Path("data/curated/review")
DEFAULT_REPORTS_DIR = Path("data/reports/misconceptions")

CANDIDATE_MISCONCEPTIONS_JSONL = "candidate_misconceptions.jsonl"
ACCEPTED_MISCONCEPTIONS_JSONL = "accepted_misconceptions.jsonl"
MISCONCEPTION_REVIEW_CSV = "misconception_review.csv"
MISCONCEPTION_REPORT_JSON = "misconception_report.json"
