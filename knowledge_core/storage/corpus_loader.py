from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from knowledge_core.storage.config import DEFAULT_VERSION_NAME, resolve_db_path
from knowledge_core.storage.schema import initialize_schema


DEFAULT_SOURCE_RECORD_PATHS = (
    Path("data/interim/clc_fce/source_records.jsonl"),
    Path("data/interim/efcamdat/source_records.jsonl"),
)
DEFAULT_ERROR_PATHS = (
    Path("data/interim/clc_fce/error_instances.jsonl"),
    Path("data/interim/efcamdat/error_instances.jsonl"),
)
DEFAULT_NORMALIZED_PATH = Path("data/interim/corpus_errors/normalized_error_instances.jsonl")


@dataclass(frozen=True, slots=True)
class CorpusStorageLoadResult:
    version_name: str
    source_record_count: int
    error_instance_count: int
    normalized_error_count: int
    cefr_pattern_count: int
    missing_source_record_links: int
    missing_normalized_error_links: int
    elapsed_seconds: float

    @property
    def is_valid(self) -> bool:
        return self.missing_source_record_links == 0 and self.missing_normalized_error_links == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "version_name": self.version_name,
            "source_record_count": self.source_record_count,
            "error_instance_count": self.error_instance_count,
            "normalized_error_count": self.normalized_error_count,
            "cefr_pattern_count": self.cefr_pattern_count,
            "missing_source_record_links": self.missing_source_record_links,
            "missing_normalized_error_links": self.missing_normalized_error_links,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "validation_result": "PASS" if self.is_valid else "FAIL",
        }


