import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from langchain_core.vectorstores import InMemoryVectorStore

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import AppConfig
from app.retrieval.embeddings import KeywordHashEmbeddings
from app.retrieval.knowledge_loader import load_knowledge_documents


def parse_args() -> argparse.Namespace:
    config = AppConfig()
    parser = argparse.ArgumentParser(
        description="Evaluate knowledge retrieval against labeled topic queries."
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
        default=3,
        help="Number of retrieved chunks to evaluate per query.",
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
    return rows


def main() -> None:
    args = parse_args()
    documents = load_knowledge_documents(args.knowledge)
    queries = load_queries(args.queries)

    vector_store = InMemoryVectorStore(embedding=KeywordHashEmbeddings())
    vector_store.add_documents(documents)
    retriever = vector_store.as_retriever(
        search_kwargs={"k": max(args.top_k, 1)}
    )

    rows: list[dict[str, object]] = []
    for query_row in queries:
        retrieved = retriever.invoke(query_row["query"])
        topics = [doc.metadata.get("topic_code", "") for doc in retrieved]
        levels = [doc.metadata.get("level", "") for doc in retrieved]
        chunk_ids = [doc.metadata.get("chunk_id", "") for doc in retrieved]

        expected_topic = query_row["expected_topic"]
        expected_level = query_row["expected_level"]
        rows.append(
            {
                "query": query_row["query"],
                "expected_topic": expected_topic,
                "expected_level": expected_level,
                "top_1_topic": topics[0] if topics else "",
                "top_1_level": levels[0] if levels else "",
                "top_k_topics": topics,
                "top_k_chunk_ids": chunk_ids,
                "top_1_match": bool(topics and topics[0] == expected_topic),
                "top_k_match": expected_topic in topics,
                "top_1_level_match": bool(levels and levels[0] == expected_level),
            }
        )

    total = len(rows)
    top_1_matches = sum(1 for row in rows if row["top_1_match"])
    top_k_matches = sum(1 for row in rows if row["top_k_match"])
    top_1_level_matches = sum(1 for row in rows if row["top_1_level_match"])
    by_expected_topic = Counter(row["expected_topic"] for row in rows)
    top_1_by_topic = Counter(
        row["expected_topic"] for row in rows if row["top_1_match"]
    )

    print(f"Queries: {total}")
    print(f"Knowledge chunks: {len(documents)}")
    print(f"Top-1 topic match: {top_1_matches}/{total} = {top_1_matches / total:.2%}")
    print(f"Top-{args.top_k} topic match: {top_k_matches}/{total} = {top_k_matches / total:.2%}")
    print(
        f"Top-1 level match: {top_1_level_matches}/{total} = "
        f"{top_1_level_matches / total:.2%}"
    )
    print("Top-1 topic match by expected topic:")
    for topic, count in sorted(by_expected_topic.items()):
        matches = top_1_by_topic[topic]
        print(f"  {topic}: {matches}/{count} = {matches / count:.2%}")

    if args.show_misses:
        misses = [row for row in rows if not row["top_k_match"]]
        if misses:
            print("\nTop-k misses:")
            for row in misses:
                print(
                    f"- {row['query']} | expected={row['expected_topic']} "
                    f"| got={row['top_k_topics']} | chunks={row['top_k_chunk_ids']}"
                )


if __name__ == "__main__":
    main()
