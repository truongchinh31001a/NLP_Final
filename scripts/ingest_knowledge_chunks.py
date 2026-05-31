import argparse
import sys
from collections import Counter
from pathlib import Path

from langchain_chroma import Chroma

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import AppConfig
from app.retrieval.embeddings import KeywordHashEmbeddings
from app.retrieval.knowledge_loader import load_knowledge_documents


def parse_args() -> argparse.Namespace:
    config = AppConfig()
    parser = argparse.ArgumentParser(
        description="Ingest processed English knowledge chunks into Chroma."
    )
    parser.add_argument(
        "--input",
        default=config.knowledge_chunks_path,
        help="Path to knowledge_chunks.json.",
    )
    parser.add_argument(
        "--persist-dir",
        default=config.chroma_persist_directory,
        help="Chroma persist directory.",
    )
    parser.add_argument(
        "--collection",
        default=config.chroma_collection_name,
        help="Chroma collection name.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the collection instead of replacing existing records.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    persist_dir = Path(args.persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    documents = load_knowledge_documents(input_path)
    ids = [str(document.metadata["chunk_id"]) for document in documents]

    vector_store = Chroma(
        collection_name=args.collection,
        embedding_function=KeywordHashEmbeddings(),
        persist_directory=str(persist_dir),
    )

    if not args.append:
        existing = vector_store.get()
        existing_ids = existing.get("ids") or []
        if existing_ids:
            vector_store.delete(ids=existing_ids)

    vector_store.add_documents(documents=documents, ids=ids)

    by_topic = Counter(document.metadata["topic"] for document in documents)
    by_level = Counter(document.metadata["level"] for document in documents)
    print(f"Ingested {len(documents)} knowledge chunks into Chroma.")
    print(f"Collection: {args.collection}")
    print(f"Persist dir: {persist_dir}")
    print(f"By topic: {dict(sorted(by_topic.items()))}")
    print(f"By level: {dict(sorted(by_level.items()))}")


if __name__ == "__main__":
    main()
