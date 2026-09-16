from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from knowledge_core.storage.artifacts import load_storage_artifacts
from knowledge_core.storage.config import DEFAULT_VERSION_NAME, resolve_db_path
from knowledge_core.storage.loader import load_knowledge_core
from knowledge_core.storage.schema import (
    KNOWLEDGE_TABLES,
    KNOWLEDGE_VIEWS,
    initialize_schema,
    sqlite_connection,
)
from knowledge_core.storage.validator import validate_storage


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db-path", default=argparse.SUPPRESS, help="SQLite database path.")
    common.add_argument(
        "--schema",
        default=argparse.SUPPRESS,
        help="Schema SQL path; defaults to app/persistence/schema.sql.",
    )
    common.add_argument(
        "--version-name",
        default=argparse.SUPPRESS,
        help="Knowledge version name to load or validate.",
    )

    parser = argparse.ArgumentParser(
        description="Knowledge Core Storage V1 schema, loader, and validator.",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "init",
        parents=[common],
        help="Initialize the local SQLite schema.",
    )

    load_parser = subparsers.add_parser(
        "load",
        parents=[common],
        help="Load Knowledge Core artifacts.",
    )
    load_parser.add_argument(
        "--twice",
        action="store_true",
        help="Run the loader twice and report idempotency counts.",
    )

    subparsers.add_parser(
        "validate",
        parents=[common],
        help="Validate persisted Knowledge Core data.",
    )
    subparsers.add_parser(
        "inspect",
        parents=[common],
        help="Inspect storage schema and artifact counts.",
    )

    reset_parser = subparsers.add_parser(
        "reset-version",
        parents=[common],
        help="Delete one explicitly named Knowledge Core version.",
    )
    reset_parser.add_argument("version", help="Version name to delete.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.db_path = getattr(args, "db_path", None)
    args.schema = getattr(args, "schema", None)
    args.version_name = getattr(args, "version_name", DEFAULT_VERSION_NAME)
    if args.command == "init":
        result = initialize_schema(args.db_path, args.schema)
        _print_json({"result": "ok", **result})
        return 0

    if args.command == "load":
        initialize_schema(args.db_path, args.schema)
        before = _validation_snapshot(args.db_path, args.version_name)
        first = load_knowledge_core(
            db_path=args.db_path,
            version_name=args.version_name,
            ensure_schema=False,
        )
        second = None
        duplicates_created = None
        if args.twice:
            second_result = load_knowledge_core(
                db_path=args.db_path,
                version_name=args.version_name,
                ensure_schema=False,
            )
            second = second_result.db_counts
            duplicates_created = _duplicates_created(first.db_counts, second)
        validation = validate_storage(
            db_path=args.db_path,
            version_name=args.version_name,
        )
        _print_json(
            {
                "result": "ok" if validation.is_valid else "validation_failed",
                "version_name": first.version_name,
                "taxonomy_hash": first.taxonomy_hash,
                "before_load_counts": before,
                "first_load_counts": first.db_counts,
                "second_load_counts": second,
                "duplicates_created": duplicates_created,
                "validation": validation.to_dict(),
            },
        )
        return 0 if validation.is_valid else 1

    if args.command == "validate":
        initialize_schema(args.db_path, args.schema)
        validation = validate_storage(
            db_path=args.db_path,
            version_name=args.version_name,
        )
        _print_json(validation.to_dict())
        return 0 if validation.is_valid else 1

    if args.command == "inspect":
        initialize_schema(args.db_path, args.schema)
        artifacts = load_storage_artifacts()
        with sqlite_connection(args.db_path) as connection:
            table_count = _sqlite_object_count(connection, KNOWLEDGE_TABLES, "table")
            view_count = _sqlite_object_count(connection, KNOWLEDGE_VIEWS, "view")
        _print_json(
            {
                "db_path": args.db_path,
                "resolved_db_path": str(resolve_db_path(args.db_path)),
                "schema_path": args.schema or "app/persistence/schema.sql",
                "knowledge_core_tables_expected": len(KNOWLEDGE_TABLES),
                "knowledge_core_tables_existing": table_count,
                "knowledge_core_views_expected": len(KNOWLEDGE_VIEWS),
                "knowledge_core_views_existing": view_count,
                "artifact_counts": artifacts.counts(),
            },
        )
        return 0

    if args.command == "reset-version":
        initialize_schema(args.db_path, args.schema)
        deleted = _reset_version(args.db_path, args.version)
        _print_json({"result": "ok", "version_name": args.version, "deleted": deleted})
        return 0

    return 2


def _validation_snapshot(
    db_path: str | Path | None,
    version_name: str,
) -> dict[str, int]:
    validation = validate_storage(db_path=db_path, version_name=version_name)
    return validation.counts


def _duplicates_created(
    first_counts: dict[str, int],
    second_counts: dict[str, int],
) -> dict[str, int]:
    keys = sorted(set(first_counts) & set(second_counts))
    return {
        key: second_counts[key] - first_counts[key]
        for key in keys
        if second_counts[key] != first_counts[key]
    }


def _sqlite_object_count(connection: Any, names: tuple[str, ...], object_type: str) -> int:
    placeholders = ",".join("?" for _ in names)
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM sqlite_master
        WHERE type = ? AND name IN ({placeholders})
        """,
        (object_type, *names),
    ).fetchone()
    return int(row["count"])


def _reset_version(db_path: str | Path | None, version_name: str) -> bool:
    from knowledge_core.storage.loader import _clear_version_scoped_data

    with sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT id FROM knowledge_versions WHERE version_name = ?",
            (version_name,),
        ).fetchone()
        if row is None:
            return False
        version_id = int(row["id"])
        _clear_version_scoped_data(connection, version_id)
        connection.execute("DELETE FROM knowledge_versions WHERE id = ?", (version_id,))
        return True


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
