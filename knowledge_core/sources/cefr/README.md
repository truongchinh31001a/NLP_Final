# CEFR Source Ingestion

This package parses the local CEFR Companion Volume 2020 PDF into two separate
layers:

1. normalized CEFR descriptor source records
2. derived CEFR learning objective candidates

It does not map descriptors to the Grammar V1 taxonomy.

## Run

```powershell
python -m knowledge_core.sources.cefr.cli run
```

Useful filters:

```powershell
python -m knowledge_core.sources.cefr.cli run --domain production
python -m knowledge_core.sources.cefr.cli run --section chapter5
python -m knowledge_core.sources.cefr.cli run --level B1
```

## Outputs

- `data/interim/cefr/cefr_descriptors.jsonl`
- `data/interim/cefr/cefr_descriptors.parquet`
- `data/interim/cefr/cefr_learning_objective_candidates.jsonl`
- `data/interim/cefr/cefr_learning_objective_candidates.parquet`
- `data/reports/cefr/source_inspection_report.json`
- `data/reports/cefr/extraction_report.json`

Rows like `No descriptors available; see C1` are preserved in descriptor
records with `descriptor_available=false`, but they are not converted into
learning objective candidates.

