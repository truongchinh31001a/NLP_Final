# Source Governance V1

Generated at: 2026-09-16T15:30:28.370968+00:00

This report records source URLs, local license evidence, and raw-data safety policy for Knowledge Core V1. It is a governance summary, not legal advice.

## Raw Data Policy

- restricted_raw_paths_gitignored: True
- redistribution_policy: Do not redistribute raw corpus files from this repository. Derived reports may summarize structure and counts only; learner free text must not be emitted in logs, reports, exceptions, or test snapshots.
- excluded_raw_dataset_policy: data/raw/Dataset is excluded from Knowledge Core V1 and remains ignored as unrelated raw exam data.
- existing_tracked_raw_file_policy: If an ignored raw path already has files tracked in Git, this inspection does not alter the index; untracking requires a deliberate git rm --cached review step.

## Sources

| Source | Required V1 | Optional | URL status | License status |
| --- | --- | --- | --- | --- |
| EFCAMDAT | True | False | recorded | local_user_agreement_reviewed_restricted |
| Cambridge Learner Corpus FCE | True | False | recorded | local_readme_reviewed_specific_license_missing |
| Write & Improve Corpus 2024 | False | True | recorded | needs_manual_review |
| Universal Dependencies English EWT | False | True | recorded | locally_documented_with_caveats |
| English Grammar Profile | True | False | recorded | needs_manual_review |
| CEFR Companion Volume 2020 | True | False | recorded | needs_manual_review |

## Classified Raw Datasets

- `data/raw/Dataset`: `unrelated_to_knowledge_core_v1`, files=695, included=false. Directory contains VNHSGE/MET exam-style files with JSON/DOCX/image assets across school subjects; it is not one of the six Knowledge Core V1 sources.

## Validation

- `official_source_urls_recorded`: True
- `raw_paths_gitignored`: True
- `raw_dataset_exclusion_recorded`: True
- `license_constraints_summarized`: True
- `legal_clearance_complete_for_all_sources`: False
