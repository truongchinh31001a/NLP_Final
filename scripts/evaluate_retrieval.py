import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import AppConfig
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import LangChainVectorStore
from app.schemas import PracticePlan


def parse_args() -> argparse.Namespace:
    config = AppConfig()
    parser = argparse.ArgumentParser(
        description="Evaluate hybrid knowledge retrieval against labeled queries."
    )
    parser.add_argument(
        "--queries",
        default="./data/evaluation/retrieval_eval_queries.csv",
        help="CSV with query, expected_topic, expected_level columns.",
    )
    parser.add_argument(
        "--knowledge",
        default=config.knowledge_chunks_path,
        help="Path to knowledge_chunks.json.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks to evaluate per query.",
    )
    parser.add_argument(
        "--mode",
        choices=["dense", "sparse", "hybrid"],
        default=config.retrieval_mode,
        help="Retrieval mode to evaluate.",
    )
    parser.add_argument(
        "--no-reranker",
        action="store_true",
        help="Disable heuristic reranking for this evaluation run.",
    )
    parser.add_argument(
        "--report-path",
        default="./evals/reports/retrieval_report.json",
        help="Where to write the JSON metric report.",
    )
    parser.add_argument(
        "--show-misses",
        action="store_true",
        help="Print detailed misses for debugging.",
    )
    return parser.parse_args()


def load_queries(path: str | Path) -> list[dict[str, str]]:
    query_path = Path(path)
    if not query_path.exists():
        raise FileNotFoundError(f"Retrieval eval query file not found: {query_path}")

    with query_path.open(newline="", encoding="utf-8") as csv_file:
        rows = [dict(row) for row in csv.DictReader(csv_file)]

    required = {"query", "expected_topic", "expected_level"}
    for index, row in enumerate(rows):
        missing = required - set(row)
        if missing:
            raise ValueError(f"Query row {index} missing columns: {sorted(missing)}")
        for field in required:
            row[field] = row[field].strip()
            if not row[field]:
                raise ValueError(f"Query row {index} has empty field: {field}")
        row["expected_subtopic"] = row.get("expected_subtopic", "").strip()
    return rows


def main() -> None:
    args = parse_args()
    config = AppConfig(
        knowledge_chunks_path=args.knowledge,
        retrieval_top_k=args.top_k,
        vector_store_backend="inmemory",
        retrieval_mode=args.mode,
        reranker_enabled=not args.no_reranker,
    )
    retrieval = RetrievalService(config, LangChainVectorStore(config))
    queries = load_queries(args.queries)

    rows: list[dict[str, object]] = []
    for query_row in queries:
        plan = PracticePlan(
            user_id="eval",
            topic=query_row["expected_topic"],
            difficulty="medium",
            exercise_type="grammar_mcq",
            num_questions=5,
            focus_reason=query_row["query"],
            target_subtopic=query_row.get("expected_subtopic") or None,
        )
        retrieved = retrieval.retrieve(plan, query_row["expected_level"])
        topics = [chunk.topic for chunk in retrieved]
        levels = [chunk.level for chunk in retrieved]
        chunk_ids = [chunk.chunk_id for chunk in retrieved]
        relevance = [int(topic == query_row["expected_topic"]) for topic in topics]
        level_relevance = [
            int(
                topic == query_row["expected_topic"]
                and level == query_row["expected_level"]
            )
            for topic, level in zip(topics, levels)
        ]
        rows.append(
            {
                "query": query_row["query"],
                "expected_topic": query_row["expected_topic"],
                "expected_level": query_row["expected_level"],
                "top_1_topic": topics[0] if topics else "",
                "top_1_level": levels[0] if levels else "",
                "top_k_topics": topics,
                "top_k_levels": levels,
                "top_k_chunk_ids": chunk_ids,
                "precision_at_k": precision_at_k(relevance, args.top_k),
                "recall_at_k": recall_at_k(relevance),
                "mrr": reciprocal_rank(relevance),
                "ndcg_at_k": ndcg_at_k(relevance),
                "level_precision_at_k": precision_at_k(level_relevance, args.top_k),
                "top_1_match": bool(relevance and relevance[0]),
                "top_k_match": any(relevance),
            }
        )

    report = build_report(rows, args)
    print_report(report)
    write_report(report, args.report_path)

    if args.show_misses:
        print_misses(rows)


def build_report(
    rows: list[dict[str, object]],
    args: argparse.Namespace,
) -> dict[str, object]:
    total = len(rows)
    by_expected_topic = Counter(str(row["expected_topic"]) for row in rows)
    top_1_by_topic = Counter(
        str(row["expected_topic"]) for row in rows if row["top_1_match"]
    )
    return {
        "retrieval_mode": args.mode,
        "reranker_enabled": not args.no_reranker,
        "top_k": args.top_k,
        "query_count": total,
        "metrics": {
            "top_1_topic_match": mean_bool(rows, "top_1_match"),
            "recall_at_k": mean_float(rows, "recall_at_k"),
            "precision_at_k": mean_float(rows, "precision_at_k"),
            "mrr": mean_float(rows, "mrr"),
            "ndcg_at_k": mean_float(rows, "ndcg_at_k"),
            "level_precision_at_k": mean_float(rows, "level_precision_at_k"),
        },
        "top_1_topic_match_by_expected_topic": {
            topic: {
                "matches": top_1_by_topic[topic],
                "total": count,
                "rate": top_1_by_topic[topic] / count,
            }
            for topic, count in sorted(by_expected_topic.items())
        },
        "rows": rows,
    }


def precision_at_k(relevance: list[int], top_k: int) -> float:
    return sum(relevance[:top_k]) / max(top_k, 1)


def recall_at_k(relevance: list[int]) -> float:
    return 1.0 if any(relevance) else 0.0


def reciprocal_rank(relevance: list[int]) -> float:
    for index, is_relevant in enumerate(relevance, start=1):
        if is_relevant:
            return 1.0 / index
    return 0.0


def ndcg_at_k(relevance: list[int]) -> float:
    dcg = sum(
        relevance_score / math.log2(rank + 1)
        for rank, relevance_score in enumerate(relevance, start=1)
    )
    ideal = sorted(relevance, reverse=True)
    ideal_dcg = sum(
        relevance_score / math.log2(rank + 1)
        for rank, relevance_score in enumerate(ideal, start=1)
    )
    return dcg / ideal_dcg if ideal_dcg else 0.0


def mean_float(rows: list[dict[str, object]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(float(row[key]) for row in rows) / len(rows)


def mean_bool(rows: list[dict[str, object]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row[key]) / len(rows)


def print_report(report: dict[str, object]) -> None:
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    print(f"Queries: {report['query_count']}")
    print(f"Mode: {report['retrieval_mode']}")
    print(f"Reranker enabled: {report['reranker_enabled']}")
    print(f"Top-K: {report['top_k']}")
    for name, value in metrics.items():
        print(f"{name}: {float(value):.3f}")


def print_misses(rows: list[dict[str, object]]) -> None:
    misses = [row for row in rows if not row["top_k_match"]]
    if not misses:
        return
    print("\nTop-k misses:")
    for row in misses:
        print(
            f"- {row['query']} | expected={row['expected_topic']} "
            f"| got={row['top_k_topics']} | chunks={row['top_k_chunk_ids']}"
        )


def write_report(report: dict[str, object], path: str | Path) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
