# Grammar Relationships V1

This package builds deterministic relationship edges between canonical Grammar V1
skills. It does not add or redesign canonical skills; group nodes such as
`grammar.present_simple` are structural taxonomy nodes derived from existing
skill ids.

## Commands

```powershell
python -m knowledge_core.relationships.cli inspect
python -m knowledge_core.relationships.cli run
python -m knowledge_core.relationships.cli validate --show-path grammar.present_perfect.experience
python -m knowledge_core.relationships.cli analyze --skill grammar.passive.present_simple
python -m knowledge_core.relationships.cli report --relation prerequisite_of
```

Common options may be placed before or after the subcommand.

## Outputs

- `data/curated/relationships/grammar_relationships.jsonl`
- `data/curated/relationships/grammar_relationships.parquet`
- `data/curated/review/grammar_relationship_review.csv`
- `data/reports/relationships/grammar_relationship_report.json`
- `data/reports/relationships/grammar_relationship_graph.json`

## Model

`parent_of` edges are generated from the canonical skill id namespace and are
accepted structural evidence. Curated pedagogical edges are configured in
`config/grammar_relationship_rules.yaml` and kept as reviewable candidates.
CEFR and EGP evidence is attached only as supporting context; CEFR ordering
alone never creates prerequisite edges.