def load_corpus_error_storage(
    *,
    db_path: str | Path | None = None,
    version_name: str = DEFAULT_VERSION_NAME,
    source_record_paths: Sequence[str | Path] = DEFAULT_SOURCE_RECORD_PATHS,
    error_paths: Sequence[str | Path] = DEFAULT_ERROR_PATHS,
    normalized_path: str | Path = DEFAULT_NORMALIZED_PATH,
    batch_size: int = 10_000,
) -> CorpusStorageLoadResult:
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")
    initialize_schema(db_path)
    started = time.monotonic()
    connection = sqlite3.connect(resolve_db_path(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    try:
        version_id = _version_id(connection, version_name)
        source_ids = _ensure_corpus_sources(connection)
        _clear_existing(connection, version_id)
        source_count = _load_source_records(
            connection, version_id, source_ids, source_record_paths, batch_size
        )
        error_count = _load_error_instances(
            connection, version_id, source_ids, error_paths, batch_size
        )
        normalized_count = _load_normalized_errors(
            connection, version_id, normalized_path, batch_size
        )
        pattern_count = refresh_error_patterns_by_cefr(connection, version_id)
        missing_source_links = _scalar(
            connection,
            "SELECT COUNT(*) FROM error_instances WHERE knowledge_version_id = ? "
            "AND corpus_source_record_id IS NULL",
            (version_id,),
        )
        missing_normalized_links = error_count - normalized_count
        connection.commit()
        return CorpusStorageLoadResult(
            version_name=version_name,
            source_record_count=source_count,
            error_instance_count=error_count,
            normalized_error_count=normalized_count,
            cefr_pattern_count=pattern_count,
            missing_source_record_links=missing_source_links,
            missing_normalized_error_links=max(0, missing_normalized_links),
            elapsed_seconds=time.monotonic() - started,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _version_id(connection: sqlite3.Connection, version_name: str) -> int:
    row = connection.execute(
        "SELECT id FROM knowledge_versions WHERE version_name = ?", (version_name,)
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Knowledge version {version_name!r} is not loaded; run storage 'load' first."
        )
    return int(row["id"])


def _ensure_corpus_sources(connection: sqlite3.Connection) -> dict[str, int]:
    names = {"clc_fce": "Cambridge Learner Corpus FCE", "efcamdat": "EFCAMDAT"}
    for key, name in names.items():
        connection.execute(
            """
            INSERT INTO knowledge_sources (source_key, source_name, source_type, metadata_json)
            VALUES (?, ?, 'annotated_error_corpus', '{}')
            ON CONFLICT(source_key) DO UPDATE SET source_name = excluded.source_name
            """,
            (key, name),
        )
    connection.commit()
    return {
        row["source_key"]: int(row["id"])
        for row in connection.execute(
            "SELECT id, source_key FROM knowledge_sources WHERE source_key IN ('clc_fce', 'efcamdat')"
        )
    }


def _clear_existing(connection: sqlite3.Connection, version_id: int) -> None:
    connection.execute(
        "DELETE FROM corpus_error_cefr_patterns WHERE knowledge_version_id = ?", (version_id,)
    )
    connection.execute(
        "DELETE FROM normalized_error_instances WHERE knowledge_version_id = ?", (version_id,)
    )
    connection.execute("DELETE FROM error_instances WHERE knowledge_version_id = ?", (version_id,))
    connection.execute(
        "DELETE FROM learner_corpus_source_records WHERE knowledge_version_id = ?", (version_id,)
    )
    connection.commit()


def refresh_error_patterns_by_cefr(connection: sqlite3.Connection, version_id: int) -> int:
    connection.execute(
        "DELETE FROM corpus_error_cefr_patterns WHERE knowledge_version_id = ?", (version_id,)
    )
    connection.execute(
        """
        INSERT INTO corpus_error_cefr_patterns (
            knowledge_version_id, source_key, proficiency_label, category, subtype, error_count
        )
        SELECT nei.knowledge_version_id, nei.source_key,
               COALESCE(lcsr.proficiency_label, 'unknown'), nei.category, nei.subtype, COUNT(*)
        FROM normalized_error_instances nei
        JOIN error_instances ei ON ei.id = nei.error_instance_db_id
        LEFT JOIN learner_corpus_source_records lcsr ON lcsr.id = ei.corpus_source_record_id
        WHERE nei.knowledge_version_id = ?
        GROUP BY nei.knowledge_version_id, nei.source_key,
                 COALESCE(lcsr.proficiency_label, 'unknown'), nei.category, nei.subtype
        """,
        (version_id,),
    )
    connection.commit()
    return _scalar(
        connection,
        "SELECT COUNT(*) FROM corpus_error_cefr_patterns WHERE knowledge_version_id = ?",
        (version_id,),
    )


def _load_source_records(
    connection: sqlite3.Connection,
    version_id: int,
    source_ids: dict[str, int],
    paths: Sequence[str | Path],
    batch_size: int,
) -> int:
    sql = """
        INSERT INTO learner_corpus_source_records (
            knowledge_version_id, knowledge_source_id, source_record_id, source_key,
            native_record_id, record_unit, split, learner_id_pseudonym,
            document_id_pseudonym, task_id, proficiency_label, source_path,
            text_fingerprint, text_length, metadata_json, provenance_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows = (
        (
            version_id, source_ids[item["source_key"]], item["source_record_id"],
            item["source_key"], item["native_record_id"], item["record_unit"],
            item.get("split"), item.get("learner_id_pseudonym"),
            item.get("document_id_pseudonym"), item.get("task_id"),
            item.get("proficiency_label"), item.get("source_path"),
            item.get("text_fingerprint"), item.get("text_length"),
            _json(item.get("metadata", {})), _json(item.get("provenance", {})),
        )
        for item in _iter_jsonl_paths(paths)
    )
    return _execute_batches(connection, sql, rows, batch_size)


def _load_error_instances(
    connection: sqlite3.Connection,
    version_id: int,
    source_ids: dict[str, int],
    paths: Sequence[str | Path],
    batch_size: int,
) -> int:
    sql = """
        INSERT INTO error_instances (
            knowledge_version_id, knowledge_source_id, corpus_source_record_id,
            error_instance_id, source_record_id, source_key, native_error_id,
            label_system, source_label, label_path, label_description,
            span_kind, source_field, start_char, end_char, token_start, token_end,
            selection_fingerprint, selected_text_length, source_markup_path,
            span_confidence, correction_type, correction_fingerprint,
            correction_length, correction_count, status, review_status,
            parser_notes_json, metadata_json, provenance_json
        ) VALUES (
            ?, ?, (SELECT id FROM learner_corpus_source_records
                   WHERE knowledge_version_id = ? AND source_record_id = ?),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """

    def rows() -> Iterator[tuple[object, ...]]:
        for item in _iter_jsonl_paths(paths):
            label = item.get("source_native_label") or {}
            span = item["span"]
            correction = item.get("correction") or {}
            yield (
                version_id, source_ids[item["source_key"]], version_id,
                item["source_record_id"], item["error_instance_id"],
                item["source_record_id"], item["source_key"], item.get("native_error_id"),
                label.get("label_system"), label.get("label"), label.get("label_path"),
                label.get("description"), span["span_kind"], span.get("source_field"),
                span.get("start_char"), span.get("end_char"), span.get("token_start"),
                span.get("token_end"), span.get("selection_fingerprint"),
                span.get("selected_text_length"), span.get("source_markup_path"),
                span.get("confidence", 1.0), correction.get("correction_type"),
                correction.get("correction_fingerprint"), correction.get("correction_length"),
                correction.get("correction_count"), item.get("status", "parsed"),
                item.get("review_status", "pending"), _json(item.get("parser_notes", [])),
                _json(item.get("metadata", {})), _json(item.get("provenance", {})),
            )

    return _execute_batches(connection, sql, rows(), batch_size)


def _load_normalized_errors(
    connection: sqlite3.Connection,
    version_id: int,
    path: str | Path,
    batch_size: int,
) -> int:
    sql = """
        INSERT INTO normalized_error_instances (
            knowledge_version_id, error_instance_db_id, normalized_error_id,
            error_instance_id, source_record_id, source_key, category, subtype,
            status, confidence, reason, review_status, taxonomy_version,
            canonical_skill_candidates_json, metadata_json, provenance_json
        ) VALUES (
            ?, (SELECT id FROM error_instances
                WHERE knowledge_version_id = ? AND error_instance_id = ?),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """

    def rows() -> Iterator[tuple[object, ...]]:
        for item in _iter_jsonl(Path(path)):
            yield (
                version_id, version_id, item["error_instance_id"], item["normalized_error_id"],
                item["error_instance_id"], item["source_record_id"], item["source_key"],
                item["category"], item.get("subtype"), item["status"], item["confidence"],
                item["reason"], item.get("review_status", "pending"), item["taxonomy_version"],
                _json(item.get("canonical_skill_candidates", [])),
                _json(item.get("metadata", {})), _json(item.get("provenance", {})),
            )

    return _execute_batches(connection, sql, rows(), batch_size)


def _execute_batches(
    connection: sqlite3.Connection,
    sql: str,
    rows: Iterable[tuple[object, ...]],
    batch_size: int,
) -> int:
    batch: list[tuple[object, ...]] = []
    total = 0
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            connection.executemany(sql, batch)
            connection.commit()
            total += len(batch)
            batch.clear()
    if batch:
        connection.executemany(sql, batch)
        connection.commit()
        total += len(batch)
    return total


def _iter_jsonl_paths(paths: Sequence[str | Path]) -> Iterator[dict[str, Any]]:
    for path in paths:
        yield from _iter_jsonl(Path(path))


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _scalar(connection: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> int:
    return int(connection.execute(sql, params).fetchone()[0])
