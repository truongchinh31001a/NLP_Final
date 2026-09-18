from __future__ import annotations

from pathlib import Path


DEFAULT_ASSESSMENT_CRITERIA_PATH = Path(
    "data/curated/assessment/grammar_assessment_criteria.jsonl",
)
DEFAULT_ASSESSMENT_PROFILES_PATH = Path(
    "data/curated/assessment/grammar_assessment_profiles.jsonl",
)
DEFAULT_ACCEPTED_MISCONCEPTIONS_PATH = Path(
    "data/curated/misconceptions/accepted_misconceptions.jsonl",
)
DEFAULT_CANDIDATE_MISCONCEPTIONS_PATH = Path(
    "data/interim/misconceptions/candidate_misconceptions.jsonl",
)

DEFAULT_CURATED_DIR = Path("data/curated/knowledge_enrichment")
DEFAULT_REVIEW_DIR = Path("data/curated/review")
DEFAULT_REPORTS_DIR = Path("data/reports/knowledge_enrichment")

DEFAULT_REVIEW_STATUS_REPORTS = {
    "egp": Path("data/reports/egp/mapping_report.json"),
    "cefr": Path("data/reports/knowledge_alignment/cefr_egp_alignment_report.json"),
    "relationships": Path("data/reports/relationships/grammar_relationship_report.json"),
    "assessment": Path("data/reports/assessment/grammar_assessment_report.json"),
    "errors": Path("data/reports/corpus_errors/error_normalization_report.json"),
    "misconceptions": Path("data/reports/misconceptions/misconception_report.json"),
}

ASSESSMENT_CRITERIA_ENRICHED_JSONL = "grammar_assessment_criteria_enriched.jsonl"
SKILL_PROFILES_ENRICHED_JSONL = "grammar_skill_profiles_enriched.jsonl"
SKILL_MISCONCEPTION_LINKS_JSONL = "skill_misconception_links.jsonl"
KNOWLEDGE_ENRICHMENT_REVIEW_CSV = "knowledge_enrichment_review.csv"
KNOWLEDGE_ENRICHMENT_REPORT_JSON = "knowledge_enrichment_report.json"

