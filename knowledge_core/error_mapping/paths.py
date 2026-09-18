from pathlib import Path


DEFAULT_MAPPINGS_PATH = Path("data/interim/corpus_errors/error_skill_mappings.jsonl")
DEFAULT_NORMALIZED_ERRORS_PATH = Path(
    "data/interim/corpus_errors/normalized_error_instances.jsonl",
)
DEFAULT_ERROR_INSTANCE_PATHS = {
    "clc_fce": Path("data/interim/clc_fce/error_instances.jsonl"),
    "efcamdat": Path("data/interim/efcamdat/error_instances.jsonl"),
}
DEFAULT_MISCONCEPTIONS_PATH = Path(
    "data/interim/misconceptions/candidate_misconceptions.jsonl",
)
DEFAULT_MISCONCEPTION_REPORT_PATH = Path(
    "data/reports/misconceptions/misconception_report.json",
)
DEFAULT_MISCONCEPTION_REVIEW_PATH = Path(
    "data/curated/review/misconception_review.csv",
)
DEFAULT_ERROR_REPORT_PATH = Path("data/reports/corpus_errors/error_normalization_report.json")
DEFAULT_REVIEW_DIR = Path("data/curated/review")
DEFAULT_CURATED_DIR = Path("data/curated/error_mapping")
DEFAULT_REPORT_PATH = Path(
    "data/reports/corpus_errors/error_mapping_human_review_report.json",
)

REVIEW_FILE = "error_skill_mapping_review.csv"
LEGACY_REVIEW_FILE = "error_normalization_label_review.csv"
GROUPS_FILE = "error_skill_mapping_review_groups.csv"
DECISIONS_FILE = "error_skill_mapping_review_decisions.csv"
GROUP_DECISIONS_FILE = "review_group_decision.csv"
ACCEPTED_FILE = "accepted_error_skill_mappings.jsonl"
REJECTED_FILE = "rejected_error_skill_mappings.jsonl"
UNRESOLVED_FILE = "unresolved_error_skill_mappings.jsonl"
MISCONCEPTION_EVIDENCE_BASELINE_FILE = "misconception_evidence_baseline.jsonl"
