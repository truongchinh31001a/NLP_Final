from __future__ import annotations

from pathlib import Path


SOURCE_KEY = "clc_fce"
SOURCE_NAME = "Cambridge Learner Corpus FCE"
DEFAULT_RAW_ROOT = Path("data/raw/_fce-released-dataset-1.1")
DEFAULT_INTERIM_DIR = Path("data/interim/clc_fce")
DEFAULT_REPORTS_DIR = Path("data/reports/clc_fce")
DEFAULT_REVIEW_DIR = Path("data/curated/review")
DEFAULT_SOURCE_INVENTORY_REPORT = Path("data/reports/source_inventory/clc_fce_inspection.json")

SPLIT_FILE_PREFIXES = {
    "train": "train",
    "dev": "dev",
    "test": "test",
    "outliers": "outliers",
}

