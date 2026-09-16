# EGP Mapping Layer

This directory contains source-to-canonical mapping code.

The EGP source adapter produces normalized source records. The mapper turns
those records into deterministic candidates for the authoritative Grammar V1
taxonomy with these statuses:

- `exact`
- `candidate`
- `ambiguous`
- `unmapped`

The mapper does not create, expand, or mutate canonical grammar skills.

Run the full post-download pipeline:

```powershell
python -m knowledge_core.mapping.egp.cli run
```

This command does not download anything. It reads XLSX files from
`data/external/english_profile/Grammar`, writes normalized records and mappings
to `data/interim/english_profile/grammar`, writes the human review queue to
`data/curated/review/egp_mapping_review.csv`, and writes reports to
`data/reports/egp`.

The normalized V1 dataset excludes unrelated search/export rows and invalid
source rows. Those exclusions are not deleted; they are reported in
`data/reports/egp/source_exclusion_report.json` with source row numbers and
reason codes.
