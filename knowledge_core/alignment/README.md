# Knowledge Alignment

This package aligns existing EGP and CEFR evidence around the existing Grammar
V1 canonical skill list. It does not mutate the canonical taxonomy.

Run the full milestone:

```powershell
python -m knowledge_core.alignment.cli run
```

Inspect existing inputs only:

```powershell
python -m knowledge_core.alignment.cli inspect
```

Useful display filters:

```powershell
python -m knowledge_core.alignment.cli report --skill grammar.present_perfect.experience
python -m knowledge_core.alignment.cli validate --level B1
python -m knowledge_core.alignment.cli report --min-confidence 0.75
```

Generated artifacts:

- `data/interim/knowledge_alignment/grammar_skill_evidence.jsonl`
- `data/interim/knowledge_alignment/grammar_skill_evidence.parquet`
- `data/interim/knowledge_alignment/cefr_egp_alignment.jsonl`
- `data/interim/knowledge_alignment/cefr_egp_alignment.parquet`
- `data/interim/knowledge_alignment/skill_source_evidence.jsonl`
- `data/interim/knowledge_alignment/skill_source_evidence.parquet`
- `data/curated/review/cefr_egp_alignment_review.csv`
- `data/reports/knowledge_alignment/cefr_egp_alignment_report.json`

Ambiguous EGP mappings are preserved for review but do not establish CEFR
levels automatically. CEFR grammatical accuracy records are attached as global
proficiency context for the inferred level, not as direct proof of any atomic
grammar skill.

