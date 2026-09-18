# Error Taxonomy V1

This package freezes the source-independent learner-error schema used before CLC FCE and EFCAMDAT ingestion.

It defines:

- `LearnerCorpusSourceRecord`
- `ErrorInstance`
- `NormalizedErrorInstance`
- deterministic ID helpers
- normalized error category vocabulary
- span policies for JSON offsets, XML inline selections, M2 token offsets, and EFCAMDAT selection text
- learner free-text safety checks

The schema stores fingerprints and lengths for learner text, selections, and corrections. It must not store raw learner free text in artifacts, logs, reports, exceptions, or tests.

