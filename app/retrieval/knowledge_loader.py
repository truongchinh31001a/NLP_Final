import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


REQUIRED_KNOWLEDGE_FIELDS = {
    "chunk_id",
    "topic_code",
    "subtopic",
    "skill",
    "level",
    "language",
    "content",
    "examples",
    "common_mistakes",
    "source",
}


def load_knowledge_chunk_records(path: str | Path) -> list[dict[str, Any]]:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"Knowledge chunks file not found: {source_path}")

    records = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Knowledge chunks file must contain a JSON array.")

    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Knowledge chunk at index {index} must be an object.")

        missing_fields = REQUIRED_KNOWLEDGE_FIELDS - set(record)
        if missing_fields:
            chunk_id = record.get("chunk_id", f"index-{index}")
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"Knowledge chunk {chunk_id} missing fields: {missing}")

        chunk_id = str(record["chunk_id"])
        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate knowledge chunk id: {chunk_id}")
        seen_ids.add(chunk_id)

    return records


def load_knowledge_documents(path: str | Path) -> list[Document]:
    return [
        knowledge_record_to_document(record)
        for record in load_knowledge_chunk_records(path)
    ]


def knowledge_record_to_document(record: dict[str, Any]) -> Document:
    metadata = {
        "chunk_id": record["chunk_id"],
        "topic": record["topic_code"],
        "topic_code": record["topic_code"],
        "subtopic": record["subtopic"],
        "skill": record["skill"],
        "level": record["level"],
        "language": record["language"],
        "source": record["source"],
        "formula": record.get("formula", ""),
        "examples_json": json.dumps(record.get("examples", []), ensure_ascii=False),
        "common_mistakes_json": json.dumps(
            record.get("common_mistakes", []),
            ensure_ascii=False,
        ),
    }
    return Document(page_content=record["content"], metadata=metadata)
