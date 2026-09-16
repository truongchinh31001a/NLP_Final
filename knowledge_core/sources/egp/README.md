# English Grammar Profile Source Adapter

This package ingests English Grammar Profile (EGP) Online exports as source
records for the knowledge core.

EGP source taxonomy is not the canonical Grammar V1 taxonomy. This adapter
stops at:

```text
EGP -> raw XLSX -> normalized source records -> validation
```

It does not create canonical skills, mutate the skill graph, infer
prerequisites, or map source can-do statements to atomic grammar skills. The
`canonical_parent_hint` values are retained only as metadata for a later mapping
layer.

## Installation

Install the backend dependencies:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

The Playwright browser install is needed only for live downloads. Offline
parsing and validation of existing XLSX files do not require a browser.

## Configuration

The category list lives in:

```text
config/egp_categories.yaml
```

Each category has a stable source id, the search query to use on EGP Online,
the relative `raw_path` under `data/external/english_profile/Grammar`, expected
source taxonomy labels, and an optional `canonical_parent_hint`. The hint must
remain metadata only.

## Downloading

Download all configured categories:

```bash
python -m knowledge_core.sources.egp.cli download
```

Download one category:

```bash
python -m knowledge_core.sources.egp.cli download --category present_perfect_simple
```

Raw files are written to:

```text
data/external/english_profile/Grammar/<configured raw_path>
```

For example:

```text
data/external/english_profile/Grammar/Tenses/Present Simple/present_simple.xlsx
```

Existing files are skipped by default. Use `--force` to overwrite them. Use
`--dry-run` to inspect what would run without downloading.

## Source Inspection

Inspect downloaded XLSX files without downloading anything:

```bash
python -m knowledge_core.sources.egp.cli inspect
```

Report path:

```text
data/reports/egp/source_inspection_report.json
```

## HTTP vs Playwright

The live EGP page inspected on September 7, 2026 is a Bubble application. Its
XLSX action uses a client-side plugin with SheetJS/FileSaver to create the file
from page JSON. The browser network trace used encrypted Bubble
`/elasticsearch/msearch` and `/elasticsearch/search` requests, and no stable
direct XLSX endpoint was found in the rendered page, static page, or bundled
plugin code. A temporary browser download was verified for `present_simple`;
all-category live acquisition should still be monitored because the UI is
controlled by the upstream site.

For that reason, `auto` mode uses `BrowserEGPDownloader` unless you provide a
confirmed export URL template:

```bash
python -m knowledge_core.sources.egp.cli download \
  --method http \
  --http-export-url-template "https://example.test/export?query={query}&level={level}"
```

The browser fallback uses Chromium, headless mode by default, Playwright
download events, semantic selectors where available, and one category at a time.
Use `--headed` to watch the browser during troubleshooting.

## Parsing

Parse existing raw XLSX files offline:

```bash
python -m knowledge_core.sources.egp.cli parse
```

Outputs:

```text
data/interim/english_profile/grammar/egp_records.jsonl
data/interim/english_profile/grammar/egp_records.parquet
```

The parser scans workbook headers, tolerates column ordering changes, keeps the
raw row payload, records the Excel row number, and preserves the original
can-do text.

Rows that do not match the configured EGP category, or that contain invalid
required source fields, are excluded from the V1 category-normalized outputs
and reported explicitly at:

```text
data/reports/egp/source_exclusion_report.json
```

The raw XLSX files are preserved unchanged.

## Normalization

Normalization is source-only. It trims whitespace, uppercases CEFR labels,
normalizes empty values to `null`, and parses labels such as:

```text
FORM/USE: WITH 'ALREADY'
```

into `feature_type = FORM/USE` and `feature_name = WITH 'ALREADY'`.

It does not rewrite source statements or infer canonical grammar skills.

## Validation

Validate and write a report:

```bash
python -m knowledge_core.sources.egp.cli validate
```

Report path:

```text
data/reports/egp/validation_report.json
```

Validation checks CEFR labels, empty can-do statements, configured category ids,
expected EGP source categories/subcategories, duplicate source records, source
file existence, empty parsed workbooks, and canonical parent hint identifiers.

## Full Run

Run download, parse, validate, and reporting:

```bash
python -m knowledge_core.sources.egp.cli run
```

The command does not bypass authentication, CAPTCHA, access controls, rate
limits, or source terms.

For the post-download Grammar V1 pipeline, use the mapping CLI instead:

```bash
python -m knowledge_core.mapping.egp.cli run
```

That command does not download anything; it inspects, parses, maps, validates,
creates the human review queue, and writes the mapping report from local XLSX
files.

## Provenance

Downloaded files receive sidecar metadata:

```text
data/external/english_profile/Grammar/Tenses/Present Simple/present_simple.metadata.json
```

The sidecar lives next to the XLSX file with the `.xlsx` suffix replaced by
`.metadata.json`.

Each normalized record stores source name, configured category id, raw file,
row number, CEFR level, source URL when known, retrieval timestamp, and future
canonical parent hint when configured.

When parsing manually supplied XLSX files without sidecar metadata, the parser
uses the file modification time as the best available local timestamp and leaves
`source_url` empty.

## Data Handling

Do not commit restricted EGP downloads or derived EGP record exports unless the
source license explicitly permits it. The repository keeps code, config, docs,
and synthetic tests, while `.gitignore` excludes generated EGP XLSX, JSONL,
Parquet, metadata, and validation report files.

Users are responsible for acquiring and using EGP data according to the source
Terms of Use.

## Troubleshooting

If downloads fail, run with `--headed --log-level DEBUG` and confirm the EGP UI
still exposes a search field, an All level selector, a Search control, and a
Download XLSX control.

If Parquet output fails, verify `pyarrow` is installed in the active Python
environment.

If validation reports category mismatches, inspect the raw XLSX first. The
adapter reports mismatches but does not alter the canonical taxonomy.
