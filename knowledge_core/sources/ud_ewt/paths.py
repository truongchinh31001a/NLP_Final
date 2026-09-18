from __future__ import annotations

from pathlib import Path


SOURCE_KEY = "ud_english_ewt"
SOURCE_NAME = "Universal Dependencies English EWT"
DEFAULT_RELEASE_ROOT = Path("data/raw/UD_English-EWT-master/UD_English-EWT-master")
DEFAULT_SOURCE_INVENTORY_REPORT = Path("data/reports/source_inventory/ud_ewt_inspection.json")
DEFAULT_INTERIM_DIR = Path("data/interim/ud_ewt")
DEFAULT_REPORTS_DIR = Path("data/reports/ud_ewt")
DEFAULT_REVIEW_DIR = Path("data/curated/review")

RELEASED_SPLIT_FILENAMES = {
    "train": "en_ewt-ud-train.conllu",
    "dev": "en_ewt-ud-dev.conllu",
    "test": "en_ewt-ud-test.conllu",
}

