import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import AppConfig
from app.retrieval.pgvector_store import PgVectorKnowledgeStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test pgvector retrieval against a running Postgres service.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "PGVECTOR_DATABASE_URL",
            "postgresql://english_tutor:english_tutor@localhost:5432/english_tutor",
        ),
    )
    parser.add_argument("--table-name", default="rag_smoke_documents")
    parser.add_argument("--connect-timeout", type=int, default=5)
    parser.add_argument("--embedding-backend", default=os.getenv("EMBEDDING_BACKEND", "keyword_hash"))
    parser.add_argument("--ollama-base-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11435"))
    parser.add_argument("--ollama-embedding-model", default=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"))
    parser.add_argument("--topic", default="passive_voice")
    parser.add_argument("--level", default="beginner")
    parser.add_argument("--subtopic", default="present_simple_passive")
    parser.add_argument("--expected-chunk-id", default="grammar_passive_002")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--soft",
        action="store_true",
        help="Print report but return exit code 0 even when checks fail.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig(
        vector_store_backend="pgvector",
        pgvector_database_url=with_connect_timeout(
            args.database_url,
            args.connect_timeout,
        ),
        pgvector_table_name=args.table_name,
        embedding_backend=args.embedding_backend,
        ollama_base_url=args.ollama_base_url,
        ollama_embedding_model=args.ollama_embedding_model,
        retrieval_top_k=args.limit,
    )
    checks: list[dict[str, Any]]
    try:
        store = PgVectorKnowledgeStore(config)
        chunks = store.search(
            args.topic,
            args.level,
            args.limit,
            subtopic=args.subtopic,
        )
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        checks = [
            check("pgvector_search_non_empty", bool(chunks), {"chunk_ids": chunk_ids}),
            check(
                "expected_chunk_returned",
                args.expected_chunk_id in chunk_ids,
                {"expected": args.expected_chunk_id, "chunk_ids": chunk_ids},
            ),
            check(
                "metadata_matches",
                bool(chunks)
                and chunks[0].topic == args.topic
                and chunks[0].level == args.level
                and chunks[0].metadata.get("subtopic") == args.subtopic,
                {"top_chunk": chunk_ids[0] if chunk_ids else None},
            ),
        ]
    except Exception as exc:
        checks = [
            check(
                "pgvector_retrieval_available",
                False,
                {"error": str(exc)},
            ),
        ]

    report = {
        "status": "ok" if all(item["passed"] for item in checks) else "failed",
        "database_url": redacted_database_url(args.database_url),
        "table_name": args.table_name,
        "embedding_backend": args.embedding_backend,
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok" and not args.soft:
        raise SystemExit(1)


def check(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    }


def redacted_database_url(value: str) -> str:
    if "@" not in value or "://" not in value:
        return value
    scheme, rest = value.split("://", maxsplit=1)
    return f"{scheme}://***@{rest.split('@', maxsplit=1)[1]}"


def with_connect_timeout(database_url: str, timeout_seconds: int) -> str:
    if "connect_timeout=" in database_url:
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}connect_timeout={max(timeout_seconds, 1)}"


if __name__ == "__main__":
    main()
