# Evaluation Suite

This folder contains lightweight offline evaluations for the adaptive tutor.

Run all available checks:

```bash
python scripts/run_evals.py
```

Run the checks that do not require LangChain retrieval dependencies:

```bash
python scripts/run_evals.py --skip-retrieval
```

Evaluation groups:

- `generation`: schema validity and validator compliance.
- `diagnosis`: structured error classification accuracy.
- `recommendation`: next-practice recommendation policy and evidence checks.
- `tutor_response`: natural tutor response guardrails, repeated-menu avoidance,
  off-topic bridge checks, and learning-focus selections.
- `explanation_grounding`: `EXPLAIN` responses preserve retrieved source
  metadata and include grounded context when available.
- `retrieval`: Precision@K, Recall@K, MRR, NDCG@K, metadata precision, source
  precision, CEFR precision, and expected chunk recall.

The retrieval summary score is a composite of Recall@K, metadata Recall@K,
expected chunk Recall@K, and top-1 metadata match.

Reports are written to `evals/reports/`.

CI threshold gates use `evals/thresholds.json`:

```bash
python scripts/check_eval_thresholds.py
```

Retrieval evaluation uses `scripts/evaluate_retrieval.py` and can be run in
isolation:

```bash
python scripts/evaluate_retrieval.py --mode hybrid --top-k 5
```

Tutor response live comparison is optional because it needs a configured model
runtime:

```bash
python scripts/run_evals.py --skip-retrieval --tutor-live-backends ollama
python scripts/run_evals.py --skip-retrieval --tutor-live-backends openai
```
