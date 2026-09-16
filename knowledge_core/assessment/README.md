# Grammar Assessment Criteria V1

This package builds deterministic assessment criteria for the existing 43
canonical Grammar V1 atomic skills. It does not add grammar skills, generate
exercises, or make final learner mastery decisions.

## Commands

```powershell
python -m knowledge_core.assessment.cli inspect
python -m knowledge_core.assessment.cli run
python -m knowledge_core.assessment.cli validate --skill grammar.present_simple.questions
python -m knowledge_core.assessment.cli report --criterion-type form_accuracy
```

Common options may be placed before or after the subcommand.

## Outputs

- `data/curated/assessment/grammar_assessment_criteria.jsonl`
- `data/curated/assessment/grammar_assessment_criteria.parquet`
- `data/curated/assessment/grammar_assessment_profiles.jsonl`
- `data/curated/review/grammar_assessment_criteria_review.csv`
- `data/reports/assessment/grammar_assessment_report.json`

## Boundaries

Recommended thresholds use `threshold_source = curated_v1_default`. They are
guidance for assessment design, not validated mastery rules. Failure signals
are curated diagnostic hints; this layer does not claim empirical misconception
or corpus error evidence.
