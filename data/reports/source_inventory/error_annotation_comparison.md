# Error Annotation Comparison V1

Source-native structures only. No error label normalization is performed here.

| Source | Unit | Original | Corrected | Span | Labels | Revision | Parser difficulty |
| --- | --- | --- | --- | --- | --- | --- | --- |
| efcamdat | XML change and cleaned CSV rows | XML selection/text and CSV original column | XML correct descendant and CSV corrected column | XML selection text in change markup, not normalized offsets; CSV original/corrected are derived text views. | 24 | False | high |
| clc_fce | answer-level edit or inline XML e element | text field in JSON and text content in XML | edits correction slot in JSON and c elements in XML | JSON character offsets; XML inline spans. | 681 | False | medium |
| write_improve | sentence-level M2 edit plus document-level TSV response | TSV text plus .orig/.tmp/.md files | .corr and M2 corrections for train/dev; test may be original-only | M2 token offsets within sentence | 54 | True | medium |
