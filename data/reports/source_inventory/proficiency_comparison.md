# CEFR And Proficiency Comparison V1

| Source | Explicit CEFR | Inferred CEFR | Proprietary level | Score only | Granularity | Caveat |
| --- | --- | --- | --- | --- | --- | --- |
| english_grammar_profile | True | False | False | False | record-level | EGP search/export category quirks are unrelated to CEFR labels. |
| cefr_companion_volume_2020 | True | False | False | False | descriptor-level | Only configured V1 scales are extracted. |
| efcamdat | False | False | True | False | writing/course-unit metadata | Course levels are not forced into CEFR. |
| clc_fce | True | False | False | True | dataset/exam-level plus answer/script scores | Individual score does not imply a per-script CEFR conversion here. |
| write_improve | True | False | False | False | essay version row | Automarker and human labels are distinct fields and may disagree. |
