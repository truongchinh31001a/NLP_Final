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
- `recommendation`: next-practice recommendation policy checks.
- `retrieval`: Precision@K, Recall@K, MRR, and NDCG@K.

Reports are written to `evals/reports/`.

Retrieval evaluation uses `scripts/evaluate_retrieval.py` and can be run in
isolation:

```bash
python scripts/evaluate_retrieval.py --mode hybrid --top-k 5
```
