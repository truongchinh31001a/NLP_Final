# Global Source Inventory V1

Generated at: 2026-09-16T10:51:53.124316+00:00

## Source Summary

| Source | Required V1 | Optional | Status | Roles | Root | Files | Formats | Records | Count type | Readiness | License |
| --- | --- | --- | --- | --- | --- | ---: | --- | ---: | --- | --- | --- |
| EFCAMDAT | True | False | discovered | annotated_error_corpus, learner_corpus | data/raw/EFCAMDAT | 14 | .csv, .pdf, .r, .txt, .xml, .zip | 1425956 | estimated | READY_WITH_KNOWN_QUIRKS | needs_manual_review |
| Cambridge Learner Corpus FCE | True | False | discovered | annotated_error_corpus | data/raw/_fce-released-dataset-1.1 | 12 | .json, .pdf, .xml, [no_extension] | 2543 | exact | READY_WITH_KNOWN_QUIRKS | needs_manual_review |
| Write & Improve Corpus 2024 | False | True | discovered | revision_corpus, annotated_error_corpus | data/raw/write-and-improve-corpus-2024-v2 | 82 | .conll, .corr, .ids, .m2, .md, .orig, .py, .tmp, .tsv, [no_extension] | 23216 | exact | READY_WITH_KNOWN_QUIRKS | needs_manual_review |
| Universal Dependencies English EWT | False | True | discovered | linguistic_structure_resource | data/raw/UD_English-EWT-master | 1202 | .conllu, .dev, .ini, .log, .md, .py, .sh, .test, .train, .txt, .xml, [no_extension] | 16622 | exact | READY | locally_documented_with_caveats |
| English Grammar Profile | True | False | discovered | canonical_grammar_evidence | data/external/english_profile | 35 | .json, .jsonl, .parquet, .xlsx | 273 | exact | READY | needs_manual_review |
| CEFR Companion Volume 2020 | True | False | discovered | proficiency_framework | data/external/cefr | 7 | .json, .jsonl, .parquet, .pdf | 334 | exact | READY | needs_manual_review |

## Classified Excluded Raw Data

- `data/raw/Dataset`: `unrelated_to_knowledge_core_v1`, files=695, included=false. Directory contains VNHSGE/MET exam-style files with JSON/DOCX/image assets across school subjects; it is not one of the six Knowledge Core V1 sources.

## Warnings And Errors

No inspection warnings or errors.

## Validation

Passed: `True`

- `all_expected_sources_accounted_for`: True
- `required_source_flags_correct`: True
- `optional_sources_remain_inventoried`: True
- `all_raw_files_assigned_or_classified`: True
- `all_raw_dataset_files_have_classification_context`: True
- `efcamdat_annotation_source_of_truth_documented`: True
- `new_corpus_reports_generated`: True
- `file_counts_internally_consistent`: True
- `raw_data_unchanged`: True
- `canonical_taxonomy_unchanged`: True
- `no_ingestion_artifacts_created`: True
- `inspection_issues_reported`: True
