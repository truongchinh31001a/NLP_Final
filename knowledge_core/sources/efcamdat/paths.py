from __future__ import annotations

from pathlib import Path


SOURCE_KEY = "efcamdat"
SOURCE_NAME = "EFCAMDAT"
DEFAULT_RAW_ROOT = Path("data/raw/EFCAMDAT")
DEFAULT_XML_PATH = DEFAULT_RAW_ROOT / "EFCAMDAT_Database.xml"
DEFAULT_CSV_PATH = (
    DEFAULT_RAW_ROOT
    / "Cleaned_Error-coded_Subcorpus (Öksüz et al., 2025)"
    / "ef_POStagged_original_corrected.csv"
)
DEFAULT_INTERIM_DIR = Path("data/interim/efcamdat")
DEFAULT_REPORTS_DIR = Path("data/reports/efcamdat")
DEFAULT_REVIEW_DIR = Path("data/curated/review")
DEFAULT_SOURCE_INVENTORY_REPORT = Path("data/reports/source_inventory/efcamdat_inspection.json")

